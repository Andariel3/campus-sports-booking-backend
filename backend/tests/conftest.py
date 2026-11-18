from collections.abc import Callable, Generator
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.clock import LOCAL_TZ
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.resource import Resource, ResourceSchedule, SportType
from app.models.user import User, UserRole


@pytest.fixture
def session_factory() -> Generator[sessionmaker, None, None]:
    """O baza SQLite in memorie, noua pentru fiecare test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(session_factory: sessionmaker) -> Generator[Session, None, None]:
    """Sesiune pentru pregatirea datelor direct in baza, in afara API-ului."""
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory: sessionmaker) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db: Session) -> Callable[..., tuple[User, dict[str, str]]]:
    """Creeaza un utilizator direct in baza si intoarce headerul cu tokenul lui."""

    def make(role: UserRole = UserRole.STUDENT, email: str | None = None):
        user = User(
            email=email or f"{role.value.lower()}{db.query(User).count()}@student.usv.ro",
            first_name="Test",
            last_name=role.value,
            password_hash=hash_password("parola-buna-123"),
            role=role,
        )
        db.add(user)
        db.commit()
        return user, {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return make


@pytest.fixture
def court(db: Session) -> Resource:
    """Teren de tenis deschis zilnic 08:00 - 22:00 (ora Romaniei), 40 lei pe ora."""
    resource = Resource(
        name="Teren tenis 1", sport_type=SportType(label="tenis"), price_per_hour=Decimal("40")
    )
    resource.schedules = [
        ResourceSchedule(day_of_week=day, open_time=time(8), close_time=time(22))
        for day in range(7)
    ]
    db.add(resource)
    db.commit()
    return resource


def local_slot(days_ahead: int, hour: int, hours: int = 1) -> tuple[datetime, datetime]:
    """Un interval la ora data (ora Romaniei), peste un numar de zile, in UTC."""
    day = (datetime.now(LOCAL_TZ) + timedelta(days=days_ahead)).date()
    start = datetime.combine(day, time(hour), tzinfo=LOCAL_TZ).astimezone(UTC)
    return start, start + timedelta(hours=hours)
