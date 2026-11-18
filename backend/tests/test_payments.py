from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Reservation, ReservationStatus, UserRole
from tests.conftest import local_slot

URL = "/api/v1/reservations"


@pytest.fixture
def reservation(db: Session, make_user, court) -> Reservation:
    student, _ = make_user(UserRole.STUDENT)
    start, end = local_slot(1, 10)
    reservation = Reservation(
        user_id=student.id,
        resource_id=court.id,
        start_time=start,
        end_time=end,
        amount=Decimal("40"),
    )
    db.add(reservation)
    db.commit()
    return reservation


def pay(client: TestClient, headers: dict, reservation_id: int, status: str):
    return client.patch(
        f"{URL}/{reservation_id}/payment", json={"paymentStatus": status}, headers=headers
    )


def test_new_reservation_is_unpaid(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 10)
    response = client.post(
        URL,
        json={"resourceId": court.id, "start": start.isoformat(), "end": end.isoformat()},
        headers=headers,
    )
    assert response.json()["paymentStatus"] == "NEACHITATA"
    assert response.json()["paidAt"] is None


def test_admin_marks_paid_and_unpaid(client: TestClient, make_user, reservation, db) -> None:
    _, admin = make_user(UserRole.ADMINISTRATOR)

    response = pay(client, admin, reservation.id, "ACHITATA")

    assert response.status_code == 200, response.text
    assert response.json()["paymentStatus"] == "ACHITATA"
    assert response.json()["paidAt"] is not None
    db.refresh(reservation)
    assert reservation.is_paid is True and reservation.paid_at is not None

    response = pay(client, admin, reservation.id, "NEACHITATA")
    assert response.json()["paymentStatus"] == "NEACHITATA"
    db.refresh(reservation)
    assert reservation.is_paid is False and reservation.paid_at is None


def test_only_admin_can_mark_payment(client: TestClient, make_user, reservation) -> None:
    _, student = make_user(UserRole.STUDENT)
    _, professor = make_user(UserRole.PROFESSOR)

    assert pay(client, student, reservation.id, "ACHITATA").status_code == 403
    assert pay(client, professor, reservation.id, "ACHITATA").status_code == 403
    assert client.patch(f"{URL}/{reservation.id}/payment", json={}).status_code == 401


def test_payment_errors(client: TestClient, make_user, reservation, db) -> None:
    _, admin = make_user(UserRole.ADMINISTRATOR)

    assert pay(client, admin, 999, "ACHITATA").status_code == 404
    assert pay(client, admin, reservation.id, "PLATIT").status_code == 422
    assert (
        client.patch(f"{URL}/{reservation.id}/payment", json={}, headers=admin).status_code == 422
    )

    reservation.status = ReservationStatus.CANCELLED
    db.commit()
    response = pay(client, admin, reservation.id, "ACHITATA")
    assert response.status_code == 400
    assert response.json() == {"detail": "Rezervarea este anulata"}


def test_paid_status_shows_in_the_owners_list(
    client: TestClient, make_user, reservation, db
) -> None:
    _, admin = make_user(UserRole.ADMINISTRATOR)
    pay(client, admin, reservation.id, "ACHITATA")

    listed = client.get(URL, headers=admin).json()
    assert [r["paymentStatus"] for r in listed] == ["ACHITATA"]
