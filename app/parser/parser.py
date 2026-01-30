import asyncio
import dataclasses
import logging
import os
import random
import sys
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext
from sqlalchemy import select

from app.config.db import AsyncSession
from app.config.init_db import init_db
from app.models.cars import CarModel
from app.parser.extract_data import (
    extract_car_number,
    extract_images_count,
    extract_main_image,
    extract_odometer,
    extract_phone_from_page,
    extract_vin,
)

load_dotenv()

BASE_URL = os.getenv("BASE_URL")
PAGE_LIMIT = int(os.getenv("PAGE_LIMIT", "1"))
WORKERS = int(os.getenv("WORKERS", "5"))
CAR_PARSE_TIMEOUT = int(os.getenv("CAR_PARSE_TIMEOUT", "120"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))


@dataclasses.dataclass
class Car:
    url: str
    title: str
    price_usd: int
    odometer: int
    username: str
    phone_number: int
    image_url: str
    images_count: int
    car_number: str
    car_vin: str
    datetime_found: datetime


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s]: %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class BrowserContextPool:

    def __init__(self, browser: Browser, size: int = WORKERS):
        self.browser = browser
        self.size = size
        self._pool: asyncio.Queue[BrowserContext] = asyncio.Queue()
        self._created = 0
        self._lock = asyncio.Lock()

    async def _create_context(self) -> BrowserContext:
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        await context.set_extra_http_headers(
            {"Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.google.com/"}
        )
        return context

    async def acquire(self) -> BrowserContext:
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            async with self._lock:
                if self._created < self.size:
                    self._created += 1
                    return await self._create_context()
            return await self._pool.get()

    async def release(self, context: BrowserContext):
        try:
            await context.clear_cookies()
        except Exception:
            pass
        await self._pool.put(context)

    async def close_all(self):
        while not self._pool.empty():
            try:
                ctx = self._pool.get_nowait()
                await ctx.close()
            except asyncio.QueueEmpty:
                break


async def get_existing_urls(session, urls: list[str]) -> set[str]:
    if not urls:
        return set()

    result = await session.execute(select(CarModel.url).where(CarModel.url.in_(urls)))
    return {row[0] for row in result.fetchall()}


async def save_cars_bulk(session, cars: list[Car]) -> int:
    if not cars:
        return 0

    db_cars = [
        CarModel(
            url=car.url,
            title=car.title,
            price_usd=car.price_usd,
            odometer=car.odometer,
            username=car.username,
            phone_number=car.phone_number,
            image_url=car.image_url,
            images_count=car.images_count,
            car_number=car.car_number,
            car_vin=car.car_vin,
            datetime_found=car.datetime_found,
        )
        for car in cars
    ]

    session.add_all(db_cars)
    await session.commit()
    return len(db_cars)


def extract_car_url(car_card: Tag) -> Optional[str]:
    link = car_card.select_one(".m-link-ticket")
    if not link:
        return None
    url = link.get("href")
    if url and "/newauto/" in url:
        return None
    return url


async def parse_single_car(
    client: httpx.AsyncClient,
    car_card: Tag,
    url: str,
    context_pool: BrowserContextPool,
) -> Optional[Car]:

    await asyncio.sleep(random.uniform(0.1, 3.0))

    try:
        async with asyncio.timeout(HTTP_TIMEOUT):
            response = await client.get(url)
    except asyncio.TimeoutError:
        logger.warning(f"HTTP timeout for {url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    title_el = car_card.select_one(".blue.bold")
    title = title_el.get_text(strip=True) if title_el else "Unknown"

    price_el = car_card.select_one("div.price-ticket")
    try:
        price_usd = int(price_el["data-main-price"]) if price_el else 0
    except (ValueError, TypeError, KeyError):
        price_usd = 0

    odometer = extract_odometer(car_card)

    username_tag = soup.select_one("#sellerInfoUserName span")
    username = username_tag.get_text(strip=True) if username_tag else None

    image_url = extract_main_image(soup)
    images_count = extract_images_count(soup)
    car_vin = extract_vin(soup)
    car_number = extract_car_number(soup)

    phone_number = None
    context = await context_pool.acquire()
    try:
        async with asyncio.timeout(90):
            phone_number = await extract_phone_from_page(url, context)
            if phone_number:
                logger.debug(f"Phone extracted: {phone_number} for {url}")
    except asyncio.TimeoutError:
        logger.warning(f"Phone extraction timeout for {url}")
    except Exception as e:
        logger.warning(f"Cannot extract phone for {url}: {e}")
    finally:
        await context_pool.release(context)

    return Car(
        url=url,
        title=title,
        price_usd=price_usd,
        odometer=odometer,
        username=username,
        phone_number=phone_number,
        image_url=image_url,
        images_count=images_count,
        car_number=car_number,
        car_vin=car_vin,
        datetime_found=datetime.now(timezone.utc),
    )


async def process_page(
    page_num: int,
    client: httpx.AsyncClient,
    session,
    context_pool: BrowserContextPool,
    semaphore: asyncio.Semaphore,
) -> int:

    url = f"{BASE_URL}?page={page_num}"
    logger.info(f"Fetching page {page_num}: {url}")

    try:
        async with asyncio.timeout(HTTP_TIMEOUT):
            response = await client.get(url)
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching page {page_num}")
        return 0
    except Exception as e:
        logger.error(f"Error fetching page {page_num}: {e}")
        return 0

    soup = BeautifulSoup(response.text, "html.parser")
    car_cards = soup.select(".content-bar")

    if not car_cards:
        logger.warning(f"No car cards found on page {page_num}")
        return 0

    card_url_pairs = []
    for card in car_cards:
        url = extract_car_url(card)
        if url:
            card_url_pairs.append((card, url))

    if not card_url_pairs:
        return 0

    all_urls = [url for _, url in card_url_pairs]
    existing_urls = await get_existing_urls(session, all_urls)

    new_cards = [
        (card, url) for card, url in card_url_pairs if url not in existing_urls
    ]

    skipped = len(card_url_pairs) - len(new_cards)
    if skipped > 0:
        logger.info(f"Page {page_num}: skipping {skipped} existing cars")

    if not new_cards:
        return 0

    async def parse_with_limit(card: Tag, url: str) -> Optional[Car]:
        async with semaphore:
            try:
                async with asyncio.timeout(CAR_PARSE_TIMEOUT):
                    return await parse_single_car(client, card, url, context_pool)
            except asyncio.TimeoutError:
                logger.error(f"Total timeout parsing {url}")
                return None
            except Exception as e:
                logger.error(f"Error parsing {url}: {e}")
                return None

    tasks = [parse_with_limit(card, url) for card, url in new_cards]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    cars_to_save = [r for r in results if isinstance(r, Car)]

    if cars_to_save:
        try:
            saved_count = await save_cars_bulk(session, cars_to_save)
            logger.info(f"Page {page_num}: saved {saved_count} new cars")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save cars from page {page_num}: {e}")
            await session.rollback()
            return 0

    return 0


async def get_home_cars():
    semaphore = asyncio.Semaphore(WORKERS)
    total_saved = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context_pool = BrowserContextPool(browser, size=WORKERS)

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                async with AsyncSession() as session:
                    for page_num in range(1, PAGE_LIMIT + 1):
                        saved = await process_page(
                            page_num, client, session, context_pool, semaphore
                        )
                        total_saved += saved
        finally:
            await context_pool.close_all()
            await browser.close()

    logger.info(f"Total cars saved: {total_saved}")
    return total_saved


async def main():
    logger.info("Initializing DB...")
    await init_db()
    logger.info(f"Starting parser with {WORKERS} workers...")
    await get_home_cars()
    logger.info("Finished.")


if __name__ == "__main__":
    asyncio.run(main())
