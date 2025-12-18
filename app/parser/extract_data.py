import random
import re
from playwright.async_api import Page, async_playwright
from bs4 import Tag
from bs4 import BeautifulSoup
import asyncio


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


async def extract_number(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url)
        await page.click('#sellerInfo button[data-action="showBottomPopUp"]')

        phone_link = await page.wait_for_selector('a.action-wrapper-link[href^="tel:"]')

        phone = (await phone_link.get_attribute("href")).replace("tel:", "")
        phone_number = re.sub(r"[^\d+]", "", phone)
        if not phone_number.startswith("38"):
            phone_number = "38" + phone_number[-10:]
        await browser.close()
        return int(phone_number)
