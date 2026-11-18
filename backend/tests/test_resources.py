from datetime import time

from fastapi.testclient import TestClient

from app.models.resource import Resource, SportType

URL = "/api/v1/resources"

TENNIS_COURT = {
    "name": "Teren tenis 1",
    "type": "teren",
    "sport": "tenis",
    "description": "Zgura, nocturna",
    "pricePerHour": 40,
    "openHour": "08:00",
    "closeHour": "22:00",
}


def create(client: TestClient, **overrides) -> dict:
    response = client.post(URL, json={**TENNIS_COURT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_create_returns_contract_fields_in_camel_case(client: TestClient) -> None:
    created = create(client)
    assert set(created) == {
        "id",
        "name",
        "type",
        "sport",
        "description",
        "pricePerHour",
        "openHour",
        "closeHour",
        "isActive",
    }
    assert created["pricePerHour"] == 40
    assert created["openHour"] == "08:00"


def test_only_name_and_sport_are_required(client: TestClient) -> None:
    response = client.post(URL, json={"name": "Bazin USV", "sport": "inot"})
    assert response.status_code == 201
    body = response.json()
    # tipul se deduce din sport, programul implicit e 08:00 - 22:00
    assert body["type"] == "bazin"
    assert body["pricePerHour"] == 0
    assert (body["openHour"], body["closeHour"]) == ("08:00", "22:00")
    assert body["isActive"] is True


def test_type_must_match_sport(client: TestClient) -> None:
    response = client.post(URL, json={**TENNIS_COURT, "type": "bazin"})
    assert response.status_code == 422
    assert "type" in response.json()["detail"]


def test_saved_like_the_database_schema(client: TestClient, db) -> None:
    created = create(client)
    create(client, name="Teren tenis 2", sport="Tenis")

    # sportul e o singura data in sport_types, programul e pe fiecare zi in resource_schedules
    assert db.query(SportType).count() == 1
    resource = db.get(Resource, created["id"])
    assert [s.day_of_week for s in resource.schedules] == list(range(7))
    assert {(s.open_time, s.close_time) for s in resource.schedules} == {(time(8, 0), time(22, 0))}


def test_get_by_id(client: TestClient) -> None:
    created = create(client)
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_list_and_filters(client: TestClient) -> None:
    create(client)
    create(client, name="Teren fotbal", sport="fotbal")
    create(client, name="Bazin USV", type="bazin", sport="inot")

    assert len(client.get(URL).json()) == 3
    assert [r["name"] for r in client.get(URL, params={"sport": "Tenis"}).json()] == [
        "Teren tenis 1"
    ]
    assert [r["name"] for r in client.get(URL, params={"type": "bazin"}).json()] == ["Bazin USV"]
    assert client.get(URL, params={"type": "sala"}).status_code == 422


def test_patch_changes_only_sent_fields(client: TestClient) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={"pricePerHour": 50})
    assert response.status_code == 200
    assert response.json() == {**created, "pricePerHour": 50}


def test_patch_checks_hours_against_saved_ones(client: TestClient) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={"openHour": "23:00"})
    assert response.status_code == 422
    assert response.json() == {"detail": "openHour must be before closeHour"}


def test_patch_hours_updates_every_day(client: TestClient, db) -> None:
    created = create(client)
    response = client.patch(f"{URL}/{created['id']}", json={"closeHour": "20:00"})
    assert response.json()["closeHour"] == "20:00"
    resource = db.get(Resource, created["id"])
    assert {s.close_time for s in resource.schedules} == {time(20, 0)}


def test_delete_deactivates_and_hides_from_list(client: TestClient) -> None:
    created = create(client)
    assert client.delete(f"{URL}/{created['id']}").status_code == 204

    assert client.get(URL).json() == []
    # rezervarile vechi trimit inca la resursa, asa ca detaliile raman
    assert client.get(f"{URL}/{created['id']}").json()["isActive"] is False


def test_missing_resource_returns_404_with_detail(client: TestClient) -> None:
    response = client.get(f"{URL}/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Resursa 999 nu exista"}
    assert client.patch(f"{URL}/999", json={"sport": "tenis"}).status_code == 404
    assert client.delete(f"{URL}/999").status_code == 404


def test_duplicate_name_returns_409(client: TestClient) -> None:
    create(client)
    response = client.post(URL, json=TENNIS_COURT)
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)


def test_validation_errors_are_a_single_detail_message(client: TestClient) -> None:
    response = client.post(
        URL, json={**TENNIS_COURT, "type": "sala", "pricePerHour": -1, "openHour": "8"}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "type" in detail and "pricePerHour" in detail and "openHour" in detail


def test_open_hour_must_be_before_close_hour(client: TestClient) -> None:
    response = client.post(URL, json={**TENNIS_COURT, "openHour": "22:00", "closeHour": "08:00"})
    assert response.status_code == 422
    assert response.json() == {"detail": "openHour must be before closeHour"}
