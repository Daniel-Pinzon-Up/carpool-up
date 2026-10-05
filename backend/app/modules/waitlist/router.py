import uuid

from fastapi import APIRouter, status

from app.core.auth import Passenger
from app.core.deps import DbSession
from app.modules.bookings.schemas import WaitlistJoin, WaitlistOut
from app.modules.waitlist.service import WaitlistService, waitlist_outs

router = APIRouter(tags=["waitlist"])


async def _out(service: WaitlistService, entry_id: uuid.UUID, user: Passenger) -> WaitlistOut:
    entry = await service.reload(entry_id)
    return (await waitlist_outs(service.session, [entry], user))[0]


@router.post(
    "/trips/{trip_id}/waitlist",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "WAITLIST_NOT_NEEDED, WAITLIST_EXISTS, BOOKING_EXISTS"}},
)
async def join_waitlist(
    trip_id: uuid.UUID, body: WaitlistJoin, user: Passenger, session: DbSession
) -> WaitlistOut:
    """Anotarse en un viaje sin cupo para los puestos pedidos."""
    service = WaitlistService(session)
    entry = await service.join(user, trip_id, body)
    return await _out(service, entry.id, user)


@router.delete("/trips/{trip_id}/waitlist", status_code=status.HTTP_204_NO_CONTENT)
async def leave_waitlist(trip_id: uuid.UUID, user: Passenger, session: DbSession) -> None:
    await WaitlistService(session).leave(user, trip_id)


@router.get("/waitlist/mine")
async def my_waitlist(user: Passenger, session: DbSession) -> list[WaitlistOut]:
    return await WaitlistService(session).list_mine(user)


@router.post(
    "/waitlist/{entry_id}/confirm",
    responses={409: {"description": "WAITLIST_OFFER_EXPIRED, TRIP_FULL"}},
)
async def confirm_offer(entry_id: uuid.UUID, user: Passenger, session: DbSession) -> WaitlistOut:
    """Acepta la oferta: crea una solicitud que el conductor aprueba como siempre."""
    service = WaitlistService(session)
    entry = await service.confirm(user, entry_id)
    return await _out(service, entry.id, user)


@router.post(
    "/waitlist/{entry_id}/decline", responses={409: {"description": "WAITLIST_OFFER_EXPIRED"}}
)
async def decline_offer(entry_id: uuid.UUID, user: Passenger, session: DbSession) -> WaitlistOut:
    service = WaitlistService(session)
    entry = await service.decline(user, entry_id)
    return await _out(service, entry.id, user)
