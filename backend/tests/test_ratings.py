"""Calificaciones, user_stats, historial y estadisticas por rol."""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import Sex, UserRole
from app.modules.places.models import Place
from app.modules.ratings.jobs import remind_pending_ratings
from app.modules.ratings.models import Rating
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth, make_driver
from tests.test_bookings import kinds
from tests.test_search import at, params, search
from tests.test_trip_lifecycle import act, full_trip, move

pytestmark = pytest.mark.integration

DRIVER_SCORES = {"punctuality": 5, "safe_driving": 4, "courtesy": 5, "cleanliness": 4}
PASSENGER_SCORES = {"punctuality": 3, "courtesy": 5, "compliance": 4}


async def finished_trip(
    api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    riders: list[User],
    **trip: Any,
) -> dict[str, Any]:
    """Viaje completado en el que todos abordaron."""
    published, bookings = await full_trip(api, driver, places, riders, **trip)
    await move(db, published["id"], 5)
    await act(api, driver[0], f"/trips/{published['id']}/start")
    for booking in bookings:
        await act(api, driver[0], f"/bookings/{booking['id']}/boarded")
    response = await act(api, driver[0], f"/trips/{published['id']}/finish")
    assert response.status_code == 200, response.text
    return published


async def rate(
    api: AsyncClient, author: User, trip_id: str, target: User, scores: dict[str, int], **extra: Any
):  # type: ignore[no-untyped-def]
    return await api.post(
        f"{API}/trips/{trip_id}/ratings",
        json={"target_id": str(target.id), "scores": scores, **extra},
        headers=auth(author),
    )


async def test_both_sides_rate_once_within_the_window(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    first, second = await make_user(UserRole.PASSENGER), await make_user(UserRole.PASSENGER)
    trip = await finished_trip(routing_api, db, driver, places, [first, second])
    assert "rating_pending" in await kinds(db, first)

    pending = (await routing_api.get(f"{API}/ratings/pending", headers=auth(first))).json()
    assert [(p["target_name"], p["target_role"]) for p in pending] == [
        (driver[0].full_name, "driver")
    ]
    assert pending[0]["criteria"] == list(DRIVER_SCORES)
    driver_pending = (
        await routing_api.get(f"{API}/ratings/pending", headers=auth(driver[0]))
    ).json()
    assert {p["target_name"] for p in driver_pending} == {first.full_name, second.full_name}

    # Criterios del otro rol, persona equivocada y alguien que no viajo.
    response = await rate(routing_api, first, trip["id"], driver[0], PASSENGER_SCORES)
    assert response.json()["code"] == "RATING_CRITERIA_INVALID"
    response = await rate(routing_api, first, trip["id"], second, PASSENGER_SCORES)
    assert response.json()["code"] == "RATING_TARGET_INVALID"
    stranger = await make_user(UserRole.PASSENGER)
    response = await rate(routing_api, stranger, trip["id"], driver[0], DRIVER_SCORES)
    assert response.status_code == 404
    response = await rate(
        routing_api, first, trip["id"], driver[0], {**DRIVER_SCORES, "courtesy": 6}
    )
    assert response.status_code == 422

    response = await rate(
        routing_api, first, trip["id"], driver[0], DRIVER_SCORES, comment="  Muy puntual  "
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["average"] == 4.5
    assert body["comment"] == "Muy puntual"
    assert "author_id" not in body
    response = await rate(routing_api, first, trip["id"], driver[0], DRIVER_SCORES)
    assert response.json()["code"] == "RATING_EXISTS"
    assert (await kinds(db, driver[0]))[-1] == "rating_received"
    assert (await routing_api.get(f"{API}/ratings/pending", headers=auth(first))).json() == []

    second_rating = await rate(
        routing_api, second, trip["id"], driver[0], {**DRIVER_SCORES, "safe_driving": 2}
    )
    assert second_rating.status_code == 201
    response = await rate(routing_api, driver[0], trip["id"], first, PASSENGER_SCORES)
    assert response.status_code == 201

    summary = (
        await routing_api.get(f"{API}/users/{driver[0].id}/rating-summary", headers=auth(first))
    ).json()
    assert summary["count"] == 2
    assert summary["criteria"] == {
        "punctuality": 5.0,
        "safe_driving": 3.0,
        "courtesy": 5.0,
        "cleanliness": 4.0,
    }
    assert summary["average"] == 4.25
    assert summary["trips_as_driver"] == 1

    # Comentario oculto por moderacion: la puntuacion se conserva.
    rating = await db.scalar(select(Rating).where(Rating.author_id == first.id))
    assert rating is not None
    rating.hidden = True
    await db.flush()
    received = (
        await routing_api.get(f"{API}/users/{driver[0].id}/ratings", headers=auth(second))
    ).json()["items"]
    hidden = next(r for r in received if r["hidden"])
    assert hidden["comment"] is None
    assert hidden["average"] == 4.5

    # Vencido el plazo ya no se califica.
    row = await db.get(Trip, trip["id"])
    assert row is not None and row.finished_at is not None
    row.finished_at = utcnow() - timedelta(days=8)
    await db.flush()
    response = await rate(routing_api, driver[0], trip["id"], second, PASSENGER_SCORES)
    assert response.json()["code"] == "RATING_WINDOW_CLOSED"
    assert (await routing_api.get(f"{API}/ratings/pending", headers=auth(driver[0]))).json() == []


async def test_search_shows_and_orders_by_driver_rating(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    rider = await make_user(UserRole.PASSENGER)
    other = await make_driver(db, make_user, sex=Sex.MALE, plate="XYZ789")
    for owner, stars in ((driver, 3), (other, 5)):
        past = await finished_trip(routing_api, db, owner, places, [rider])
        scores = dict.fromkeys(DRIVER_SCORES, stars)
        assert (await rate(routing_api, rider, past["id"], owner[0], scores)).status_code == 201

    # Mismos lugares y hora: desempata la calificacion del conductor.
    for owner in (driver, other):
        response = await routing_api.post(
            f"{API}/trips",
            json={
                "place_ids": [str(places[0].id), str(places[1].id), str(places[2].id)],
                "departs_at": at(7).isoformat(),
                "vehicle_id": str(owner[1].id),
                "seats": 3,
                "price_per_seat": 2000,
            },
            headers=auth(owner[0]),
        )
        assert response.status_code == 201, response.text
    seeker = await make_user(UserRole.PASSENGER)
    results = (await search(routing_api, seeker, params(places[0], places[2]))).json()
    assert [r["driver"]["rating"] for r in results] == [5.0, 3.0]
    assert results[0]["driver"]["trips_as_driver"] == 1


async def test_stats_and_history_for_both_roles(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    rider = await make_user(UserRole.PASSENGER)
    trip = await finished_trip(routing_api, db, driver, places, [rider])
    tickets = (await routing_api.get(f"{API}/tickets/mine", headers=auth(rider))).json()
    await routing_api.post(
        f"{API}/tickets/{tickets[0]['id']}/paid", json={"paid": True}, headers=auth(driver[0])
    )
    cancelled = await full_trip(routing_api, driver, places, [])
    await routing_api.post(
        f"{API}/trips/{cancelled[0]['id']}/cancel",
        json={"reason": "Se dano el carro"},
        headers=auth(driver[0]),
    )

    mine = (await routing_api.get(f"{API}/stats/passenger", headers=auth(rider))).json()
    assert mine["trips"] == 1
    assert mine["spent"] == 2000
    assert mine["top_origins"] == [{"name": "Ciudad Universitaria", "count": 1}]
    assert len(mine["by_month"]) == 12
    assert sum(m["trips"] for m in mine["by_month"]) == 1
    assert mine["by_month"][-1]["spent"] in (0, 2000)  # el mes actual o el siguiente
    assert (await routing_api.get(f"{API}/stats/driver", headers=auth(rider))).status_code == 403

    stats = (await routing_api.get(f"{API}/stats/driver", headers=auth(driver[0]))).json()
    assert stats["trips"] == 1
    assert stats["passengers"] == 1
    assert stats["occupancy"] == pytest.approx(1 / 3, abs=0.001)
    assert stats["contributions"] == 2000
    assert stats["confirmed_contributions"] == 2000
    assert stats["cancellations"] == 1

    history = (await routing_api.get(f"{API}/history/passenger", headers=auth(rider))).json()
    entry = history["items"][0]
    assert entry["trip_id"] == trip["id"]
    assert entry["ticket_code"].startswith("CP-")
    assert entry["paid_confirmed"] is True
    assert entry["rating"] == "pending"
    await rate(routing_api, rider, trip["id"], driver[0], DRIVER_SCORES)
    history = (await routing_api.get(f"{API}/history/passenger", headers=auth(rider))).json()
    assert history["items"][0]["rating"] == "done"

    driven = (await routing_api.get(f"{API}/history/driver", headers=auth(driver[0]))).json()
    by_trip = {item["trip_id"]: item for item in driven["items"]}
    assert by_trip[trip["id"]]["to_rate"] == 1
    assert by_trip[trip["id"]]["passengers"] == 1
    assert by_trip[cancelled[0]["id"]]["trip_status"] == "cancelled_by_driver"
    assert by_trip[cancelled[0]["id"]]["rating"] == "none"


async def test_last_reminder_before_the_window_closes(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    rider, quick = await make_user(UserRole.PASSENGER), await make_user(UserRole.PASSENGER)
    trip = await finished_trip(routing_api, db, driver, places, [rider, quick])
    await rate(routing_api, quick, trip["id"], driver[0], DRIVER_SCORES)
    assert await remind_pending_ratings(db) == 0  # aun faltan dias

    row = await db.get(Trip, trip["id"])
    assert row is not None
    row.finished_at = utcnow() - timedelta(days=6, hours=12)
    await db.flush()
    assert await remind_pending_ratings(db) == 2  # el pasajero que falta y el conductor
    assert (await kinds(db, rider))[-1] == "rating_reminder"
    assert (await kinds(db, quick))[-1] != "rating_reminder"
    assert await remind_pending_ratings(db) == 0  # una sola vez
