import asyncio
from app.dumper.config import load_config
from app.dumper.dump import dump_postgres_db

cfg = load_config()

asyncio.run(dump_postgres_db(cfg))
