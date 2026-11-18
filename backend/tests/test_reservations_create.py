from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.clock import LOCAL_TZ
from app.models import Reservation, UserRole
from tests.conftest import local_slot

URL = "/api/v1/reservations"


def body(resource_id: int, start: datetime, end: datetime) -> dict:
    return {"resourceId": resource_id, "start": start.isoformat(), "end": end.isoformat()}


def test_student_creates_reservation(client: TestClient, make_user, court, db) -> None:
    user, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 18, hours=2)

    response = client.post(URL, json=body(court.id, start, end), headers=headers)

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["userId"] == user.id
    assert created["resource"]["name"] == "Teren tenis 1"
    assert created["status"] == "ACTIVA"
    assert created["paymentStatus"] == "NEACHITATA"
    assert created["amount"] == 80
    assert datetime.fromisoformat(created["start"]) == start
    assert db.query(Reservation).count() == 1


def test_time_without_timezone_is_romanian_time(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 18)
    naive_start = start.astimezone(LOCAL_TZ).replace(tzinfo=None)

    response = client.post(
        URL,
        json={
            "resourceId": court.id,
            "start": naive_start.isoformat(),
            "end": (naive_start + timedelta(hours=1)).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert datetime.fromisoformat(response.json()["start"]) == start


def test_reserved_slot_shows_as_taken(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 18)
    client.post(URL, json=body(court.id, start, end), headers=headers)

    day = start.astimezone(LOCAL_TZ).date().isoformat()
    slots = client.get(f"/api/v1/resources/{court.id}/availability?date={day}").json()["slots"]
    taken = [s for s in slots if s["status"] == "ocupat"]
    assert [datetime.fromisoformat(s["start"]) for s in taken] == [start]


def test_requires_login(client: TestClient, court) -> None:
    start, end = local_slot(2, 18)
    assert client.post(URL, json=body(court.id, start, end)).status_code == 401


def test_missing_resource_returns_404(client: TestClient, make_user) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 18)
    response = client.post(URL, json=body(999, start, end), headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Resursa 999 nu exista"}


def test_bad_intervals_return_400(client: TestClient, make_user, court) -> None:
    _, headers = make_user(UserRole.STUDENT)
    start, end = local_slot(2, 18)

    cases = {
        "Ora de sfarsit trebuie sa fie dupa ora de inceput": (end, start),
        "Rezervarile se fac pe ore fixe (de ex. 18:00 - 19:00)": (
            start + timedelta(minutes=30),
            end + timedelta(minutes=30),
        ),
        "Nu se poate rezerva in trecut": local_slot(-1, 18),
        "Intervalul este in afara programului resursei": local_slot(2, 21, hours=2),
    }
    for message, (bad_start, bad_end) in cases.items():
        response = client.post(URL, json=body(court.id, bad_start, bad_end), headers=headers)
        assert response.status_code == 400, message
        assert response.json() == {"detail": message}


def test_inactive_resource_cannot_be_booked(client: TestClient, make_user, court, db) -> None:
    _, headers = make_user(UserRole.STUDENT)
    court.is_active = False
    db.commit()
    start, end = local_slot(2, 18)
    assert client.post(URL, json=body(court.id, start, end), headers=headers).status_code == 400


def test_missing_fields_return_422(client: TestClient, make_user) -> None:
    _, headers = make_user(UserRole.STUDENT)
    response = client.post(URL, json={}, headers=headers)
    assert response.status_code == 422
    assert "resourceId" in response.json()["detail"]
