import pytest
from httpx import AsyncClient

from tests.conftest import API

pytestmark = pytest.mark.integration

URL = f"{API}/admin/legal"
BODY = "Texto de prueba de los terminos y condiciones con la longitud minima exigida."


async def publish(
    api: AsyncClient,
    headers: dict[str, str],
    version: str,
    language: str = "es",
    kind: str = "terms",
) -> dict[str, object]:
    response = await api.post(
        URL,
        json={"kind": kind, "version": version, "language": language, "body_markdown": BODY},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_new_version_replaces_current(api: AsyncClient, su_headers: dict[str, str]) -> None:
    first = await publish(api, su_headers, "1.0")
    second = await publish(api, su_headers, "1.1")

    current = await api.get(f"{API}/legal/current", params={"language": "es"})
    assert [d["id"] for d in current.json() if d["kind"] == "terms"] == [second["id"]]

    all_versions = {
        d["id"]: d["is_current"] for d in (await api.get(URL, headers=su_headers)).json()
    }
    assert all_versions[first["id"]] is False
    assert all_versions[second["id"]] is True


async def test_versions_are_immutable(api: AsyncClient, su_headers: dict[str, str]) -> None:
    await publish(api, su_headers, "1.0")
    response = await api.post(
        URL,
        json={"kind": "terms", "version": "1.0", "language": "es", "body_markdown": BODY},
        headers=su_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "LEGAL_VERSION_EXISTS"


async def test_falls_back_to_spanish(api: AsyncClient, su_headers: dict[str, str]) -> None:
    await publish(api, su_headers, "1.0", "es", "terms")
    await publish(api, su_headers, "1.0", "es", "data_policy")
    english = await publish(api, su_headers, "1.0", "en", "terms")

    docs = (await api.get(f"{API}/legal/current", params={"language": "en"})).json()
    by_kind = {d["kind"]: d for d in docs}
    assert by_kind["terms"]["id"] == english["id"]
    assert by_kind["data_policy"]["language"] == "es"


async def test_rejects_bad_versions_and_short_bodies(
    api: AsyncClient, su_headers: dict[str, str]
) -> None:
    for body in (
        {"kind": "terms", "version": "uno", "language": "es", "body_markdown": BODY},
        {"kind": "terms", "version": "1.0", "language": "es", "body_markdown": "corto"},
        {"kind": "terms", "version": "1.0", "language": "de", "body_markdown": BODY},
    ):
        assert (await api.post(URL, json=body, headers=su_headers)).status_code == 422


async def test_publication_is_audited(api: AsyncClient, su_headers: dict[str, str]) -> None:
    doc = await publish(api, su_headers, "2.0")
    audit = await api.get(f"{API}/admin/audit", params={"entity_id": doc["id"]}, headers=su_headers)
    entry = audit.json()["items"][0]
    assert entry["action"] == "legal.publish"
    assert entry["after"] == {"kind": "terms", "language": "es", "version": "2.0"}
