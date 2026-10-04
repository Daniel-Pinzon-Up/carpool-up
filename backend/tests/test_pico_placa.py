from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VehicleType
from app.modules.pico_placa.models import PicoPlacaRule
from app.modules.pico_placa.service import PicoPlacaService, last_digit
from tests.conftest import API

URL = f"{API}/admin/pico-placa"
MONDAY = date(2030, 3, 4)


@pytest.mark.parametrize(
    ("plate", "digit"),
    [("ABC123", 3), ("abc120", 0), ("ABC12D", 2), (" XYZ45E ", 5), ("SINNUM", None), ("", None)],
)
def test_last_numeric_digit(plate: str, digit: int | None) -> None:
    assert last_digit(plate) == digit


async def add_rule(db: AsyncSession, **overrides: object) -> PicoPlacaRule:
    values: dict[str, object] = {
        "vehicle_type": VehicleType.CAR,
        "weekday": 0,
        "restricted_digits": [0, 1],
        "valid_from": date(2030, 1, 1),
        "valid_to": None,
        "is_active": True,
    }
    values.update(overrides)
    rule = PicoPlacaRule(**values)
    db.add(rule)
    await db.flush()
    return rule


@pytest.mark.integration
async def test_is_restricted_matches_weekday_digit_and_type(db: AsyncSession) -> None:
    await add_rule(db)
    service = PicoPlacaService(db)
    assert await service.is_restricted(VehicleType.CAR, "ABC121", MONDAY)
    assert not await service.is_restricted(VehicleType.CAR, "ABC122", MONDAY)
    assert not await service.is_restricted(VehicleType.CAR, "ABC121", date(2030, 3, 5))
    assert not await service.is_restricted(VehicleType.MOTORCYCLE, "ABC21D", MONDAY)


@pytest.mark.integration
async def test_motorcycle_plates_use_last_numeric_digit(db: AsyncSession) -> None:
    await add_rule(db, vehicle_type=VehicleType.MOTORCYCLE)
    assert await PicoPlacaService(db).is_restricted(VehicleType.MOTORCYCLE, "XYZ01A", MONDAY)


@pytest.mark.integration
async def test_validity_window_and_inactive_rules(db: AsyncSession) -> None:
    await add_rule(db, valid_from=date(2030, 3, 10))
    await add_rule(db, weekday=1, valid_to=date(2030, 3, 1))
    await add_rule(db, weekday=2, is_active=False)
    service = PicoPlacaService(db)
    assert not await service.is_restricted(VehicleType.CAR, "ABC121", MONDAY)
    assert await service.is_restricted(VehicleType.CAR, "ABC121", date(2030, 3, 11))
    assert not await service.is_restricted(VehicleType.CAR, "ABC121", date(2030, 3, 5))
    assert not await service.is_restricted(VehicleType.CAR, "ABC121", date(2030, 3, 6))


@pytest.mark.integration
async def test_restricted_dates_over_a_range(db: AsyncSession) -> None:
    await add_rule(db, weekday=0, restricted_digits=[1])
    await add_rule(db, weekday=3, restricted_digits=[1, 2])
    dates = await PicoPlacaService(db).restricted_dates(
        VehicleType.CAR, "ABC111", date(2030, 3, 4), date(2030, 3, 17)
    )
    assert dates == {date(2030, 3, 4), date(2030, 3, 7), date(2030, 3, 11), date(2030, 3, 14)}


@pytest.mark.integration
async def test_crud_normalizes_digits_and_audits(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    created = await api.post(
        URL,
        json={
            "vehicle_type": "car",
            "weekday": 4,
            "restricted_digits": [9, 8],
            "valid_from": "2030-01-01",
        },
        headers=su_headers,
    )
    assert created.status_code == 201
    rule = created.json()
    assert rule["restricted_digits"] == [8, 9]

    updated = await api.patch(
        f"{URL}/{rule['id']}",
        json={"valid_to": "2030-06-30", "is_active": False},
        headers=su_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["valid_to"] == "2030-06-30"
    assert updated.json()["is_active"] is False

    reopened = await api.patch(f"{URL}/{rule['id']}", json={"valid_to": None}, headers=su_headers)
    assert reopened.json()["valid_to"] is None

    assert (await api.delete(f"{URL}/{rule['id']}", headers=su_headers)).status_code == 204
    audit = await api.get(
        f"{API}/admin/audit", params={"entity_id": rule["id"]}, headers=su_headers
    )
    assert [i["action"] for i in audit.json()["items"]] == [
        "pico_placa.delete",
        "pico_placa.update",
        "pico_placa.update",
        "pico_placa.create",
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    "body",
    [
        {"weekday": 7},
        {"restricted_digits": [10]},
        {"restricted_digits": [1, 1]},
        {"restricted_digits": []},
        {"valid_to": "2029-12-31"},
    ],
)
async def test_rejects_invalid_rules(
    api: AsyncClient, su_headers: dict[str, str], body: dict[str, object]
) -> None:
    base = {
        "vehicle_type": "car",
        "weekday": 0,
        "restricted_digits": [1],
        "valid_from": "2030-01-01",
    }
    response = await api.post(URL, json={**base, **body}, headers=su_headers)
    assert response.status_code == 422


@pytest.mark.integration
async def test_update_cannot_invert_validity(api: AsyncClient, su_headers: dict[str, str]) -> None:
    rule = (
        await api.post(
            URL,
            json={
                "vehicle_type": "car",
                "weekday": 0,
                "restricted_digits": [1],
                "valid_from": "2030-01-01",
            },
            headers=su_headers,
        )
    ).json()
    response = await api.patch(
        f"{URL}/{rule['id']}", json={"valid_to": "2029-01-01"}, headers=su_headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PICO_PLACA_INVALID_DATES"
