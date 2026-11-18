"""Regulile din regulamentul USV, verificate prin API (IP-30).

Ruleaza cu TestClient pe o baza SQLite separata, noua la fiecare test (vezi conftest.py).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import LOCAL_TZ
from app.models import MaintenanceBlock, Reservation, ReservationStatus, User, UserRole
from tests.conftest import local_slot

URL = "/api/v1/reservations"


def book(client: TestClient, headers: dict, resource_id: int, slot: tuple[datetime, datetime]):
    start, end = slot
    return client.post(
        URL,
        json={"resourceId": resource_id, "start": start.isoformat(), "end": end.isoformat()},
        headers=headers,
    )


def add_existing(
    db: Session,
    user: User,
    resource_id: int,
    slot: tuple[datetime, datetime],
    status: ReservationStatus = ReservationStatus.CONFIRMED,
) -> Reservation:
    reservation = Reservation(
        user_id=user.id,
        resource_id=resource_id,
        start_time=slot[0],
        end_time=slot[1],
        amount=Decimal("40"),
        status=status,
    )
    db.add(reservation)
    db.commit()
    return reservation


# --- maxim 3 rezervari pe luna pentru studenti ---


def test_fourth_reservation_in_a_month_is_refused_for_student(
    client: TestClient, make_user, court
) -> None:
    _, headers = make_user(UserRole.STUDENT)
    # toate in aceeasi zi, deci sigur in aceeasi luna
    for hour in (10, 11, 12):
        assert book(client, headers, court.id, local_slot(3, hour)).status_code == 201

    response = book(client, headers, court.id, local_slot(3, 13))

    assert response.status_code == 403
    assert response.json() == {"detail": "Ai atins limita de 3 rezervari pe luna"}


def test_cancelled_reservations_do_not_count_for_the_limit(
    client: TestClient, make_user, court, db
) -> None:
    student, headers = make_user(UserRole.STUDENT)
    add_existing(db, student, court.id, local_slot(3, 10), ReservationStatus.CANCELLED)
    for hour in (11, 12):
        assert book(client, headers, court.id, local_slot(3, hour)).status_code == 201

    assert book(client, headers, court.id, local_slot(3, 13)).status_code == 201


def test_professor_has_no_monthly_limit(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.PROFESSOR, email="maria.ionescu@usm.ro")
    for hour in (10, 11, 12, 13):
        assert book(client, headers, court.id, local_slot(3, hour)).status_code == 201


def test_limit_is_per_student(client: TestClient, make_user, court) -> None:
    _, first = make_user(UserRole.STUDENT)
    _, second = make_user(UserRole.STUDENT)
    for hour in (10, 11, 12):
        assert book(client, first, court.id, local_slot(3, hour)).status_code == 201

    assert book(client, second, court.id, local_slot(3, 13)).status_code == 201


# --- maxim 14 zile inainte ---


def test_reservation_15_days_ahead_is_refused(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)

    response = book(client, headers, court.id, local_slot(15, 10))

    assert response.status_code == 400
    assert response.json() == {"detail": "Se poate rezerva cu maxim 14 zile inainte"}


def test_reservation_13_days_ahead_is_allowed(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)
    assert book(client, headers, court.id, local_slot(13, 10)).status_code == 201


# --- fara suprapuneri ---


def test_same_interval_twice_is_refused(client: TestClient, make_user, court) -> None:
    _, first = make_user(UserRole.STUDENT)
    _, second = make_user(UserRole.STUDENT)
    slot = local_slot(2, 18)
    assert book(client, first, court.id, slot).status_code == 201

    response = book(client, second, court.id, slot)

    assert response.status_code == 409
    assert response.json() == {"detail": "Intervalul este deja ocupat"}


def test_partly_overlapping_interval_is_refused(client: TestClient, make_user, court) -> None:
    _, first = make_user(UserRole.STUDENT)
    _, second = make_user(UserRole.STUDENT)
    assert book(client, first, court.id, local_slot(2, 18, hours=2)).status_code == 201

    assert book(client, second, court.id, local_slot(2, 19, hours=2)).status_code == 409


def test_back_to_back_intervals_are_allowed(client: TestClient, make_user, court) -> None:
    _, first = make_user(UserRole.STUDENT)
    _, second = make_user(UserRole.STUDENT)
    assert book(client, first, court.id, local_slot(2, 18)).status_code == 201
    assert book(client, second, court.id, local_slot(2, 19)).status_code == 201


def test_cancelled_interval_can_be_booked_again(client: TestClient, make_user, court, db) -> None:
    other, _ = make_user(UserRole.STUDENT)
    _, headers = make_user(UserRole.STUDENT)
    slot = local_slot(2, 18)
    add_existing(db, other, court.id, slot, ReservationStatus.CANCELLED)

    assert book(client, headers, court.id, slot).status_code == 201


def test_maintenance_interval_is_refused(client: TestClient, make_user, court, db) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 8, hours=4)
    db.add(MaintenanceBlock(resource_id=court.id, start_time=start, end_time=end))
    db.commit()

    response = book(client, headers, court.id, local_slot(2, 9))

    assert response.status_code == 409
    assert response.json() == {"detail": "Intervalul este blocat pentru mentenanta"}


# --- cont blocat ---


def test_blocked_account_cannot_book(client: TestClient, make_user, court, db) -> None:
    student, headers = make_user(UserRole.STUDENT)
    student.blocked_until = datetime.now(LOCAL_TZ) + timedelta(days=10)
    db.commit()

    response = book(client, headers, court.id, local_slot(2, 18))

    assert response.status_code == 403
    assert response.json() == {"detail": "Contul este blocat din cauza neprezentarilor"}


# --- anulare cu minim 2 ore inainte ---


def hours_from_now(hours: int) -> tuple[datetime, datetime]:
    """Un interval care incepe intre hours-1 si hours ore de acum (la ora fixa)."""
    # in UTC, cum salveaza si aplicatia (SQLite pastreaza ora fara fus orar)
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start += timedelta(hours=hours)
    return start, start + timedelta(hours=1)


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.PROFESSOR])
def test_cancel_one_hour_before_is_refused(client: TestClient, make_user, court, db, role) -> None:
    user, headers = make_user(role)
    # incepe in mai putin de 2 ore
    reservation = add_existing(db, user, court.id, hours_from_now(2))

    response = client.delete(f"{URL}/{reservation.id}", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Anularea se poate face cu minim 2 ore inainte"}
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CONFIRMED


def test_cancel_three_hours_before_is_allowed(client: TestClient, make_user, court, db) -> None:
    student, headers = make_user(UserRole.STUDENT)
    reservation = add_existing(db, student, court.id, hours_from_now(4))

    assert client.delete(f"{URL}/{reservation.id}", headers=headers).status_code == 200


def test_admin_can_cancel_one_hour_before(client: TestClient, make_user, court, db) -> None:
    student, _ = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)
    reservation = add_existing(db, student, court.id, hours_from_now(1))

    assert client.delete(f"{URL}/{reservation.id}", headers=admin).status_code == 200
