import os
import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta
import pytz
from app.dumper.config import load_config
from app.dumper.dump import dump_postgres_db

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dumper_scheduler")

TIMEZONE = pytz.timezone("Europe/Kiev")


async def scheduler(cfg):
    while True:
        now = datetime.now(TIMEZONE)
        target_today = TIMEZONE.localize(
            datetime.combine(now.date(), dt_time(cfg.dump_hour, cfg.dump_minute))
        )

        if now >= target_today:
            target_today += timedelta(days=1)

        wait_seconds = (target_today - now).total_seconds()
        logger.info(
            f"Next dump scheduled at {target_today.strftime('%Y-%m-%d %H:%M:%S')} "
            f"({int(wait_seconds)} seconds from now)"
        )

        await asyncio.sleep(wait_seconds)

        logger.info(
            f"Starting dump at {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        try:
            await dump_postgres_db(cfg)
            logger.info("Dump completed successfully.")
        except Exception as e:
            logger.error(f"Dump failed: {e}")

        await asyncio.sleep(10)


def main():
    cfg = load_config()
    os.makedirs(cfg.dump_folder, exist_ok=True)
    asyncio.run(scheduler(cfg))


if __name__ == "__main__":
    main()
