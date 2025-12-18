import dataclasses
import logging
import sys
import os

from app.config.db import AsyncSession
from app.config.init_db import init_db
from app.models.cars import CarModel
from app.parser.extract_data import (
    extract_odometer,
    extract_main_image,
    extract_images_count,
    extract_vin,
    extract_car_number,
    extract_phone,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datetime
import httpx
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("BASE_URL")


@dataclasses.dataclass
class Car:
    url: str
    title: str
    price_usd: int
    odometer: int
    username: str
    phone_number: int | None
    image_url: str
    images_count: int
    car_number: str
    car_vin: str
    datetime_found: datetime.datetime


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s]: %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler(sys.stdout),
    ],
)


async def parse_single_car(
    client: httpx.AsyncClient,
    car: Tag,
) -> Car:
    url = car.select_one(".m-link-ticket")["href"]

    response = await client.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    title = car.select_one(".blue.bold").get_text(strip=True)

    price_usd = int(car.select_one("div.price-ticket")["data-main-price"])

    odometer = extract_odometer(car)

    username_tag = soup.select_one("#sellerInfoUserName span")
    username = username_tag.get_text(strip=True) if username_tag else None

    image_url = extract_main_image(soup)

    images_count = extract_images_count(soup)

    car_vin = extract_vin(soup)

    car_number = extract_car_number(soup)

    phone_number = await extract_phone(url)

    found_at = datetime.datetime.utcnow()

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
        datetime_found=found_at,
    )


async def car_exists(session: AsyncSession, url: str) -> bool:
    result = await session.execute(
        CarModel.__table__.select().where(CarModel.url == url)
    )
    return result.first() is not None


async def get_home_cars():
    page = 1
    async with httpx.AsyncClient() as client, AsyncSession() as session:
        while True:
            logging.info(f"Start parsing for page {page}")
            url = f"{BASE_URL}?page={page}"
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            car_cards = soup.select(".content-bar")
            if not car_cards:
                logging.info("No cars found, stop parsing")
                break

            for car_card in car_cards:
                car = await parse_single_car(client, car_card)

                if await car_exists(session, car.url):
                    logging.info(f"Car {car.url} already exists, skipping")
                    continue

                db_car = CarModel(
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
                session.add(db_car)
            await session.commit()
            page += 1


async def main():
    logging.info("Initializing DB...")
    await init_db()
    logging.info("Start parser...")
    await get_home_cars()
    logging.info("Finished.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
