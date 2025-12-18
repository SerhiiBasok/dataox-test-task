import os
from dataclasses import dataclass


@dataclass
class Config:
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    dump_folder: str
    dump_hour: int
    dump_minute: int


def load_config() -> Config:
    try:
        return Config(
            db_name=os.environ["POSTGRES_DB"],
            db_user=os.environ["POSTGRES_USER"],
            db_password=os.environ["POSTGRES_PASSWORD"],
            db_host=os.environ["POSTGRES_HOST"],
            db_port=os.environ.get("POSTGRES_PORT"),
            dump_folder=os.environ.get("DUMP_FOLDER"),
            dump_hour=int(os.environ["DUMP_HOUR"]),
            dump_minute=int(os.environ["DUMP_MINUTE"]),
        )
    except KeyError as e:
        raise RuntimeError(f"Missing required env var: {e.args[0]}")
