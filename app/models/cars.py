from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Cars(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    price_usd: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )

    odometer: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    phone_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=True,
    )

    image_url: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    images_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )

    car_number: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    car_vin: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    datetime_found: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
