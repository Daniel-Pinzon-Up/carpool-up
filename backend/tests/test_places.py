import pytest
from httpx import AsyncClient

from app.core.enums import UserStatus
from tests.conftest import API, UserFactory, auth

pytestmark = pytest.mark.integration

URL = f"{API}/admin/places"
CAMPUS = {"name": "Campus de prueba", "kind": "campus", "lat": 7.3870, "lon": -72.6495}


async def test_create_and_list_in_public_catalog(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    created = await api.post(URL, json=CAMPUS, headers=su_headers)
    assert created.status_code == 201
    body = created.json()
    assert (body["lat"], body["lon"]) == (7.387, -72.6495)

    catalog = await api.get(f"{API}/places", params={"kind": "campus"})
    assert body["id"] in [p["id"] for p in catalog.json()]


async def test_points_outside_pamplona_are_rejected(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    cucuta = {**CAMPUS, "name": "Cucuta", "lat": 7.8939, "lon": -72.5078}
    response = await api.post(URL, json=cucuta, headers=su_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "PLACE_OUT_OF_AREA"


async def test_service_area_is_configurable(api: AsyncClient, su_headers: dict[str, str]) -> None:
    wide = {"min_lat": 7.0, "max_lat": 8.0, "min_lon": -73.0, "max_lon": -72.0}
    await api.patch(f"{API}/admin/settings/service_area", json={"value": wide}, headers=su_headers)
    response = await api.post(
        URL, json={**CAMPUS, "name": "Cucuta", "lat": 7.8939, "lon": -72.5078}, headers=su_headers
    )
    assert response.status_code == 201


async def test_custom_kind_is_not_allowed_in_catalog(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    response = await api.post(URL, json={**CAMPUS, "kind": "custom"}, headers=su_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_duplicate_names_per_kind(api: AsyncClient, su_headers: dict[str, str]) -> None:
    await api.post(URL, json=CAMPUS, headers=su_headers)
    response = await api.post(URL, json=CAMPUS, headers=su_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "PLACE_NAME_TAKEN"


async def test_update_moves_point_inside_area_only(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    place = (await api.post(URL, json=CAMPUS, headers=su_headers)).json()
    moved = await api.patch(
        f"{URL}/{place['id']}", json={"lat": 7.3760, "name": "Campus movido"}, headers=su_headers
    )
    assert moved.status_code == 200
    assert moved.json()["lat"] == 7.376
    assert moved.json()["lon"] == -72.6495
    assert moved.json()["name"] == "Campus movido"

    outside = await api.patch(f"{URL}/{place['id']}", json={"lat": 8.5}, headers=su_headers)
    assert outside.status_code == 422


async def test_deactivated_places_leave_public_catalog(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    place = (await api.post(URL, json=CAMPUS, headers=su_headers)).json()
    assert (await api.delete(f"{URL}/{place['id']}", headers=su_headers)).status_code == 204

    public_ids = [p["id"] for p in (await api.get(f"{API}/places")).json()]
    assert place["id"] not in public_ids
    admin = (await api.get(URL, headers=su_headers)).json()
    assert next(p for p in admin if p["id"] == place["id"])["is_active"] is False

    audit = await api.get(
        f"{API}/admin/audit", params={"entity_id": place["id"]}, headers=su_headers
    )
    assert [i["action"] for i in audit.json()["items"]] == ["place.deactivate", "place.create"]


async def test_users_can_drop_custom_pins_that_stay_private(
    api: AsyncClient, make_user: UserFactory
) -> None:
    passenger = await make_user()
    pin = await api.post(
        f"{API}/places/custom",
        json={"name": "Mi casa", "lat": 7.3801, "lon": -72.6480},
        headers=auth(passenger),
    )
    assert pin.status_code == 201
    assert pin.json()["kind"] == "custom"
    public_ids = [p["id"] for p in (await api.get(f"{API}/places")).json()]
    assert pin.json()["id"] not in public_ids


async def test_custom_pins_need_an_active_account(api: AsyncClient, make_user: UserFactory) -> None:
    body = {"name": "Mi casa", "lat": 7.3801, "lon": -72.6480}
    anonymous = await api.post(f"{API}/places/custom", json=body)
    assert anonymous.status_code == 401
    pending = await make_user(status=UserStatus.PENDING_APPROVAL)
    response = await api.post(f"{API}/places/custom", json=body, headers=auth(pending))
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_NOT_ACTIVE"


async def test_admin_cannot_edit_custom_pins_through_catalog(
    api: AsyncClient, make_user: UserFactory, su_headers: dict[str, str]
) -> None:
    passenger = await make_user()
    pin = (
        await api.post(
            f"{API}/places/custom",
            json={"name": "Mi casa", "lat": 7.3801, "lon": -72.6480},
            headers=auth(passenger),
        )
    ).json()
    response = await api.patch(f"{URL}/{pin['id']}", json={"name": "x" * 5}, headers=su_headers)
    assert response.status_code == 404
