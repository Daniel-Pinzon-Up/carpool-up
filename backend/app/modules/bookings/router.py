import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, status

from app.core.auth import ActiveUser, Driver, Passenger
from app.core.deps import DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.core.rate_limit import limiter
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingOut,
    InboxOut,
    ReasonIn,
    SeriesAvailability,
    SubscriptionCreate,
    SubscriptionOut,
)
from app.modules.bookings.service import BookingService
from app.modules.bookings.subscriptions import SubscriptionService, subscription_outs
from app.modules.trips.lifecycle import TripLifecycle

router = APIRouter(tags=["bookings"])

REQUEST_ERRORS: dict[int | str, dict[str, str]] = {
    403: {"description": "WOMEN_ONLY_TRIP, BOOKING_SUSPENDED, FORBIDDEN (solo pasajeros)"},
    409: {
        "description": "TRIP_FULL, TRIP_NOT_BOOKABLE, BOOKING_EXISTS, BOOKING_OVERLAP, "
        "BOOKING_OWN_TRIP"
    },
    422: {"description": "POINTS_OFF_ROUTE, PREFERENCES_CONFLICT, PLACE_OUT_OF_AREA"},
}
DECISION_ERRORS: dict[int | str, dict[str, str]] = {
    409: {"description": "BOOKING_NOT_PENDING, TRIP_FULL, TRIP_NOT_BOOKABLE"}
}


# --- Reservas -------------------------------------------------------------------------


@router.post(
    "/trips/{trip_id}/bookings", status_code=status.HTTP_201_CREATED, responses=REQUEST_ERRORS
)
@limiter.limit("20/minute")
async def request_booking(
    request: Request, trip_id: uuid.UUID, body: BookingCreate, user: Passenger, session: DbSession
) -> BookingOut:
    """Solicita cupo. Queda en requested y no aparta puestos hasta que el conductor acepte."""
    service = BookingService(session)
    return await service.out(await service.request(user, trip_id, body), user)


@router.get("/trips/{trip_id}/bookings")
async def trip_bookings(trip_id: uuid.UUID, user: Driver, session: DbSession) -> list[BookingOut]:
    """Todas las reservas de un viaje propio, por hora de recogida."""
    return await BookingService(session).list_for_trip(user, trip_id)


@router.get("/bookings/mine")
async def my_bookings(
    user: Passenger,
    session: DbSession,
    scope: Literal["upcoming", "history"] = "upcoming",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[BookingOut]:
    return await BookingService(session).list_mine(user, scope, limit, cursor)


@router.get("/bookings/inbox")
async def driver_inbox(user: Driver, session: DbSession) -> InboxOut:
    """Solicitudes, cancelaciones tardias y suscripciones que esperan al conductor."""
    requests, cancellations = await BookingService(session).pending_for_driver(user)
    subscriptions = await SubscriptionService(session).pending_for_driver(user)
    return InboxOut(bookings=requests, cancellations=cancellations, subscriptions=subscriptions)


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: uuid.UUID, user: ActiveUser, session: DbSession) -> BookingOut:
    """Para el pasajero y el conductor del viaje."""
    service = BookingService(session)
    return await service.out(await service.get_visible(user, booking_id), user)


@router.post("/bookings/{booking_id}/accept", responses=DECISION_ERRORS)
async def accept_booking(booking_id: uuid.UUID, user: Driver, session: DbSession) -> BookingOut:
    """Acepta con el viaje bloqueado: nunca se aceptan mas puestos que los ofrecidos."""
    service = BookingService(session)
    return await service.out(await service.accept(user, booking_id), user)


@router.post("/bookings/{booking_id}/reject", responses=DECISION_ERRORS)
async def reject_booking(
    booking_id: uuid.UUID, body: ReasonIn, user: Driver, session: DbSession
) -> BookingOut:
    service = BookingService(session)
    return await service.out(await service.reject(user, booking_id, body.reason), user)


@router.post(
    "/bookings/{booking_id}/cancel",
    responses={
        409: {"description": "BOOKING_NOT_CANCELLABLE, CANCELLATION_PENDING"},
        422: {"description": "CANCEL_REASON_REQUIRED"},
    },
)
async def cancel_booking(
    booking_id: uuid.UUID, body: ReasonIn, user: Passenger, session: DbSession
) -> BookingOut:
    """Cancela directo si faltan mas de cancel_free_hours, si el viaje cambio o si el
    conductor va retrasado; si no, crea una solicitud de cancelacion con motivo."""
    service = BookingService(session)
    return await service.out(await service.cancel(user, booking_id, body.reason), user)


@router.post(
    "/cancellation-requests/{request_id}/accept",
    responses={409: {"description": "CANCELLATION_NOT_PENDING"}},
)
async def accept_cancellation(
    request_id: uuid.UUID, user: Driver, session: DbSession
) -> BookingOut:
    service = BookingService(session)
    return await service.out(await service.resolve_cancellation(user, request_id, True), user)


@router.post(
    "/cancellation-requests/{request_id}/reject",
    responses={409: {"description": "CANCELLATION_NOT_PENDING"}},
)
async def reject_cancellation(
    request_id: uuid.UUID, user: Driver, session: DbSession
) -> BookingOut:
    service = BookingService(session)
    return await service.out(await service.resolve_cancellation(user, request_id, False), user)


BOARDING_ERRORS: dict[int | str, dict[str, str]] = {
    409: {"description": "TRIP_NOT_IN_PROGRESS, BOOKING_NOT_BOARDABLE, NO_SHOW_TOO_EARLY"}
}


@router.post("/bookings/{booking_id}/boarded", responses=BOARDING_ERRORS)
async def mark_boarded(booking_id: uuid.UUID, user: Driver, session: DbSession) -> BookingOut:
    """El conductor marca que el pasajero subio (viaje en curso)."""
    booking = await TripLifecycle(session).board(user, booking_id)
    service = BookingService(session)
    return await service.out(await service.reload(booking.id), user)


@router.post("/bookings/{booking_id}/no-show", responses=BOARDING_ERRORS)
async def mark_no_show(booking_id: uuid.UUID, user: Driver, session: DbSession) -> BookingOut:
    """Desde la salida mas no_show_wait_minutes. Varios no-shows suspenden las reservas."""
    booking = await TripLifecycle(session).no_show(user, booking_id)
    service = BookingService(session)
    return await service.out(await service.reload(booking.id), user)


# --- Suscripciones a series -----------------------------------------------------------


async def _subscription(service: SubscriptionService, sub_id: uuid.UUID) -> SubscriptionOut:
    sub = await service.reload(sub_id)
    return (await subscription_outs(service.session, [sub]))[0]


@router.get("/series/{series_id}/availability")
async def series_availability(
    series_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    seats: Annotated[int, Query(ge=1, le=7)] = 1,
) -> SeriesAvailability:
    """Fechas futuras de la serie con su cupo; las de pico y placa aparecen bloqueadas."""
    return await SubscriptionService(session).availability(user, series_id, seats)


@router.post(
    "/series/{series_id}/subscriptions",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "WOMEN_ONLY_TRIP, BOOKING_SUSPENDED"},
        409: {"description": "SUBSCRIPTION_EXISTS, BOOKING_OWN_TRIP"},
        422: {
            "description": "SUBSCRIPTION_OPTION_INVALID, SUBSCRIPTION_OUT_OF_RANGE, "
            "SUBSCRIPTION_EMPTY, POINTS_OFF_ROUTE, PREFERENCES_CONFLICT"
        },
    },
)
@limiter.limit("10/minute")
async def request_subscription(
    request: Request,
    series_id: uuid.UUID,
    body: SubscriptionCreate,
    user: Passenger,
    session: DbSession,
) -> SubscriptionOut:
    """Pide unirse a la serie por 8 dias, 15 dias o toda la serie."""
    service = SubscriptionService(session)
    sub = await service.request(user, series_id, body)
    return await _subscription(service, sub.id)


@router.get("/subscriptions/mine")
async def my_subscriptions(user: Passenger, session: DbSession) -> list[SubscriptionOut]:
    return await SubscriptionService(session).list_mine(user)


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: uuid.UUID, user: ActiveUser, session: DbSession
) -> SubscriptionOut:
    service = SubscriptionService(session)
    sub = await service.get_visible(user, subscription_id)
    return await _subscription(service, sub.id)


@router.post(
    "/subscriptions/{subscription_id}/accept",
    responses={409: {"description": "SUBSCRIPTION_NOT_PENDING"}},
)
async def accept_subscription(
    subscription_id: uuid.UUID, user: Driver, session: DbSession
) -> SubscriptionOut:
    """Aprobacion unica: crea las reservas de las fechas con cupo."""
    service = SubscriptionService(session)
    sub = await service.accept(user, subscription_id)
    return await _subscription(service, sub.id)


@router.post(
    "/subscriptions/{subscription_id}/reject",
    responses={409: {"description": "SUBSCRIPTION_NOT_PENDING"}},
)
async def reject_subscription(
    subscription_id: uuid.UUID, body: ReasonIn, user: Driver, session: DbSession
) -> SubscriptionOut:
    service = SubscriptionService(session)
    sub = await service.reject(user, subscription_id, body.reason)
    return await _subscription(service, sub.id)


@router.post(
    "/subscriptions/{subscription_id}/cancel",
    responses={
        409: {"description": "SUBSCRIPTION_NOT_ACTIVE"},
        422: {"description": "CANCEL_REASON_REQUIRED"},
    },
)
async def cancel_subscription(
    subscription_id: uuid.UUID, body: ReasonIn, user: Passenger, session: DbSession
) -> SubscriptionOut:
    """Cancela las reservas futuras con las reglas de cancelacion, fecha por fecha."""
    service = SubscriptionService(session)
    sub = await service.cancel(user, subscription_id, body.reason)
    return await _subscription(service, sub.id)
