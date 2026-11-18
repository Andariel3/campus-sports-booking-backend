from datetime import time
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResourceType(StrEnum):
    """Tipul din API (Swagger). In baza de date nu e coloana, se deduce din sport."""

    TEREN = "teren"
    BAZIN = "bazin"


# sporturile care se fac in bazin; restul sunt terenuri
POOL_SPORTS = {"inot", "înot", "natatie", "înot (bazin)"}


class SportType(Base):
    """Tabela sport_types din schema BD (fotbal, tenis, inot...)."""

    __tablename__ = "sport_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(100), unique=True)


class Resource(Base):
    """Un teren sau bazinul. Tabela resources din schema BD."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("sport_types.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    price_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sport_type: Mapped[SportType | None] = relationship(lazy="joined")
    schedules: Mapped[list["ResourceSchedule"]] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
        order_by="ResourceSchedule.day_of_week",
        lazy="selectin",
    )

    @property
    def sport(self) -> str:
        return self.sport_type.label if self.sport_type else ""

    @property
    def type(self) -> ResourceType:
        return ResourceType.BAZIN if self.sport.lower() in POOL_SPORTS else ResourceType.TEREN

    @property
    def open_hour(self) -> time | None:
        # in API e un singur program pentru toate zilele, il luam din prima zi activa
        active = [s for s in self.schedules if s.is_active]
        return active[0].open_time if active else None

    @property
    def close_hour(self) -> time | None:
        active = [s for s in self.schedules if s.is_active]
        return active[0].close_time if active else None

    def schedule_for(self, weekday: int) -> "ResourceSchedule | None":
        """Programul pentru o zi (0 = luni ... 6 = duminica, ca date.weekday())."""
        for schedule in self.schedules:
            if schedule.day_of_week == weekday and schedule.is_active:
                return schedule
        return None


class ResourceSchedule(Base):
    """Programul pe zile al unei resurse. Tabela resource_schedules din schema BD."""

    __tablename__ = "resource_schedules"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="check_day_of_week"),
        CheckConstraint("open_time < close_time", name="check_schedule_times"),
        UniqueConstraint("resource_id", "day_of_week", name="unique_resource_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(Integer)
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    resource: Mapped[Resource] = relationship(back_populates="schedules")
