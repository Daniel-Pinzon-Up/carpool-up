"""Autorizacion por propiedad (definicion de terminado): nadie lee ni cambia lo ajeno.

Se arma un escenario completo (viaje con reserva aceptada y chat, serie con suscripcion,
ticket, lista de espera, solicitud de cancelacion, contacto de confianza, documento) y
otra persona intenta cada accion sobre recursos que no son suyos. Toda ruta con un id que
no este clasificada aqui hace fallar la prueba: una ruta nueva obliga a decidir quien la usa.
"""

import re
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus, DocKind, ReviewStatus, TripStatus, UserRole
from app.main import create_app
from app.modules.bookings.models import Booking
from app.modules.documents.models import Document
from app.modules.notifications.models import Notification
from app.modules.places.models import Place
from app.modules.semesters.models import Semester
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth, make_driver
from tests.test_chat import chats, ride
from tests.test_ratings import finished_trip
from tests.test_trips import tomorrow_at

# Rutas con id que cualquier cuenta activa puede usar a proposito.
OPEN_TO_ACTIVE = {
    ("GET", "/trips/{trip_id}"),  # detalle para reservar
    ("POST", "/trips/{trip_id}/bookings"),  # pedir cupo
    ("GET", "/users/{user_id}/ratings"),  # reputacion (sin autores)
    ("GET", "/users/{user_id}/rating-summary"),
    ("GET", "/vehicles/{vehicle_id}/photo"),  # foto del carro para reconocerlo
    ("GET", "/public/share/{token}"),  # enlace compartido, sin sesion
}


def id_routes() -> set[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    return {
        (method.upper(), path.removeprefix("/api/v1"))
        for path, operations in paths.items()
        if "{" in path and not path.startswith("/api/v1/admin")
        for method in operations
    }


async def scenario(
    api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> dict[str, Any]:
    owner = await make_user(UserRole.PASSENGER)
    trip, booking = await ride(api, driver, places, owner)
    conversation = (await chats(api, owner))[0]["id"]
    contact = await api.post(
        f"{API}/me/trusted-contacts",
        json={"name": "Mamá", "phone": "+573001112233"},
        headers=auth(owner),
    )
    assert contact.status_code == 201, contact.text
    notification = await db.scalar(select(Notification.id).where(Notification.user_id == owner.id))
    rider = await make_user(UserRole.PASSENGER)
    done = await finished_trip(
        api, db, driver, places, [rider], departs_at=tomorrow_at(days=3).isoformat()
    )
    ticket = await db.scalar(
        select(Booking.id).where(Booking.trip_id == done["id"], Booking.ticket_code.is_not(None))
    )
    document = Document(
        user_id=owner.id,
        kind=DocKind.STUDENT_CARD,
        file_path="identity/otro.png",
        content_type="image/png",
        status=ReviewStatus.APPROVED,
    )
    db.add(document)
    await db.flush()
    return {
        "owner": owner,
        "trip_id": trip["id"],
        "booking_id": booking["id"],
        "conversation_id": conversation,
        "contact_id": contact.json()["id"],
        "notification_id": str(notification),
        "done_trip_id": done["id"],
        "ticket_id": str(ticket),
        "document_id": str(document.id),
        "vehicle_id": str(driver[1].id),
    }


async def test_nobody_reaches_what_belongs_to_someone_else(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
    semester: Semester,
) -> None:
    ids = await scenario(routing_api, db, driver, places, make_user)
    other_driver, _ = await make_driver(db, make_user, plate="XYZ987")
    stranger = await make_user(UserRole.PASSENGER)
    trip = ids["trip_id"]
    # (metodo, ruta, quien lo intenta, cuerpo). El extrano de cada caso no tiene relacion
    # con el recurso: otro conductor para lo que es del conductor, otra pasajera para lo demas.
    attempts: list[tuple[str, str, User, dict[str, Any] | None]] = [
        ("GET", "/bookings/{booking_id}", stranger, None),
        ("POST", "/bookings/{booking_id}/accept", other_driver, {}),
        ("POST", "/bookings/{booking_id}/reject", other_driver, {"reason": "No puedo ese dia"}),
        ("POST", "/bookings/{booking_id}/boarded", other_driver, {}),
        ("POST", "/bookings/{booking_id}/no-show", other_driver, {}),
        ("POST", "/bookings/{booking_id}/cancel", stranger, {"reason": "No puedo ese dia"}),
        ("POST", "/bookings/{booking_id}/cancellation/accept", other_driver, {}),
        ("POST", "/bookings/{booking_id}/cancellation/reject", other_driver, {}),
        ("GET", "/conversations/{conversation_id}", stranger, None),
        ("GET", "/conversations/{conversation_id}/messages", stranger, None),
        ("POST", "/conversations/{conversation_id}/messages", stranger, {"body": "Hola"}),
        ("POST", "/conversations/{conversation_id}/read", stranger, {}),
        ("PATCH", "/me/trusted-contacts/{contact_id}", stranger, {"name": "Otro"}),
        ("DELETE", "/me/trusted-contacts/{contact_id}", stranger, None),
        ("POST", "/notifications/{notification_id}/read", stranger, {}),
        ("POST", "/tickets/{ticket_id}/paid", other_driver, {"paid": True}),
        ("PATCH", "/trips/{trip_id}", other_driver, {"seats": 2}),
        ("GET", "/trips/{trip_id}/bookings", other_driver, None),
        ("POST", "/trips/{trip_id}/cancel", other_driver, {"reason": "Ya no voy"}),
        (
            "POST",
            "/trips/{trip_id}/duplicate",
            other_driver,
            {"departs_at": tomorrow_at(days=5).isoformat()},
        ),
        ("POST", "/trips/{trip_id}/emergency", stranger, {}),
        ("POST", "/trips/{trip_id}/finish", other_driver, {}),
        ("GET", "/trips/{trip_id}/location", stranger, None),
        (
            "POST",
            "/trips/{done_trip_id}/ratings",
            stranger,
            {"target_id": str(driver[0].id), "scores": {}},
        ),
        ("POST", "/trips/{trip_id}/share-links", stranger, {}),
        ("POST", "/trips/{trip_id}/start", other_driver, {}),
        ("GET", "/users/me/documents/{document_id}/file", stranger, None),
        ("PATCH", "/vehicles/{vehicle_id}", other_driver, {"color": "Rojo"}),
        ("DELETE", "/vehicles/{vehicle_id}", other_driver, None),
        ("PUT", "/vehicles/{vehicle_id}/photo", other_driver, None),
        (
            "GET",
            "/vehicles/{vehicle_id}/pico-placa?from=2026-10-01&to=2026-10-31",
            other_driver,
            None,
        ),
    ]

    # Toda ruta con id queda clasificada: abierta a proposito o probada contra extranos.
    tried = {
        (method, re.sub(r"\{done_trip_id\}", "{trip_id}", path).split("?")[0])
        for method, path, _, _ in attempts
    }
    assert id_routes() == tried | OPEN_TO_ACTIVE, "clasifica la ruta nueva en OPEN_TO_ACTIVE o aqui"

    failures: list[str] = []
    for method, template, who, body in attempts:
        url = API + template.format(**ids)
        if method == "PUT":
            response = await routing_api.put(
                url,
                files={"photo": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
                headers=auth(who),
            )
        else:
            response = await routing_api.request(method, url, json=body, headers=auth(who))
        if response.status_code not in (403, 404):
            failures.append(f"{method} {template}: {response.status_code} {response.text[:160]}")
    assert failures == []

    # Y nada cambio para la duena.
    booking = await db.get(Booking, ids["booking_id"])
    trip_row = await db.get(Trip, trip)
    assert booking is not None and trip_row is not None
    await db.refresh(booking)
    await db.refresh(trip_row)
    assert booking.status == BookingStatus.ACCEPTED
    assert trip_row.status == TripStatus.SCHEDULED
