from datetime import date

import pytest
from httpx import AsyncClient

from app.modules.semesters import service as semester_service
from tests.conftest import API

pytestmark = pytest.mark.integration

URL = f"{API}/admin/semesters"


async def create(api: AsyncClient, headers: dict[str, str], **body: object) -> dict[str, object]:
    response = await api.post(URL, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_default_revalidation_deadline_is_start_plus_setting(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    semester = await create(
        api, su_headers, name="2030-1", starts_on="2030-02-01", ends_on="2030-06-30"
    )
    assert semester["revalidation_deadline"] == "2030-03-03"


async def test_explicit_deadline_must_be_inside_semester(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    response = await api.post(
        URL,
        json={
            "name": "2030-1",
            "starts_on": "2030-02-01",
            "ends_on": "2030-06-30",
            "revalidation_deadline": "2030-07-15",
        },
        headers=su_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SEMESTER_INVALID_DATES"


async def test_end_must_be_after_start(api: AsyncClient, su_headers: dict[str, str]) -> None:
    response = await api.post(
        URL,
        json={"name": "2030-1", "starts_on": "2030-06-30", "ends_on": "2030-02-01"},
        headers=su_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SEMESTER_INVALID_DATES"


async def test_semesters_cannot_overlap_but_can_be_adjacent(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    await create(api, su_headers, name="2030-1", starts_on="2030-02-01", ends_on="2030-06-30")
    overlap = await api.post(
        URL,
        json={"name": "2030-X", "starts_on": "2030-06-30", "ends_on": "2030-08-30"},
        headers=su_headers,
    )
    assert overlap.status_code == 409
    assert overlap.json() == {
        "code": "SEMESTER_OVERLAP",
        "message": "Semesters cannot overlap",
        "details": {"conflicts_with": "2030-1"},
    }
    await create(api, su_headers, name="2030-2", starts_on="2030-07-01", ends_on="2030-12-15")


async def test_names_are_unique(api: AsyncClient, su_headers: dict[str, str]) -> None:
    await create(api, su_headers, name="2030-1", starts_on="2030-02-01", ends_on="2030-06-30")
    response = await api.post(
        URL,
        json={"name": "2030-1", "starts_on": "2031-02-01", "ends_on": "2031-06-30"},
        headers=su_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "SEMESTER_NAME_TAKEN"


async def test_current_semester_uses_local_date(
    api: AsyncClient, su_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await create(api, su_headers, name="2030-2", starts_on="2030-08-01", ends_on="2030-12-15")

    monkeypatch.setattr(semester_service, "local_today", lambda: date(2030, 12, 15))
    current = await api.get(f"{API}/meta/semesters/current")
    assert current.status_code == 200
    assert current.json()["name"] == "2030-2"

    monkeypatch.setattr(semester_service, "local_today", lambda: date(2030, 12, 16))
    missing = await api.get(f"{API}/meta/semesters/current")
    assert missing.status_code == 404
    assert missing.json()["code"] == "NO_CURRENT_SEMESTER"


async def test_update_checks_overlap_and_audits(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    first = await create(
        api, su_headers, name="2030-1", starts_on="2030-02-01", ends_on="2030-06-30"
    )
    second = await create(
        api, su_headers, name="2030-2", starts_on="2030-08-01", ends_on="2030-12-15"
    )

    clash = await api.patch(
        f"{URL}/{second['id']}", json={"starts_on": "2030-06-15"}, headers=su_headers
    )
    assert clash.status_code == 409

    moved = await api.patch(
        f"{URL}/{first['id']}", json={"ends_on": "2030-07-20"}, headers=su_headers
    )
    assert moved.status_code == 200
    assert moved.json()["ends_on"] == "2030-07-20"

    audit = await api.get(
        f"{API}/admin/audit", params={"entity_id": first["id"]}, headers=su_headers
    )
    actions = [item["action"] for item in audit.json()["items"]]
    assert actions == ["semester.update", "semester.create"]
    assert audit.json()["items"][0]["before"]["ends_on"] == "2030-06-30"


async def test_delete(api: AsyncClient, su_headers: dict[str, str]) -> None:
    semester = await create(
        api, su_headers, name="2030-1", starts_on="2030-02-01", ends_on="2030-06-30"
    )
    response = await api.delete(f"{URL}/{semester['id']}", headers=su_headers)
    assert response.status_code == 204
    listing = await api.get(URL, headers=su_headers)
    assert all(s["id"] != semester["id"] for s in listing.json())
    missing = await api.delete(f"{URL}/{semester['id']}", headers=su_headers)
    assert missing.status_code == 404
