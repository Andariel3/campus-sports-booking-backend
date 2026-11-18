from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    MaintenanceBlock,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceSchedule,
    SportType,
    UserRole,
)

# o zi de iarna (UTC+2): 08:00 ora Romaniei = 06:00 UTC
DAY = date(2026, 12, 10)


def utc(hour: int) -> datetime:
    return datetime(2026, 12, 10, hour, 0, tzinfo=UTC)


@pytest.fixture
def court(db: Session) -> Resource:
    resource = Resource(name="Teren tenis 1", sport_type=SportType(label="tenis"))
    resource.schedules = [
        ResourceSchedule(day_of_week=d, open_time=time(8), close_time=time(12)) for d in range(7)
    ]
    db.add(resource)
    db.commit()
    return resource


def url(resource_id: int, day: date = DAY) -> str:
    return f"/api/v1/resources/{resource_id}/availability?date={day.isoformat()}"


def statuses(client: TestClient, resource_id: int) -> list[str]:
    return [slot["status"] for slot in client.get(url(resource_id)).json()["slots"]]


def test_free_day_has_one_hour_slots_in_local_time(client: TestClient, court) -> None:
    response = client.get(url(court.id))

    assert response.status_code == 200
    body = response.json()
    assert body["resourceId"] == court.id
    assert body["date"] == "2026-12-10"
    assert [s["status"] for s in body["slots"]] == ["liber"] * 4
    first = body["slots"][0]
    assert datetime.fromisoformat(first["start"]) == utc(6)
    assert datetime.fromisoformat(first["end"]) == utc(7)


def test_reserved_and_maintenance_hours(client: TestClient, court, db, make_user) -> None:
    user, _ = make_user(UserRole.STUDENT)
    db.add_all(
        [
            Reservation(
                user_id=user.id,
                resource_id=court.id,
                start_time=utc(6),
                end_time=utc(7),
                amount=Decimal("0"),
            ),
            MaintenanceBlock(resource_id=court.id, start_time=utc(8), end_time=utc(10)),
        ]
    )
    db.commit()

    assert statuses(client, court.id) == ["ocupat", "liber", "mentenanta", "mentenanta"]


def test_cancelled_reservation_frees_the_slot(client: TestClient, court, db, make_user) -> None:
    user, _ = make_user(UserRole.STUDENT)
    db.add(
        Reservation(
            user_id=user.id,
            resource_id=court.id,
            start_time=utc(6),
            end_time=utc(7),
            amount=Decimal("0"),
            status=ReservationStatus.CANCELLED,
        )
    )
    db.commit()

    assert statuses(client, court.id) == ["liber"] * 4


def test_partial_overlap_marks_the_slot(client: TestClient, court, db, make_user) -> None:
    user, _ = make_user(UserRole.STUDENT)
    db.add(
        MaintenanceBlock(
            resource_id=court.id,
            start_time=utc(6) + timedelta(minutes=30),
            end_time=utc(7) + timedelta(minutes=15),
        )
    )
    db.commit()
    assert statuses(client, court.id) == ["mentenanta", "mentenanta", "liber", "liber"]


def test_inactive_resource_has_no_slots(client: TestClient, court, db) -> None:
    court.is_active = False
    db.commit()
    assert client.get(url(court.id)).json()["slots"] == []


def test_missing_resource_and_bad_date(client: TestClient, court) -> None:
    assert client.get(url(999)).status_code == 404
    response = client.get(f"/api/v1/resources/{court.id}/availability?date=10-12-2026")
    assert response.status_code == 422
    assert client.get(f"/api/v1/resources/{court.id}/availability").status_code == 422
