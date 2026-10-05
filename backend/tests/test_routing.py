"""Vista previa de ruta: puntos, area de servicio, ETA con factor de trafico y precio."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.enums import PlaceKind, UserRole
from app.core.geo import point
from app.main import create_app
from app.modules.auth.router import get_email_queue
from app.modules.places.models import Place
from app.modules.routing.models import TrafficFactor
from app.modules.routing.osrm import Leg, OsrmClient, RouteResult, cache_key
from app.modules.routing.router import get_route_provider
from app.modules.routing.service import estimate_price, round_to_hundred, weekday_group
from app.modules.users.models import User
from tests.conftest import API, Outbox, UserFactory, auth

ORIGIN = {"lat": 7.3870, "lon": -72.6495}
STOP = {"lat": 7.3790, "lon": -72.6440}
DESTINATION = {"lat": 7.3712, "lon": -72.6512}


class FakeProvider:
    """OSRM en memoria: cada tramo mide 2 km y dura 300 s."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[float, float]]] = []

    async def route(self, points: list[tuple[float, float]]) -> RouteResult:
        self.calls.append(points)
        legs = [Leg(2000.0, 300.0) for _ in points[1:]]
        return RouteResult(
            coordinates=[[lon, lat] for lat, lon in points],
            distance_m=sum(leg.distance_m for leg in legs),
            duration_s=sum(leg.duration_s for leg in legs),
            legs=legs,
        )


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
async def routing_api(
    db: AsyncSession, outbox: Outbox, provider: FakeProvider
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_email_queue] = lambda: outbox
    app.dependency_overrides[get_route_provider] = lambda: provider
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def preview(api: AsyncClient, user: User, **body: Any) -> httpx.Response:
    payload = {"points": [ORIGIN, DESTINATION], **body}
    return await api.post(f"{API}/routing/preview", json=payload, headers=auth(user))


# --- Unidades -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"), [(1249, 1200), (1250, 1300), (1251, 1300), (49, 0), (0, 0)]
)
def test_round_to_hundred(value: float, expected: int) -> None:
    assert round_to_hundred(value) == expected


def test_price_formula_and_cap() -> None:
    # 6 km * 600 COP / (3 puestos + 1) = 900
    assert estimate_price(6000, 600, 3, None) == 900
    assert estimate_price(6000, 600, 3, 800) == 800
    assert estimate_price(6000, 600, 3, 0) == 0


def test_weekday_groups_use_pamplona_time() -> None:
    # Sabado 00:30 en Pamplona es sabado 05:30 UTC; viernes 23:30 en Pamplona es sabado 04:30 UTC.
    assert weekday_group(datetime(2030, 3, 9, 5, 30, tzinfo=UTC)) == "saturday"
    assert weekday_group(datetime(2030, 3, 9, 4, 30, tzinfo=UTC)) == "weekday"
    assert weekday_group(datetime(2030, 3, 10, 18, 0, tzinfo=UTC)) == "sunday"


def test_cache_key_ignores_insignificant_decimals() -> None:
    assert cache_key([(7.123451, -72.1)]) == cache_key([(7.1234512, -72.1)])
    assert cache_key([(7.1, -72.1), (7.2, -72.2)]) != cache_key([(7.2, -72.2), (7.1, -72.1)])


# --- Endpoint -------------------------------------------------------------------------


@pytest.mark.integration
async def test_preview_returns_route_and_stop_etas(
    routing_api: AsyncClient, make_user: UserFactory, provider: FakeProvider
) -> None:
    driver = await make_user(UserRole.DRIVER)
    departs = "2030-03-04T12:00:00Z"  # lunes 7:00 en Pamplona
    response = await routing_api.post(
        f"{API}/routing/preview",
        json={"points": [ORIGIN, STOP, DESTINATION], "departs_at": departs},
        headers=auth(driver),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["distance_m"] == 4000
    assert body["duration_s"] == 600 and body["traffic_factor"] == 1.0
    assert [p["eta_offset_s"] for p in body["points"]] == [0, 300, 600]
    assert body["points"][2]["eta"].startswith("2030-03-04T12:10:00")
    assert body["geometry"][0] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert provider.calls == [
        [
            (ORIGIN["lat"], ORIGIN["lon"]),
            (STOP["lat"], STOP["lon"]),
            (DESTINATION["lat"], DESTINATION["lon"]),
        ]
    ]


@pytest.mark.integration
async def test_traffic_factor_of_the_departure_slot(
    routing_api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    db.add(TrafficFactor(weekday_group="weekday", hour=7, factor=1.5, samples=10))
    await db.flush()
    driver = await make_user(UserRole.DRIVER)
    rush = await preview(routing_api, driver, departs_at="2030-03-04T12:15:00Z")  # 7:15 local
    calm = await preview(routing_api, driver, departs_at="2030-03-04T15:00:00Z")  # 10:00 local
    assert rush.json()["traffic_factor"] == 1.5 and rush.json()["duration_s"] == 450
    assert calm.json()["traffic_factor"] == 1.0 and calm.json()["duration_s"] == 300


@pytest.mark.integration
async def test_price_suggestion_needs_configuration(
    routing_api: AsyncClient, make_user: UserFactory, su_headers: dict[str, str]
) -> None:
    driver = await make_user(UserRole.DRIVER)
    unconfigured = (await preview(routing_api, driver, vehicle_type="car", seats=3)).json()
    assert unconfigured["pricing_configured"] is False and unconfigured["suggested_price"] is None

    await routing_api.patch(
        f"{API}/admin/settings/cost_per_km_car", json={"value": 600}, headers=su_headers
    )
    await routing_api.patch(
        f"{API}/admin/settings/max_price_per_seat", json={"value": 500}, headers=su_headers
    )
    priced = (await preview(routing_api, driver, vehicle_type="car", seats=3)).json()
    # 2 km * 600 / 4 = 300, por debajo del tope
    assert priced["pricing_configured"] is True
    assert priced["suggested_price"] == 300 and priced["max_price_per_seat"] == 500

    one_seat = (await preview(routing_api, driver, vehicle_type="car", seats=1)).json()
    assert one_seat["suggested_price"] == 500  # 600 sin tope, limitado a 500


@pytest.mark.integration
async def test_points_from_catalog_and_own_pins_only(
    routing_api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)
    other = await make_user(UserRole.DRIVER)
    campus = Place(name="Campus", kind=PlaceKind.CAMPUS, point=point(7.387, -72.6495))
    foreign_pin = Place(
        name="Casa ajena", kind=PlaceKind.CUSTOM, point=point(7.38, -72.65), created_by=other.id
    )
    own_pin = Place(
        name="Mi casa", kind=PlaceKind.CUSTOM, point=point(7.375, -72.645), created_by=driver.id
    )
    db.add_all([campus, foreign_pin, own_pin])
    await db.flush()

    ok = await preview(
        routing_api, driver, points=[{"place_id": str(campus.id)}, {"place_id": str(own_pin.id)}]
    )
    assert ok.status_code == 200
    assert [p["name"] for p in ok.json()["points"]] == ["Campus", "Mi casa"]

    hidden = await preview(
        routing_api,
        driver,
        points=[{"place_id": str(campus.id)}, {"place_id": str(foreign_pin.id)}],
    )
    assert hidden.status_code == 404 and hidden.json()["code"] == "PLACE_NOT_FOUND"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("points", "code"),
    [
        ([ORIGIN, {"lat": 7.89, "lon": -72.50}], "PLACE_OUT_OF_AREA"),
        ([ORIGIN], "VALIDATION_ERROR"),
        ([ORIGIN, {"lat": 7.38}], "VALIDATION_ERROR"),
        (
            [
                ORIGIN,
                {"place_id": "00000000-0000-0000-0000-000000000000", "lat": 7.38, "lon": -72.64},
            ],
            "VALIDATION_ERROR",
        ),
        ([ORIGIN, *[STOP] * 6, DESTINATION], "TOO_MANY_STOPS"),
    ],
)
async def test_invalid_points(
    routing_api: AsyncClient, make_user: UserFactory, points: list[dict[str, Any]], code: str
) -> None:
    response = await preview(routing_api, await make_user(UserRole.DRIVER), points=points)
    assert response.json()["code"] == code


@pytest.mark.integration
async def test_preview_requires_active_account(routing_api: AsyncClient) -> None:
    response = await routing_api.post(
        f"{API}/routing/preview", json={"points": [ORIGIN, DESTINATION]}
    )
    assert response.status_code == 401


# --- Cliente OSRM ---------------------------------------------------------------------


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value


OSRM_OK = {
    "code": "Ok",
    "routes": [
        {
            "geometry": {"coordinates": [[-72.6495, 7.387], [-72.6512, 7.3712]]},
            "distance": 2345.6,
            "duration": 321.9,
            "legs": [{"distance": 2345.6, "duration": 321.9}],
        }
    ],
}


async def test_osrm_client_parses_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=OSRM_OK)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    client = OsrmClient(MemoryRedis(), "http://osrm:5000")  # type: ignore[arg-type]
    points = [(7.387, -72.6495), (7.3712, -72.6512)]
    first = await client.route(points)
    second = await client.route(points)
    assert first == second
    assert first.distance_m == 2345.6 and first.legs[0].duration_s == 321.9
    assert len(requests) == 1  # la segunda vez sale de la cache
    assert "-72.649500,7.387000;-72.651200,7.371200" in str(requests[0].url)


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(400, json={"code": "NoRoute"}), "ROUTE_NOT_FOUND"),
        (httpx.Response(500, json={"code": "InternalError"}), "ROUTING_UNAVAILABLE"),
        (httpx.Response(502, text="bad gateway"), "ROUTING_UNAVAILABLE"),
    ],
)
async def test_osrm_client_errors(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, code: str
) -> None:
    from app.core.errors import AppError

    transport = httpx.MockTransport(lambda request: response)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: original(transport=transport))
    client = OsrmClient(MemoryRedis(), "http://osrm:5000")  # type: ignore[arg-type]
    with pytest.raises(AppError) as error:
        await client.route([(7.38, -72.64), (7.37, -72.65)])
    assert error.value.code == code


async def test_osrm_down_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.errors import AppError

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: original(transport=httpx.MockTransport(boom))
    )
    with pytest.raises(AppError) as error:
        await OsrmClient(MemoryRedis(), "http://osrm:5000").route([(7.38, -72.64), (7.37, -72.65)])  # type: ignore[arg-type]
    assert error.value.code == "ROUTING_UNAVAILABLE" and error.value.status_code == 503
