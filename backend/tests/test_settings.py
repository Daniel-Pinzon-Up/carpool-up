from typing import Any

import pytest
from httpx import AsyncClient

from app.modules.settings.definitions import DEFINITIONS
from tests.conftest import API

pytestmark = pytest.mark.integration


async def test_lists_every_setting_with_defaults(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    response = await api.get(f"{API}/admin/settings", headers=su_headers)
    assert response.status_code == 200
    by_key = {item["key"]: item for item in response.json()}
    assert set(by_key) == set(DEFINITIONS)
    assert by_key["cancel_free_hours"]["value"] == 2
    assert by_key["series_window_options_days"]["value"] == [15, 28, "semester"]
    assert by_key["cost_per_km_car"]["value"] is None


async def test_public_settings_need_no_login(api: AsyncClient) -> None:
    response = await api.get(f"{API}/meta/settings/public")
    assert response.status_code == 200
    assert response.json()["no_show_limit"] == 3


async def test_update_is_validated_persisted_and_audited(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    response = await api.patch(
        f"{API}/admin/settings/cancel_free_hours", json={"value": 3}, headers=su_headers
    )
    assert response.status_code == 200
    assert response.json()["value"] == 3
    assert response.json()["updated_by"] is not None

    public = await api.get(f"{API}/meta/settings/public")
    assert public.json()["cancel_free_hours"] == 3

    audit = await api.get(
        f"{API}/admin/audit", params={"entity": "system_setting"}, headers=su_headers
    )
    entry = audit.json()["items"][0]
    assert entry["action"] == "setting.update"
    assert entry["entity_id"] == "cancel_free_hours"
    assert entry["before"] == {"value": 2}
    assert entry["after"] == {"value": 3}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("cancel_free_hours", True),
        ("cancel_free_hours", -1),
        ("cancel_free_hours", "2"),
        ("no_show_limit", 0),
        ("search_radius_meters", 10),
        ("series_window_options_days", []),
        ("series_window_options_days", [15, "series"]),
        ("subscription_options_days", [8, "semester"]),
        ("max_price_per_seat", 2.5),
        ("service_area", {"min_lat": 7.5, "max_lat": 7.3, "min_lon": -72.7, "max_lon": -72.6}),
    ],
)
async def test_rejects_invalid_values(
    api: AsyncClient, su_headers: dict[str, str], key: str, value: Any
) -> None:
    response = await api.patch(
        f"{API}/admin/settings/{key}", json={"value": value}, headers=su_headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SETTING_INVALID"


async def test_optional_prices_accept_null_and_integers(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    for value in (4500, None, 0):
        response = await api.patch(
            f"{API}/admin/settings/max_price_per_seat", json={"value": value}, headers=su_headers
        )
        assert response.status_code == 200
        assert response.json()["value"] == value


async def test_unknown_setting(api: AsyncClient, su_headers: dict[str, str]) -> None:
    response = await api.patch(
        f"{API}/admin/settings/no_existe", json={"value": 1}, headers=su_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SETTING_UNKNOWN"
