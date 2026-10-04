import pytest
from fastapi import APIRouter, Request
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.errors import AppError
from app.main import create_app
from tests.conftest import API


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get(f"{API}/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_security_headers(client: AsyncClient) -> None:
    response = await client.get(f"{API}/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Request-ID"]


async def test_not_found_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get(f"{API}/no-existe")
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Not Found", "details": {}}


async def test_openapi_is_published(client: AsyncClient) -> None:
    response = await client.get(f"{API}/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/health/ready" in response.json()["paths"]


class Payload(BaseModel):
    seats: int


def _app_with_probe_routes() -> AsyncClient:
    app = create_app()
    probe = APIRouter()

    @probe.post("/probe/validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    @probe.get("/probe/app-error")
    async def app_error() -> None:
        raise AppError("TRIP_FULL", "No seats left", 409, {"available": 0})

    @probe.get("/probe/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    app.include_router(probe)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_validation_error_envelope() -> None:
    async with _app_with_probe_routes() as ac:
        response = await ac.post("/probe/validate", json={"seats": "muchos"})
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]["fields"][0]["loc"] == ["body", "seats"]


async def test_app_error_envelope() -> None:
    async with _app_with_probe_routes() as ac:
        response = await ac.get("/probe/app-error")
    assert response.status_code == 409
    assert response.json() == {
        "code": "TRIP_FULL",
        "message": "No seats left",
        "details": {"available": 0},
    }


async def test_unhandled_error_hides_internals() -> None:
    async with _app_with_probe_routes() as ac:
        response = await ac.get("/probe/crash")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "boom" not in response.text


async def test_rate_limit_returns_error_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.rate_limit import limiter

    monkeypatch.setattr(limiter, "_default_limits", [])
    limiter.reset()
    app = create_app()

    @app.get("/probe/limited")
    @limiter.limit("2/minute")
    async def limited(request: Request) -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        codes = [(await ac.get("/probe/limited")).status_code for _ in range(3)]
        last = await ac.get("/probe/limited")
    assert codes == [200, 200, 429]
    assert last.json()["code"] == "RATE_LIMITED"


@pytest.mark.integration
async def test_readiness_with_real_services(client: AsyncClient) -> None:
    response = await client.get(f"{API}/health/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"
    assert body["checks"]["postgis"]
