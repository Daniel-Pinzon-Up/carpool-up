"""Busqueda geografica: radio, sentido de la ruta, ventana horaria, cupo, reglas y privacidad."""

from datetime import datetime, time, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, local_today
from app.core.enums import Sex, UserRole
from app.modules.places.models import Place
from app.modules.search.service import Point, walk_m
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth, make_driver
from tests.test_trips import publish, trip_body

pytestmark = pytest.mark.integration

TOMORROW = local_today() + timedelta(days=1)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TOMORROW, time(hour, minute), tzinfo=LOCAL_TZ)


def params(
    origin: Place | dict[str, float], destination: Place | dict[str, float], **extra: Any
) -> dict[str, Any]:
    query: dict[str, Any] = {"date": TOMORROW.isoformat(), "time": "07:00", **extra}
    for prefix, point in (("origin", origin), ("destination", destination)):
        if isinstance(point, Place):
            query[f"{prefix}_place_id"] = str(point.id)
        else:
            query[f"{prefix}_lat"], query[f"{prefix}_lon"] = point["lat"], point["lon"]
    return query


async def search(api: AsyncClient, user: User, query: dict[str, Any]) -> httpx.Response:
    return await api.get(f"{API}/search/trips", params=query, headers=auth(user))


@pytest.fixture
async def trip(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place]
) -> dict[str, Any]:
    """Campus -> Casona -> Terminal, manana a las 7:00, 3 puestos."""
    user, vehicle = driver
    response = await publish(
        routing_api, user, trip_body(places, vehicle, departs_at=at(7).isoformat())
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def passenger(make_user: UserFactory) -> User:
    return await make_user(UserRole.PASSENGER, sex=Sex.MALE)


def test_walk_distance() -> None:
    campus, terminal = Point(7.3870, -72.6495), Point(7.3712, -72.6512)
    assert 1700 < walk_m(campus, terminal) < 1800


async def test_finds_trip_with_pickup_and_dropoff_at_stops(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    response = await search(routing_api, passenger, params(places[0], places[2]))
    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["trip_id"] == trip["id"]
    assert result["pickup"]["kind"] == "stop"
    assert result["pickup"]["name"] == "Ciudad Universitaria"
    assert result["pickup"]["walk_m"] == 0
    assert result["dropoff"]["name"] == "Terminal"
    departs = datetime.fromisoformat(result["departs_at"])
    assert datetime.fromisoformat(result["pickup"]["eta"]) == departs
    assert datetime.fromisoformat(result["dropoff"]["eta"]) == departs + timedelta(seconds=600)
    assert result["seats_available"] == 3
    assert result["minutes_from_requested"] == 0
    assert result["rules"] == [{"kind": "pets", "value": "not_allowed"}]


async def test_no_private_data_in_results(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
    driver: tuple[User, Vehicle],
) -> None:
    """Aceptacion del paso 7: sin placa ni datos privados."""
    response = await search(routing_api, passenger, params(places[0], places[2]))
    body = response.text
    user, vehicle = driver
    assert vehicle.plate not in body
    assert user.email not in body
    result = response.json()[0]
    assert set(result["driver"]) == {"id", "full_name", "rating", "trips_as_driver"}
    assert "plate" not in result["vehicle"]


async def test_direction_matters(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    response = await search(routing_api, passenger, params(places[2], places[0]))
    assert response.json() == []


async def test_pickup_between_stops_uses_the_route(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    # Punto medio entre el campus y la Casona: a mas de 500 m de ambas paradas.
    middle = {"lat": (7.3870 + 7.3762) / 2, "lon": (-72.6495 + -72.6468) / 2}
    [result] = (await search(routing_api, passenger, params(middle, places[2]))).json()
    assert result["pickup"]["kind"] == "route"
    assert result["pickup"]["name"] is None
    assert result["pickup"]["walk_m"] < 5
    departs = datetime.fromisoformat(result["departs_at"])
    eta = datetime.fromisoformat(result["pickup"]["eta"])
    assert departs < eta < departs + timedelta(seconds=300)


async def test_points_far_from_the_route_do_not_match(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    far = {"lat": 7.4000, "lon": -72.6200}
    assert (await search(routing_api, passenger, params(far, places[2]))).json() == []


async def test_time_window_and_seats(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    near = await search(routing_api, passenger, params(places[0], places[2], time="07:40"))
    assert near.json()[0]["minutes_from_requested"] == -40
    later = await search(routing_api, passenger, params(places[0], places[2], time="09:00"))
    assert later.json() == []
    too_many = await search(routing_api, passenger, params(places[0], places[2], seats=4))
    assert too_many.json() == []


async def test_rules_must_match_preferences(
    routing_api: AsyncClient,
    trip: dict[str, Any],
    places: list[Place],
    passenger: User,
) -> None:
    query = params(places[0], places[2])
    assert len((await search(routing_api, passenger, {**query, "pets": True})).json()) == 0
    assert (
        len(
            (await search(routing_api, passenger, {**query, "luggage": True, "music": True})).json()
        )
        == 1
    )
    assert len((await search(routing_api, passenger, {**query, "no_smoking": True})).json()) == 1


async def test_women_only_trips_are_only_offered_to_women(
    routing_api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    places: list[Place],
    driver: tuple[User, Vehicle],
) -> None:
    woman_driver, car = driver
    rules = [{"kind": "women_only", "value": "allowed"}]
    body = trip_body(places, car, rules=rules, departs_at=at(7).isoformat())
    assert (await publish(routing_api, woman_driver, body)).status_code == 201
    man_driver, his_car = await make_driver(db, make_user, sex=Sex.MALE, plate="DEF456")
    assert (
        await publish(
            routing_api,
            man_driver,
            trip_body(places, his_car, rules=[], departs_at=at(7, 10).isoformat()),
        )
    ).status_code == 201

    query = params(places[0], places[2])
    man = await make_user(UserRole.PASSENGER, sex=Sex.MALE)
    woman = await make_user(UserRole.PASSENGER, sex=Sex.FEMALE)
    assert len((await search(routing_api, man, query)).json()) == 1
    assert len((await search(routing_api, woman, query)).json()) == 2
    only = (await search(routing_api, woman, {**query, "women_only": True})).json()
    assert [r["driver"]["id"] for r in only] == [str(woman_driver.id)]


async def test_order_by_pickup_distance_then_time(
    routing_api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    places: list[Place],
    driver: tuple[User, Vehicle],
) -> None:
    user, car = driver
    later = trip_body(
        places,
        car,
        place_ids=[str(places[1].id), str(places[2].id)],
        rules=[],
        departs_at=at(7, 20).isoformat(),
    )
    other, other_car = await make_driver(db, make_user, plate="DEF456")
    first = (await publish(routing_api, user, later)).json()
    second = (
        await publish(
            routing_api,
            other,
            trip_body(places, other_car, rules=[], departs_at=at(6, 50).isoformat()),
        )
    ).json()

    passenger = await make_user(UserRole.PASSENGER)
    # Ambos pasan por la Casona: gana el de menor diferencia horaria con las 7:10 (7:20).
    results = (
        await search(routing_api, passenger, params(places[1], places[2], time="07:10"))
    ).json()
    assert [r["trip_id"] for r in results] == [first["id"], second["id"]]
    # Desde el campus solo pasa el segundo.
    from_campus = (
        await search(routing_api, passenger, params(places[0], places[2], time="07:10"))
    ).json()
    assert [r["trip_id"] for r in from_campus] == [second["id"]]


async def test_excludes_own_cancelled_and_past_trips(
    routing_api: AsyncClient,
    db: AsyncSession,
    trip: dict[str, Any],
    places: list[Place],
    driver: tuple[User, Vehicle],
    passenger: User,
) -> None:
    user, _ = driver
    query = params(places[0], places[2])
    assert (await search(routing_api, user, query)).json() == []  # el propio conductor
    row = await db.get(Trip, trip["id"])
    assert row is not None
    row.departs_at = datetime.now(LOCAL_TZ) - timedelta(minutes=5)
    await db.flush()
    past = params(
        places[0],
        places[2],
        date=local_today().isoformat(),
        time=datetime.now(LOCAL_TZ).strftime("%H:%M"),
    )
    assert (await search(routing_api, passenger, past)).json() == []
    row.departs_at = at(7)
    await db.flush()
    await routing_api.post(
        f"{API}/trips/{trip['id']}/cancel", json={"reason": "Ya no voy"}, headers=auth(user)
    )
    assert (await search(routing_api, passenger, query)).json() == []


async def test_search_validation(
    routing_api: AsyncClient,
    places: list[Place],
    passenger: User,
) -> None:
    missing = {"date": TOMORROW.isoformat(), "time": "07:00", "origin_place_id": str(places[0].id)}
    assert (await search(routing_api, passenger, missing)).json()["code"] == "VALIDATION_ERROR"
    both = {**params(places[0], places[2]), "origin_lat": 7.38, "origin_lon": -72.64}
    assert (await search(routing_api, passenger, both)).json()["code"] == "VALIDATION_ERROR"
    outside = params({"lat": 4.71, "lon": -74.07}, places[2])
    assert (await search(routing_api, passenger, outside)).json()["code"] == "PLACE_OUT_OF_AREA"
    yesterday = params(places[0], places[2], date=(local_today() - timedelta(days=1)).isoformat())
    assert (await search(routing_api, passenger, yesterday)).json()["code"] == "SEARCH_IN_PAST"
