"""Viajes y series: validaciones, ocurrencias, pico y placa, edicion, cancelacion y duplicado."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, local_today
from app.core.enums import PlaceKind, ReviewStatus, Sex, UserRole, VehicleType
from app.core.geo import point
from app.modules.documents.models import DriverLicense
from app.modules.notifications.models import Notification
from app.modules.pico_placa.models import PicoPlacaRule
from app.modules.places.models import Place
from app.modules.semesters.models import Semester
from app.modules.series.service import finish_past_series, series_days, window_end
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth

pytestmark = pytest.mark.integration


# --- Datos ----------------------------------------------------------------------------


@pytest.fixture
async def places(db: AsyncSession) -> list[Place]:
    rows = [
        Place(name="Ciudad Universitaria", kind=PlaceKind.CAMPUS, point=point(7.3870, -72.6495)),
        Place(name="Sede Casona", kind=PlaceKind.CAMPUS, point=point(7.3762, -72.6468)),
        Place(name="Terminal", kind=PlaceKind.LANDMARK, point=point(7.3712, -72.6512)),
    ]
    db.add_all(rows)
    await db.flush()
    return rows


@pytest.fixture
async def semester(db: AsyncSession) -> Semester:
    today = local_today()
    row = Semester(
        name="2026-T",
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=90),
        revalidation_deadline=today,
    )
    db.add(row)
    await db.flush()
    return row


async def make_driver(
    db: AsyncSession, make_user: UserFactory, sex: Sex = Sex.FEMALE, plate: str = "ABC123"
) -> tuple[User, Vehicle]:
    user = await make_user(UserRole.DRIVER, sex=sex)
    db.add(
        DriverLicense(
            user_id=user.id,
            file_path="licenses/x.pdf",
            content_type="application/pdf",
            expires_on=local_today() + timedelta(days=365),
            status=ReviewStatus.APPROVED,
        )
    )
    vehicle = Vehicle(
        owner_id=user.id,
        type=VehicleType.CAR,
        plate=plate,
        brand="Chevrolet",
        model="Spark",
        color="Gris",
        year=2018,
        capacity=5,
    )
    db.add(vehicle)
    await db.flush()
    return user, vehicle


@pytest.fixture
async def driver(db: AsyncSession, make_user: UserFactory) -> tuple[User, Vehicle]:
    return await make_driver(db, make_user)


async def pico_placa(db: AsyncSession, weekday: int, digits: list[int]) -> PicoPlacaRule:
    rule = PicoPlacaRule(
        vehicle_type=VehicleType.CAR,
        weekday=weekday,
        restricted_digits=digits,
        valid_from=local_today() - timedelta(days=1),
    )
    db.add(rule)
    await db.flush()
    return rule


def tomorrow_at(hour: int = 7, days: int = 1) -> datetime:
    day = local_today() + timedelta(days=days)
    return datetime.combine(day, time(hour, 0), tzinfo=LOCAL_TZ)


def next_monday() -> date:
    today = local_today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def trip_body(places: list[Place], vehicle: Vehicle, **overrides: Any) -> dict[str, Any]:
    return {
        "place_ids": [str(places[0].id), str(places[1].id), str(places[2].id)],
        "departs_at": tomorrow_at().isoformat(),
        "vehicle_id": str(vehicle.id),
        "seats": 3,
        "price_per_seat": 2000,
        "rules": [{"kind": "pets", "value": "not_allowed"}],
        **overrides,
    }


def series_body(places: list[Place], vehicle: Vehicle, **overrides: Any) -> dict[str, Any]:
    return {
        "place_ids": [str(places[0].id), str(places[2].id)],
        "weekdays": [0, 2, 4],
        "departure_time": "07:00",
        "start_date": next_monday().isoformat(),
        "window": 28,
        "vehicle_id": str(vehicle.id),
        "seats": 4,
        "price_per_seat": 1500,
        "rules": [],
        **overrides,
    }


async def publish(api: AsyncClient, user: User, body: dict[str, Any]) -> httpx.Response:
    return await api.post(f"{API}/trips", json=body, headers=auth(user))


async def publish_series(api: AsyncClient, user: User, body: dict[str, Any]) -> httpx.Response:
    return await api.post(f"{API}/series", json=body, headers=auth(user))


# --- Unidades -------------------------------------------------------------------------


def test_series_days_and_window_end() -> None:
    monday = date(2026, 10, 5)
    days = series_days(monday, monday + timedelta(days=27), [0, 2, 4])
    assert len(days) == 12
    assert {day.weekday() for day in days} == {0, 2, 4}
    semester = Semester(ends_on=monday + timedelta(days=10))
    assert window_end(monday, 28, semester) == monday + timedelta(days=10)
    assert window_end(monday, 15, Semester(ends_on=monday + timedelta(days=90))) == monday + (
        timedelta(days=14)
    )
    assert window_end(monday, "semester", semester) == semester.ends_on


# --- Viaje puntual --------------------------------------------------------------------


async def test_publish_single_trip_with_route_eta_and_rules(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    user, vehicle = driver
    response = await publish(routing_api, user, trip_body(places, vehicle))
    assert response.status_code == 201, response.text
    trip = response.json()
    assert trip["status"] == "scheduled"
    assert trip["series_id"] is None
    assert [s["kind"] for s in trip["stops"]] == ["origin", "stop", "destination"]
    assert trip["stop_count"] == 1
    assert trip["distance_m"] == 4000
    assert trip["est_duration_s"] == 600
    departs = datetime.fromisoformat(trip["departs_at"])
    etas = [datetime.fromisoformat(s["eta"]) - departs for s in trip["stops"]]
    assert etas == [timedelta(0), timedelta(seconds=300), timedelta(seconds=600)]
    assert trip["rules"] == [{"kind": "pets", "value": "not_allowed"}]
    assert trip["vehicle"]["plate"] == "ABC123"
    assert trip["editable"] is True
    assert len(trip["geometry"]) == 3

    # Otro usuario ve el viaje, sin placa ni datos privados del conductor.
    passenger = await make_user(UserRole.PASSENGER)
    seen = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(passenger))).json()
    assert seen["vehicle"]["plate"] is None
    assert seen["editable"] is False
    assert set(seen["driver"]) == {"id", "full_name"}


async def test_only_drivers_who_can_publish(
    routing_api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    places: list[Place],
    driver: tuple[User, Vehicle],
) -> None:
    _, vehicle = driver
    passenger = await make_user(UserRole.PASSENGER)
    response = await publish(routing_api, passenger, trip_body(places, vehicle))
    assert response.json()["code"] == "PUBLISH_NOT_ALLOWED"

    unlicensed = await make_user(UserRole.DRIVER)
    response = await publish(routing_api, unlicensed, trip_body(places, vehicle))
    assert response.status_code == 403
    assert "license_missing" in response.json()["details"]["blockers"]

    # Vehiculo ajeno: no existe para este conductor.
    other, _ = await make_driver(db, make_user, plate="DEF456")
    response = await publish(routing_api, other, trip_body(places, vehicle))
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"seats": 5}, "SEATS_INVALID"),
        (
            {"departs_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()},
            "DEPARTURE_TOO_SOON",
        ),
        ({"departs_at": (datetime.now(UTC) + timedelta(days=90)).isoformat()}, "DEPARTURE_TOO_FAR"),
        ({"rules": [{"kind": "pets", "value": "maybe"}]}, "VALIDATION_ERROR"),
        ({"rules": [{"kind": "pets", "value": "allowed"}] * 2}, "VALIDATION_ERROR"),
        ({"place_ids": []}, "VALIDATION_ERROR"),
    ],
)
async def test_publish_validations(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    overrides: dict[str, Any],
    code: str,
) -> None:
    user, vehicle = driver
    response = await publish(routing_api, user, trip_body(places, vehicle, **overrides))
    assert response.json()["code"] == code


async def test_price_cap_and_inactive_vehicle(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    su_headers: dict[str, str],
) -> None:
    user, vehicle = driver
    await routing_api.patch(
        f"{API}/admin/settings/max_price_per_seat", json={"value": 3000}, headers=su_headers
    )
    response = await publish(routing_api, user, trip_body(places, vehicle, price_per_seat=3500))
    assert response.json() == {
        "code": "PRICE_ABOVE_MAX",
        "message": response.json()["message"],
        "details": {"max": 3000},
    }
    assert (
        await publish(routing_api, user, trip_body(places, vehicle, price_per_seat=0))
    ).status_code == 201

    vehicle.is_active = False
    db.add(
        Vehicle(
            owner_id=user.id,
            type=VehicleType.CAR,
            plate="KLM987",
            brand="Kia",
            model="Picanto",
            color="Rojo",
            year=2020,
            capacity=5,
        )
    )
    await db.flush()
    response = await publish(
        routing_api, user, trip_body(places, vehicle, departs_at=tomorrow_at(9).isoformat())
    )
    assert response.json()["code"] == "VEHICLE_INACTIVE"


async def test_women_only_needs_a_female_driver(
    routing_api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    places: list[Place],
    driver: tuple[User, Vehicle],
) -> None:
    rules = [{"kind": "women_only", "value": "allowed"}]
    man, his_car = await make_driver(db, make_user, sex=Sex.MALE, plate="DEF456")
    response = await publish(routing_api, man, trip_body(places, his_car, rules=rules))
    assert response.status_code == 403
    assert response.json()["code"] == "WOMEN_ONLY_FEMALE_DRIVERS"

    woman, her_car = driver
    response = await publish(routing_api, woman, trip_body(places, her_car, rules=rules))
    assert response.status_code == 201
    assert response.json()["rules"] == rules

    # "No" en solo mujeres equivale a no tener la regla.
    response = await publish(
        routing_api,
        man,
        trip_body(places, his_car, rules=[{"kind": "women_only", "value": "not_allowed"}]),
    )
    assert response.status_code == 201
    assert response.json()["rules"] == []


async def test_single_trip_on_pico_placa_day_is_rejected(
    routing_api: AsyncClient, db: AsyncSession, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    user, vehicle = driver
    departs = tomorrow_at()
    await pico_placa(db, departs.weekday(), [3])
    response = await publish(routing_api, user, trip_body(places, vehicle))
    assert response.status_code == 422
    assert response.json()["code"] == "PICO_PLACA_RESTRICTED"
    assert response.json()["details"]["date"] == departs.date().isoformat()


async def test_other_users_pins_cannot_be_used(
    routing_api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    places: list[Place],
    driver: tuple[User, Vehicle],
) -> None:
    stranger = await make_user(UserRole.PASSENGER)
    pin = Place(
        name="Casa", kind=PlaceKind.CUSTOM, point=point(7.38, -72.65), created_by=stranger.id
    )
    db.add(pin)
    await db.flush()
    user, vehicle = driver
    body = trip_body(places, vehicle, place_ids=[str(places[0].id), str(pin.id)])
    response = await publish(routing_api, user, body)
    assert response.status_code == 404
    assert response.json()["code"] == "PLACE_NOT_FOUND"


async def test_driver_cannot_overlap_trips(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    user, vehicle = driver
    assert (await publish(routing_api, user, trip_body(places, vehicle))).status_code == 201
    clash = tomorrow_at() + timedelta(minutes=5)
    response = await publish(
        routing_api, user, trip_body(places, vehicle, departs_at=clash.isoformat())
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TRIP_OVERLAP"
    later = tomorrow_at() + timedelta(minutes=15)
    response = await publish(
        routing_api, user, trip_body(places, vehicle, departs_at=later.isoformat())
    )
    assert response.status_code == 201


# --- Editar, cancelar y duplicar ------------------------------------------------------


async def test_edit_trip_until_cutoff(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    user, vehicle = driver
    trip = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    url = f"{API}/trips/{trip['id']}"
    new_time = tomorrow_at(9)
    response = await routing_api.patch(
        url,
        json={
            "departs_at": new_time.isoformat(),
            "seats": 2,
            "place_ids": [str(places[0].id), str(places[2].id)],
        },
        headers=auth(user),
    )
    assert response.status_code == 200, response.text
    edited = response.json()
    assert datetime.fromisoformat(edited["departs_at"]) == new_time
    assert edited["seats_total"] == 2
    assert len(edited["stops"]) == 2
    assert edited["rules"] == trip["rules"]

    # Nadie mas edita el viaje.
    other = await make_user(UserRole.DRIVER)
    assert (await routing_api.patch(url, json={"seats": 1}, headers=auth(other))).status_code == 404

    # A menos de trip_edit_cutoff_minutes de salir ya no se edita.
    row = await db.get(Trip, edited["id"])
    assert row is not None
    row.departs_at = datetime.now(UTC) + timedelta(minutes=20)
    await db.flush()
    response = await routing_api.patch(url, json={"seats": 1}, headers=auth(user))
    assert response.status_code == 409
    assert response.json()["code"] == "TRIP_NOT_EDITABLE"


async def test_cancel_trip_needs_reason_and_hides_it(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    user, vehicle = driver
    trip = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    url = f"{API}/trips/{trip['id']}/cancel"
    assert (
        await routing_api.post(url, json={"reason": "no"}, headers=auth(user))
    ).status_code == 422
    response = await routing_api.post(url, json={"reason": "Se daño el carro"}, headers=auth(user))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled_by_driver"
    assert response.json()["cancel_reason"] == "Se daño el carro"
    again = await routing_api.post(url, json={"reason": "Otra vez"}, headers=auth(user))
    assert again.json()["code"] == "TRIP_NOT_EDITABLE"

    passenger = await make_user(UserRole.PASSENGER)
    hidden = await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(passenger))
    assert hidden.status_code == 404


async def test_duplicate_trip_with_new_date(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    user, vehicle = driver
    trip = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    new_time = tomorrow_at(days=2)
    response = await routing_api.post(
        f"{API}/trips/{trip['id']}/duplicate",
        json={"departs_at": new_time.isoformat()},
        headers=auth(user),
    )
    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != trip["id"]
    assert [s["place_id"] for s in copy["stops"]] == [s["place_id"] for s in trip["stops"]]
    assert (copy["seats_total"], copy["price_per_seat"], copy["rules"]) == (
        trip["seats_total"],
        trip["price_per_seat"],
        trip["rules"],
    )


async def test_my_trips_upcoming_and_history(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    user, vehicle = driver
    first = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    second = (
        await publish(
            routing_api,
            user,
            trip_body(places, vehicle, departs_at=tomorrow_at(days=2).isoformat()),
        )
    ).json()
    await routing_api.post(
        f"{API}/trips/{second['id']}/cancel",
        json={"reason": "Cambio de planes"},
        headers=auth(user),
    )

    upcoming = (await routing_api.get(f"{API}/trips/mine?limit=1", headers=auth(user))).json()
    assert [t["id"] for t in upcoming["items"]] == [first["id"]]
    assert upcoming["next_cursor"] is None
    history = (await routing_api.get(f"{API}/trips/mine?scope=history", headers=auth(user))).json()
    assert [t["id"] for t in history["items"]] == [second["id"]]


# --- Series ---------------------------------------------------------------------------


async def test_four_week_series_generates_occurrences_and_marks_pico_placa(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    semester: Semester,
    make_user: UserFactory,
) -> None:
    """Aceptacion del paso 6."""
    user, vehicle = driver
    await pico_placa(db, weekday=2, digits=[3])  # miercoles, placa terminada en 3
    response = await publish_series(routing_api, user, series_body(places, vehicle))
    assert response.status_code == 201, response.text
    series = response.json()
    start = next_monday()
    assert series["window_start"] == start.isoformat()
    assert series["window_end"] == (start + timedelta(days=27)).isoformat()
    assert series["counts"] == {"total": 12, "scheduled": 8, "pico_placa": 4, "cancelled": 0}

    occurrences = series["occurrences"]
    departures = [datetime.fromisoformat(o["departs_at"]).astimezone(LOCAL_TZ) for o in occurrences]
    assert {d.weekday() for d in departures} == {0, 2, 4}
    assert all(d.time() == time(7, 0) for d in departures)
    for occurrence, departure in zip(occurrences, departures, strict=True):
        expected = "cancelled_pico_placa" if departure.weekday() == 2 else "scheduled"
        assert occurrence["status"] == expected
        assert occurrence["seats_total"] == 4
        assert occurrence["price_per_seat"] == 1500
    assert series["next_departure"] is not None

    # Los demas usuarios solo ven las ocurrencias reservables y nunca la placa.
    passenger = await make_user(UserRole.PASSENGER)
    seen = (await routing_api.get(f"{API}/series/{series['id']}", headers=auth(passenger))).json()
    assert len(seen["occurrences"]) == 8
    assert seen["vehicle"]["plate"] is None


async def test_series_never_passes_semester_end(
    routing_api: AsyncClient, db: AsyncSession, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    today = local_today()
    semester = Semester(
        name="corto",
        starts_on=today - timedelta(days=10),
        ends_on=today + timedelta(days=12),
        revalidation_deadline=today,
    )
    db.add(semester)
    await db.flush()
    user, vehicle = driver
    start = today + timedelta(days=2)
    body = series_body(places, vehicle, start_date=start.isoformat(), weekdays=list(range(7)))
    series = (await publish_series(routing_api, user, body)).json()
    assert series["window_end"] == semester.ends_on.isoformat()
    last = max(datetime.fromisoformat(o["departs_at"]) for o in series["occurrences"])
    assert last.astimezone(LOCAL_TZ).date() == semester.ends_on
    assert series["counts"]["total"] == 11

    whole = series_body(
        places, vehicle, start_date=start.isoformat(), window="semester", departure_time="18:00"
    )
    assert (await publish_series(routing_api, user, whole)).json()[
        "window_end"
    ] == semester.ends_on.isoformat()


async def test_series_validations(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    semester: Semester,
) -> None:
    user, vehicle = driver
    bad_window = await publish_series(routing_api, user, series_body(places, vehicle, window=10))
    assert bad_window.json()["code"] == "SERIES_WINDOW_INVALID"

    past = series_body(places, vehicle, start_date=(local_today() - timedelta(days=1)).isoformat())
    assert (await publish_series(routing_api, user, past)).json()["code"] == "SERIES_START_IN_PAST"

    outside = series_body(
        places, vehicle, start_date=(semester.ends_on + timedelta(days=5)).isoformat()
    )
    assert (await publish_series(routing_api, user, outside)).json()[
        "code"
    ] == "SERIES_OUTSIDE_SEMESTER"

    await pico_placa(db, weekday=2, digits=[3])
    only_wednesdays = series_body(places, vehicle, weekdays=[2])
    response = await publish_series(routing_api, user, only_wednesdays)
    assert response.json()["code"] == "SERIES_EMPTY"
    assert len(response.json()["details"]["pico_placa_dates"]) == 4

    repeated = series_body(places, vehicle, weekdays=[1, 1])
    assert (await publish_series(routing_api, user, repeated)).json()["code"] == "VALIDATION_ERROR"


async def test_series_occurrences_cannot_overlap_other_trips(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place], semester: Semester
) -> None:
    user, vehicle = driver
    monday = datetime.combine(next_monday(), time(7, 2), tzinfo=LOCAL_TZ)
    assert (
        await publish(routing_api, user, trip_body(places, vehicle, departs_at=monday.isoformat()))
    ).status_code == 201
    response = await publish_series(routing_api, user, series_body(places, vehicle))
    assert response.status_code == 409
    assert response.json()["details"]["dates"] == [next_monday().isoformat()]


async def test_edit_series_regenerates_future_occurrences(
    routing_api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place], semester: Semester
) -> None:
    user, vehicle = driver
    series = (await publish_series(routing_api, user, series_body(places, vehicle))).json()
    first_ids = {o["id"] for o in series["occurrences"]}
    response = await routing_api.patch(
        f"{API}/series/{series['id']}",
        json={"weekdays": [0, 3], "departure_time": "08:30", "seats": 2, "price_per_seat": 1000},
        headers=auth(user),
    )
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["weekdays"] == [0, 3]
    assert edited["counts"] == {"total": 8, "scheduled": 8, "pico_placa": 0, "cancelled": 0}
    departures = [
        datetime.fromisoformat(o["departs_at"]).astimezone(LOCAL_TZ) for o in edited["occurrences"]
    ]
    assert {d.weekday() for d in departures} == {0, 3}
    assert all(d.time() == time(8, 30) for d in departures)
    assert all(o["seats_total"] == 2 and o["price_per_seat"] == 1000 for o in edited["occurrences"])
    # Los lunes se actualizan en su lugar; los jueves son nuevos.
    mondays = {
        o["id"] for o, d in zip(edited["occurrences"], departures, strict=True) if d.weekday() == 0
    }
    assert mondays <= first_ids
    assert len(mondays) == 4


async def test_cancel_and_duplicate_series(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    semester: Semester,
    make_user: UserFactory,
) -> None:
    user, vehicle = driver
    series = (await publish_series(routing_api, user, series_body(places, vehicle))).json()
    url = f"{API}/series/{series['id']}"
    response = await routing_api.post(
        f"{url}/cancel", json={"reason": "Termino el curso"}, headers=auth(user)
    )
    assert response.status_code == 200
    cancelled = response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["counts"]["cancelled"] == 12
    assert (await routing_api.patch(url, json={"seats": 1}, headers=auth(user))).json()[
        "code"
    ] == "SERIES_NOT_ACTIVE"

    passenger = await make_user(UserRole.PASSENGER)
    assert (await routing_api.get(url, headers=auth(passenger))).status_code == 404

    response = await routing_api.post(
        f"{url}/duplicate",
        json={"start_date": next_monday().isoformat(), "window": 15},
        headers=auth(user),
    )
    assert response.status_code == 201
    copy = response.json()
    assert copy["status"] == "active"
    assert copy["counts"]["total"] == 7  # 15 dias desde un lunes: 3 lunes, 2 miercoles, 2 viernes
    mine = (await routing_api.get(f"{API}/series/mine", headers=auth(user))).json()
    assert [s["status"] for s in mine] == ["active", "cancelled"]


async def test_finish_past_series(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    semester: Semester,
) -> None:
    user, vehicle = driver
    series = (await publish_series(routing_api, user, series_body(places, vehicle))).json()
    assert await finish_past_series(db, next_monday() + timedelta(days=27)) == 0
    assert await finish_past_series(db, next_monday() + timedelta(days=28)) == 1
    detail = (await routing_api.get(f"{API}/series/{series['id']}", headers=auth(user))).json()
    assert detail["status"] == "finished"


# --- Pico y placa y vehiculos ---------------------------------------------------------


async def test_pico_placa_rule_changes_recheck_future_trips(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    su_headers: dict[str, str],
) -> None:
    user, vehicle = driver
    trip = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    rule = {
        "vehicle_type": "car",
        "weekday": tomorrow_at().weekday(),
        "restricted_digits": [3],
        "valid_from": local_today().isoformat(),
    }
    created = await routing_api.post(f"{API}/admin/pico-placa", json=rule, headers=su_headers)
    assert created.status_code == 201

    detail = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(user))).json()
    assert detail["status"] == "cancelled_pico_placa"
    kinds = (
        await db.scalars(select(Notification.kind).where(Notification.user_id == user.id))
    ).all()
    assert "trip_pico_placa_cancelled" in kinds

    await routing_api.delete(f"{API}/admin/pico-placa/{created.json()['id']}", headers=su_headers)
    detail = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(user))).json()
    assert detail["status"] == "scheduled"


async def test_vehicles_with_trips_cannot_be_removed(
    routing_api: AsyncClient, db: AsyncSession, driver: tuple[User, Vehicle], places: list[Place]
) -> None:
    user, vehicle = driver
    trip = (await publish(routing_api, user, trip_body(places, vehicle))).json()
    url = f"{API}/vehicles/{vehicle.id}"
    assert (await routing_api.delete(url, headers=auth(user))).json()["code"] == "VEHICLE_HAS_TRIPS"
    response = await routing_api.patch(url, json={"is_active": False}, headers=auth(user))
    assert response.json()["code"] == "VEHICLE_HAS_TRIPS"

    await routing_api.post(
        f"{API}/trips/{trip['id']}/cancel", json={"reason": "Ya no voy"}, headers=auth(user)
    )
    assert (await routing_api.delete(url, headers=auth(user))).status_code == 204


async def test_vehicle_pico_placa_dates(
    routing_api: AsyncClient, db: AsyncSession, driver: tuple[User, Vehicle], make_user: UserFactory
) -> None:
    user, vehicle = driver
    await pico_placa(db, weekday=2, digits=[3])
    start = next_monday()
    url = f"{API}/vehicles/{vehicle.id}/pico-placa?from={start}&to={start + timedelta(days=13)}"
    response = await routing_api.get(url, headers=auth(user))
    assert response.json() == [
        (start + timedelta(days=2)).isoformat(),
        (start + timedelta(days=9)).isoformat(),
    ]
    other = await make_user(UserRole.DRIVER)
    assert (await routing_api.get(url, headers=auth(other))).status_code == 404
    too_long = (
        f"{API}/vehicles/{vehicle.id}/pico-placa?from={start}&to={start + timedelta(days=400)}"
    )
    assert (await routing_api.get(too_long, headers=auth(user))).json()["code"] == "INVALID_RANGE"
