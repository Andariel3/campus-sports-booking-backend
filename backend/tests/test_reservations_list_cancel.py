from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import LOCAL_TZ
from app.models import Reservation, ReservationStatus, Resource, User, UserRole
from tests.conftest import local_slot

URL = "/api/v1/reservations"


def add(
    db: Session,
    user: User,
    resource: Resource,
    slot: tuple[datetime, datetime],
    status: ReservationStatus = ReservationStatus.CONFIRMED,
) -> Reservation:
    """Rezervare pusa direct in baza (si in trecut, unde API-ul nu lasa)."""
    reservation = Reservation(
        user_id=user.id,
        resource_id=resource.id,
        start_time=slot[0],
        end_time=slot[1],
        amount=Decimal("40"),
        status=status,
    )
    db.add(reservation)
    db.commit()
    return reservation


@pytest.fixture
def people(make_user):
    student, student_headers = make_user(UserRole.STUDENT)
    other, other_headers = make_user(UserRole.STUDENT)
    admin, admin_headers = make_user(UserRole.ADMINISTRATOR)
    return {
        "student": (student, student_headers),
        "other": (other, other_headers),
        "admin": (admin, admin_headers),
    }


def ids(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [r["id"] for r in response.json()]


def test_users_see_only_their_reservations_admin_sees_all(
    client: TestClient, db, court, people
) -> None:
    student, student_headers = people["student"]
    other, _ = people["other"]
    mine = add(db, student, court, local_slot(1, 10))
    theirs = add(db, other, court, local_slot(1, 11))

    assert ids(client.get(URL, headers=student_headers)) == [mine.id]
    assert ids(client.get(URL, headers=people["admin"][1])) == [theirs.id, mine.id]
    assert client.get(URL).status_code == 401


def test_status_filter_uses_api_names(client: TestClient, db, court, people) -> None:
    student, headers = people["student"]
    active = add(db, student, court, local_slot(1, 10))
    finished = add(db, student, court, local_slot(-2, 10))
    cancelled = add(db, student, court, local_slot(2, 10), ReservationStatus.CANCELLED)
    no_show = add(db, student, court, local_slot(-3, 10), ReservationStatus.NO_SHOW)

    def by_status(status: str) -> list[int]:
        return ids(client.get(URL, params={"status": status}, headers=headers))

    assert by_status("ACTIVA") == [active.id]
    assert by_status("FINALIZATA") == [finished.id]
    assert by_status("ANULATA") == [cancelled.id]
    assert by_status("NEPREZENTARE") == [no_show.id]
    statuses = {r["id"]: r["status"] for r in client.get(URL, headers=headers).json()}
    assert statuses[finished.id] == "FINALIZATA"
    assert client.get(URL, params={"status": "Confirmed"}, headers=headers).status_code == 422


def test_date_and_resource_filters(client: TestClient, db, court, people) -> None:
    student, headers = people["student"]
    pool = Resource(name="Bazin", sport_type=court.sport_type)
    db.add(pool)
    db.commit()
    tomorrow = add(db, student, court, local_slot(1, 10))
    later = add(db, student, court, local_slot(5, 10))
    in_pool = add(db, student, pool, local_slot(1, 12))

    day = (datetime.now(LOCAL_TZ) + timedelta(days=1)).date().isoformat()
    params = {"from": day, "to": day}
    assert ids(client.get(URL, params=params, headers=headers)) == [in_pool.id, tomorrow.id]
    assert ids(client.get(URL, params={"resourceId": court.id}, headers=headers)) == [
        later.id,
        tomorrow.id,
    ]


def test_get_one(client: TestClient, db, court, people) -> None:
    student, headers = people["student"]
    reservation = add(db, student, court, local_slot(1, 10))

    response = client.get(f"{URL}/{reservation.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == reservation.id
    # rezervarea altcuiva apare ca inexistenta
    assert client.get(f"{URL}/{reservation.id}", headers=people["other"][1]).status_code == 404
    assert client.get(f"{URL}/{reservation.id}", headers=people["admin"][1]).status_code == 200
    response = client.get(f"{URL}/999", headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Rezervarea 999 nu exista"}


def test_cancel_keeps_the_row_and_frees_the_slot(client: TestClient, db, court, people) -> None:
    student, headers = people["student"]
    reservation = add(db, student, court, local_slot(1, 10))

    response = client.delete(f"{URL}/{reservation.id}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ANULATA"
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.cancelled_by_id == student.id
    assert reservation.cancelled_at is not None
    day = local_slot(1, 10)[0].astimezone(LOCAL_TZ).date().isoformat()
    slots = client.get(f"/api/v1/resources/{court.id}/availability?date={day}").json()["slots"]
    assert all(s["status"] == "liber" for s in slots)


def test_cannot_cancel_someone_elses_reservation(client: TestClient, db, court, people) -> None:
    student, _ = people["student"]
    reservation = add(db, student, court, local_slot(1, 10))

    response = client.delete(f"{URL}/{reservation.id}", headers=people["other"][1])
    assert response.status_code == 403
    assert response.json() == {"detail": "Rezervarea nu este a ta"}


def test_admin_cancels_any_time(client: TestClient, db, court, people) -> None:
    student, _ = people["student"]
    start = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    reservation = add(db, student, court, (start, start + timedelta(hours=1)))

    response = client.delete(f"{URL}/{reservation.id}", headers=people["admin"][1])
    assert response.status_code == 200
    db.refresh(reservation)
    assert reservation.cancelled_by_id == people["admin"][0].id


def test_cancel_twice_or_after_no_show_returns_400(client: TestClient, db, court, people) -> None:
    student, headers = people["student"]
    cancelled = add(db, student, court, local_slot(1, 10), ReservationStatus.CANCELLED)
    no_show = add(db, student, court, local_slot(-1, 10), ReservationStatus.NO_SHOW)

    assert client.delete(f"{URL}/{cancelled.id}", headers=headers).json() == {
        "detail": "Rezervarea este deja anulata"
    }
    response = client.delete(f"{URL}/{no_show.id}", headers=people["admin"][1])
    assert response.status_code == 400
    assert client.delete(f"{URL}/999", headers=headers).status_code == 404
