import asyncio
import random
import re
from playwright.async_api import Browser
from bs4 import Tag
from bs4 import BeautifulSoup


VIN_RE = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
CAR_NUMBER_RE = re.compile(r"\b[A-ZА-ЯІЇЄ]{2}\s?\d{4}\s?[A-ZА-ЯІЇЄ]{2}\b")


def extract_vin(soup: BeautifulSoup) -> str | None:
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if VIN_RE.fullmatch(text):
            return text
    return None


def extract_car_number(soup: BeautifulSoup) -> str | None:
    for span in soup.find_all("span"):
        text = span.get_text(strip=True).upper()
        if CAR_NUMBER_RE.fullmatch(text):
            return text
    return None


def extract_main_image(soup: BeautifulSoup) -> str | None:
    picture = soup.find("picture", {"data-upload-message": "Завантажено"})
    if picture:
        img = picture.find("img")
        if img:
            return img.get("data-src") or img.get("src")
    return None


def extract_images_count(soup: BeautifulSoup) -> int:
    badge = soup.select_one("span.common-badge.alpha.medium")
    if badge:
        spans = badge.find_all("span")
        if len(spans) >= 2:
            try:
                return int(spans[1].get_text(strip=True))
            except ValueError:
                pass

    panoram_div = soup.select_one("div.panoram-tab.flex.gap-4 label.panoram-tab-item")
    if panoram_div:
        try:
            return int(panoram_div.get_text(strip=True))
        except ValueError:
            return 0

    return 0


def extract_odometer(car_card: Tag) -> int:
    try:
        odometer_text = car_card.select_one("li.item-char.js-race").get_text()
        return int("".join(filter(str.isdigit, odometer_text))) * 1000
    except Exception:
        return 0


PHONE_RE = re.compile(r"[^\d]+")


async def extract_number(url: str, browser: Browser) -> int | None:
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )

    await context.set_extra_http_headers(
        {"Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.google.com/"}
    )

    page = await context.new_page()

    try:
        await asyncio.sleep(random.uniform(1.0, 3.0))
        await page.goto(url, wait_until="load", timeout=60000)
        await page.mouse.wheel(0, 400)
        await asyncio.sleep(random.uniform(0.5, 1.5))

        button_selectors = [
            '#sellerInfo button[data-action="showBottomPopUp"]',
            ".phones_list.mb-15 .m-link-ticket",
            "span.phone_show_link",
        ]

        show_button = None
        for selector in button_selectors:
            show_button = page.locator(selector).first
            if await show_button.is_visible():
                break

        if show_button:
            await show_button.click()
            await asyncio.sleep(random.uniform(1, 2))

        phone_selectors = [
            ".popup-inner button[data-action='call']",
            "div.list-phone a",
            ".phone",
        ]

        raw_phone = None
        for selector in phone_selectors:
            phone_el = page.locator(selector).first
            if await phone_el.is_visible():
                raw_phone = await phone_el.inner_text()
                break

        if not raw_phone:
            return None

        phone_digits = PHONE_RE.sub("", raw_phone)

        if len(phone_digits) == 10 and phone_digits.startswith("0"):
            phone_digits = "38" + phone_digits
        elif len(phone_digits) == 9:
            phone_digits = "380" + phone_digits
        elif not phone_digits.startswith("38") and len(phone_digits) >= 10:
            phone_digits = "38" + phone_digits[-10:]

        return int(phone_digits)

    except Exception as e:
        print(f"Error extracting phone for {url}: {e}")
        return None
    finally:
        await page.close()
        await context.close()
