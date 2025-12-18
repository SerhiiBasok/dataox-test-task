import os
import asyncio
from datetime import datetime
import pandas as pd

from app.dumper.config import Config
from app.config.db import AsyncSession
from app.models.cars import CarModel


async def dump_postgres_db(cfg: Config):
    os.makedirs(cfg.dump_folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    bin_file = os.path.join(cfg.dump_folder, f"dump_{timestamp}.sql")
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = cfg.db_password

    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h",
        cfg.db_host,
        "-p",
        cfg.db_port,
        "-U",
        cfg.db_user,
        "-F",
        "c",
        "-f",
        bin_file,
        cfg.db_name,
        env=env,
    )

    await process.wait()

    if process.returncode == 0:
        print(f"[DUMP] Created binary dump: {bin_file}")
    else:
        print(f"[ERROR] Binary dump failed with return code {process.returncode}")

    csv_file = os.path.join(cfg.dump_folder, f"dump_{timestamp}.csv")
    async with AsyncSession() as session:
        result = await session.execute(CarModel.__table__.select())
        cars = result.fetchall()

    if cars:
        df = pd.DataFrame([dict(row._mapping) for row in cars])
        df.to_csv(csv_file, index=False)
        print(f"[DUMP] Created CSV dump: {csv_file}")
    else:
        print("[DUMP] No data found to dump into CSV")
