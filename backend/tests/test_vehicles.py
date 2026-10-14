"""Vehiculos del conductor y requisitos para publicar."""

import io
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.enums import DocKind, ReviewStatus, UserRole, UserStatus
from app.modules.documents.models import Document
from app.modules.users.models import User
from tests.conftest import API, UserFactory, auth

pytestmark = pytest.mark.integration

CAR = {
    "type": "car",
    "plate": "abc-123",
    "brand": "Chevrolet",
    "model": "Spark",
    "color": "Gris",
    "year": 2018,
    "capacity": 5,
    "luggage_space": True,
}
MOTO = {
    **CAR,
    "type": "motorcycle",
    "plate": "XYZ 12d",
    "brand": "Yamaha",
    "model": "FZ",
    "capacity": 2,
}


async def create(api: AsyncClient, user: User, **overrides: Any) -> dict[str, Any]:
    response = await api.post(f"{API}/vehicles", json={**CAR, **overrides}, headers=auth(user))
    return {"status_code": response.status_code, **response.json()}


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (30, 20), "red").save(out, format="PNG")
    return out.getvalue()


async def approved_license(db: AsyncSession, user: User, days: int = 365) -> Document:
    license_ = Document(
        kind=DocKind.DRIVER_LICENSE,
        user_id=user.id,
        file_path="licenses/x.pdf",
        content_type="application/pdf",
        expires_on=local_today() + timedelta(days=days),
        status=ReviewStatus.APPROVED,
    )
    db.add(license_)
    await db.flush()
    return license_


async def test_create_normalizes_plate_and_lists_own(
    api: AsyncClient, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)
    car = await create(api, driver)
    assert car["status_code"] == 201
    assert car["plate"] == "ABC123" and car["has_photo"] is False
    moto = await create(api, driver, **MOTO)
    assert moto["plate"] == "XYZ12D"

    other = await make_user(UserRole.DRIVER)
    await create(api, other, plate="DEF456")
    own = (await api.get(f"{API}/vehicles", headers=auth(driver))).json()
    assert sorted(v["plate"] for v in own) == ["ABC123", "XYZ12D"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"plate": "AB1234"},
        {"plate": "ABC12D"},  # formato de moto en un carro
        {"type": "motorcycle", "plate": "ABC123", "capacity": 2},  # formato de carro en una moto
        {"capacity": 1},
        {"capacity": 9},
        {"type": "motorcycle", "plate": "ABC12D", "capacity": 3},
        {"year": 1970},
        {"year": local_today().year + 2},
        {"brand": "X"},
    ],
)
async def test_rejects_invalid_vehicles(
    api: AsyncClient, make_user: UserFactory, overrides: dict[str, Any]
) -> None:
    response = await create(api, await make_user(UserRole.DRIVER), **overrides)
    assert response["status_code"] == 422


async def test_plates_are_unique_among_live_vehicles(
    api: AsyncClient, make_user: UserFactory
) -> None:
    first = await make_user(UserRole.DRIVER)
    second = await make_user(UserRole.DRIVER)
    car = await create(api, first)
    duplicate = await create(api, second, plate="ABC 123")
    assert duplicate["status_code"] == 409 and duplicate["code"] == "VEHICLE_PLATE_TAKEN"

    assert (await api.delete(f"{API}/vehicles/{car['id']}", headers=auth(first))).status_code == 204
    again = await create(api, second, plate="ABC123")
    assert again["status_code"] == 201  # liberada tras el borrado logico


async def test_only_active_drivers_manage_vehicles(
    api: AsyncClient, make_user: UserFactory
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    assert (await create(api, passenger))["code"] == "VEHICLES_DRIVERS_ONLY"
    pending = await make_user(UserRole.DRIVER, UserStatus.PENDING_APPROVAL)
    assert (await create(api, pending))["code"] == "ACCOUNT_NOT_ACTIVE"


async def test_update_keeps_type_rules_and_ownership(
    api: AsyncClient, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)
    moto = await create(api, driver, **MOTO)
    bad = await api.patch(
        f"{API}/vehicles/{moto['id']}", json={"capacity": 4}, headers=auth(driver)
    )
    assert bad.status_code == 422 and bad.json()["details"]["rule"] == "capacity_motorcycle"

    ok = await api.patch(
        f"{API}/vehicles/{moto['id']}",
        json={"color": "Negro", "is_active": False},
        headers=auth(driver),
    )
    assert ok.json()["color"] == "Negro" and ok.json()["is_active"] is False

    intruder = await make_user(UserRole.DRIVER)
    for method in ("patch", "delete"):
        response = await api.request(
            method.upper(),
            f"{API}/vehicles/{moto['id']}",
            json={"color": "Rojo"},
            headers=auth(intruder),
        )
        assert response.status_code == 404


async def test_photos_are_images_and_visible_to_signed_in_users(
    api: AsyncClient, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)
    car = await create(api, driver)
    pdf = await api.put(
        f"{API}/vehicles/{car['id']}/photo",
        files={"photo": ("foto.pdf", b"%PDF-1.7\n", "application/pdf")},
        headers=auth(driver),
    )
    assert pdf.status_code == 415

    uploaded = await api.put(
        f"{API}/vehicles/{car['id']}/photo",
        files={"photo": ("foto.png", png(), "image/png")},
        headers=auth(driver),
    )
    assert uploaded.json()["has_photo"] is True

    viewer = await make_user(UserRole.PASSENGER)
    photo = await api.get(f"{API}/vehicles/{car['id']}/photo", headers=auth(viewer))
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/png"
    assert (await api.get(f"{API}/vehicles/{car['id']}/photo")).status_code == 401


async def test_publishing_requirements(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)

    async def blockers() -> list[str]:
        me = (await api.get(f"{API}/users/me", headers=auth(driver))).json()
        assert me["can_publish"] is (me["publish_blockers"] == [])
        return list(me["publish_blockers"])

    assert await blockers() == ["license_missing", "no_active_vehicle"]
    license_ = await approved_license(db, driver)
    assert await blockers() == ["no_active_vehicle"]

    car = await create(api, driver)
    assert await blockers() == []

    await api.patch(f"{API}/vehicles/{car['id']}", json={"is_active": False}, headers=auth(driver))
    assert await blockers() == ["no_active_vehicle"]
    await api.patch(f"{API}/vehicles/{car['id']}", json={"is_active": True}, headers=auth(driver))

    license_.expires_on = local_today() - timedelta(days=1)
    await db.flush()
    assert await blockers() == ["license_expired"]
    license_.status = ReviewStatus.PENDING
    await db.flush()
    assert await blockers() == ["license_pending"]

    passenger = await make_user(UserRole.PASSENGER)
    me = (await api.get(f"{API}/users/me", headers=auth(passenger))).json()
    assert me["can_publish"] is False and me["publish_blockers"] == []
