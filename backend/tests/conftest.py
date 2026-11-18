from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
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
