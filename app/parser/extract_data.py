import asyncio
import logging
import random
import re
from typing import Optional

from playwright.async_api import BrowserContext
from bs4 import Tag, BeautifulSoup


logger = logging.getLogger(__name__)

VIN_RE = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
CAR_NUMBER_RE = re.compile(r"\b[A-ZА-ЯІЇЄ]{2}\s?\d{4}\s?[A-ZА-ЯІЇЄ]{2}\b")
PHONE_RE = re.compile(r"[^\d]+")


def extract_vin(soup: BeautifulSoup) -> Optional[str]:
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if VIN_RE.fullmatch(text):
            return text
    return None


def extract_car_number(soup: BeautifulSoup) -> Optional[str]:
    for span in soup.find_all("span"):
        text = span.get_text(strip=True).upper()
        if CAR_NUMBER_RE.fullmatch(text):
            return text
    return None


def extract_main_image(soup: BeautifulSoup) -> Optional[str]:
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


def normalize_phone(raw_phone: str) -> Optional[int]:
    phone_digits = PHONE_RE.sub("", raw_phone)

    if len(phone_digits) == 10 and phone_digits.startswith("0"):
        phone_digits = "38" + phone_digits
    elif len(phone_digits) == 9:
        phone_digits = "380" + phone_digits
    elif not phone_digits.startswith("38") and len(phone_digits) >= 10:
        phone_digits = "38" + phone_digits[-10:]

    try:
        return int(phone_digits)
    except ValueError:
        return None


async def extract_phone_from_page(url: str, context: BrowserContext) -> Optional[int]:
    page = await context.new_page()

    try:
        await asyncio.sleep(random.uniform(0.5, 1.5))

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        await asyncio.sleep(random.uniform(1.0, 2.0))

        try:
            cookie_btn = page.locator(
                'button:has-text("Розумію"), button:has-text("Accept")'
            ).first
            if await cookie_btn.is_visible(timeout=1000):
                await cookie_btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        await page.mouse.move(random.randint(100, 500), random.randint(100, 300))
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.mouse.wheel(0, random.randint(200, 400))
        await asyncio.sleep(random.uniform(0.5, 1.0))

        button_selectors = [
            '#sellerInfo button[data-action="showBottomPopUp"]',
            "#sellerInfo button",
            ".phones_list.mb-15 .m-link-ticket",
            "span.phone_show_link",
            "a.phone_show_link",
            ".seller-phones button",
            "button.show-phone",
            '[class*="phone"] button',
            'span:has-text("XXX")',
        ]

        button_clicked = False
        for selector in button_selectors:
            try:
                show_button = page.locator(selector).first
                if await show_button.is_visible(timeout=2000):
                    await show_button.hover()
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await show_button.click()
                    button_clicked = True
                    logger.debug(f"Clicked button: {selector}")
                    break
            except Exception:
                continue

        if not button_clicked:
            logger.debug(f"No phone button found for {url}")
            return None

        await asyncio.sleep(random.uniform(1.5, 3.0))

        phone_selectors = [
            ".popup-inner button[data-action='call']",
            ".popup-inner a[href^='tel:']",
            "div.list-phone a[href^='tel:']",
            "a[href^='tel:']",
            ".phone:not(:has-text('XXX'))",
            "div.list-phone a",
        ]

        raw_phone = None
        for selector in phone_selectors:
            try:
                phone_el = page.locator(selector).first
                if await phone_el.is_visible(timeout=2000):
                    href = await phone_el.get_attribute("href")
                    if href and href.startswith("tel:"):
                        raw_phone = href.replace("tel:", "")
                        logger.debug(f"Found phone from href: {selector}")
                        break
                    raw_phone = await phone_el.inner_text()
                    if raw_phone and any(c.isdigit() for c in raw_phone):
                        logger.debug(f"Found phone from text: {selector}")
                        break
            except Exception:
                continue

        if not raw_phone:
            logger.debug(f"Phone not visible after click for {url}")
            return None

        return normalize_phone(raw_phone)

    except Exception as e:
        logger.warning(f"Error extracting phone for {url}: {e}")
        return None
    finally:
        await page.close()
