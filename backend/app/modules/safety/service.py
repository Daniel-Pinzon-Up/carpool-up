"""Seguridad (seccion 7.8): contactos de confianza, enlace compartido, ubicacion y emergencias."""

import hashlib
import secrets
import uuid
from datetime import timedelta

import structlog
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import utcnow
from app.core.enums import TripStatus, UserRole, UserStatus
from app.core.errors import AppError, NotFoundError
from app.core.realtime import emit
from app.modules.audit.service import AuditService
from app.modules.bookings.models import HOLDING_STATUSES, Booking
from app.modules.notifications.service import Kind, NotificationService
from app.modules.safety.location import last_location
from app.modules.safety.models import EmergencyEvent, ShareLink, TrustedContact
from app.modules.safety.schemas import (
    ContactIn,
    ContactUpdate,
    EmergencyIn,
    EmergencyOut,
    LiveLocation,
    PublicStop,
    PublicTrip,
    PublicVehicle,
    ShareLinkOut,
)
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.users.models import User

logger = structlog.get_logger("safety")

ADMIN_CHANNEL = "admin:emergencies"
LIVE_STATUSES = (TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def is_participant(session: AsyncSession, trip: Trip, user: User) -> bool:
    """El conductor o un pasajero aceptado (que viaja) en ese viaje."""
    if trip.driver_id == user.id:
        return True
    found = await session.scalar(
        select(Booking.id).where(
            Booking.trip_id == trip.id,
            Booking.passenger_id == user.id,
            Booking.status.in_(HOLDING_STATUSES),
        )
    )
    return found is not None


async def participant_trip(session: AsyncSession, user: User, trip_id: uuid.UUID) -> Trip:
    trip = await session.get(Trip, trip_id)
    if trip is None or trip.deleted_at is not None or not await is_participant(session, trip, user):
        raise NotFoundError("trip")
    return trip


def emergency_out(event: EmergencyEvent) -> EmergencyOut:
    trip = event.trip
    return EmergencyOut(
        id=event.id,
        trip_id=trip.id,
        trip_status=trip.status,
        route=f"{trip.stops[0].place.name} - {trip.stops[-1].place.name}",
        user_id=event.user_id,
        user_name=event.user.full_name,
        lat=event.lat,
        lon=event.lon,
        note=event.note,
        created_at=event.created_at,
        handled_at=event.handled_at,
        resolution=event.resolution,
    )


class SafetyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)

    # --- Contactos de confianza --------------------------------------------------------------

    async def contacts(self, user: User) -> list[TrustedContact]:
        rows = await self.session.scalars(
            select(TrustedContact)
            .where(TrustedContact.user_id == user.id)
            .order_by(TrustedContact.created_at)
        )
        return list(rows.all())

    async def add_contact(self, user: User, data: ContactIn) -> TrustedContact:
        limit = int(await self.settings.get("trusted_contacts_max"))
        count = await self.session.scalar(
            select(func.count()).where(TrustedContact.user_id == user.id)
        )
        if int(count or 0) >= limit:
            raise AppError(
                "TRUSTED_CONTACTS_LIMIT", "Too many trusted contacts", 409, {"max": limit}
            )
        contact = TrustedContact(
            user_id=user.id, name=data.name, phone=data.phone, relation=data.relationship
        )
        self.session.add(contact)
        await self.session.commit()
        return contact

    async def own_contact(self, user: User, contact_id: uuid.UUID) -> TrustedContact:
        contact = await self.session.get(TrustedContact, contact_id)
        if contact is None or contact.user_id != user.id:
            raise NotFoundError("trusted_contact")
        return contact

    async def update_contact(
        self, user: User, contact_id: uuid.UUID, data: ContactUpdate
    ) -> TrustedContact:
        contact = await self.own_contact(user, contact_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            contact.name = changes["name"]
        if "phone" in changes:
            contact.phone = changes["phone"]
        if "relationship" in changes:
            contact.relation = changes["relationship"]
        await self.session.commit()
        return contact

    async def delete_contact(self, user: User, contact_id: uuid.UUID) -> None:
        await self.session.delete(await self.own_contact(user, contact_id))
        await self.session.commit()

    # --- Enlace compartido -----------------------------------------------------------------

    async def create_share_link(self, user: User, trip_id: uuid.UUID) -> ShareLinkOut:
        """Vence al terminar el viaje (llegada estimada) mas share_link_extra_minutes."""
        trip = await participant_trip(self.session, user, trip_id)
        if trip.status not in LIVE_STATUSES:
            raise AppError("TRIP_NOT_SHAREABLE", "Only upcoming or ongoing trips are shared", 409)
        extra = int(await self.settings.get("share_link_extra_minutes"))
        start = max(trip.departs_at, trip.started_at or trip.departs_at)
        expires_at = start + timedelta(seconds=trip.est_duration_s, minutes=extra)
        token = secrets.token_urlsafe(32)
        self.session.add(
            ShareLink(
                trip_id=trip.id,
                created_by=user.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return ShareLinkOut(token=token, path=f"/compartido/{token}", expires_at=expires_at)

    async def public_trip(self, token: str) -> PublicTrip:
        """Lo que ve quien recibe el enlace: ruta, vehiculo con placa y ubicacion en vivo.
        Sin nombres, correos ni telefonos."""
        link = await self.session.scalar(
            select(ShareLink).where(ShareLink.token_hash == hash_token(token))
        )
        if link is None or link.expires_at <= utcnow() or link.trip.deleted_at is not None:
            raise NotFoundError("share_link")
        trip = link.trip
        vehicle = trip.vehicle
        located = await last_location(trip.id) if trip.status == TripStatus.IN_PROGRESS else None
        line = to_shape(trip.route)
        return PublicTrip(
            status=trip.status,
            departs_at=trip.departs_at,
            started_at=trip.started_at,
            finished_at=trip.finished_at,
            arrives_at=max(trip.departs_at, trip.started_at or trip.departs_at)
            + timedelta(seconds=trip.est_duration_s),
            geometry=[[x, y] for x, y in line.coords],
            stops=[
                PublicStop(name=s.place.name, lat=s.place.lat, lon=s.place.lon, kind=s.kind)
                for s in trip.stops
            ],
            vehicle=PublicVehicle(
                type=vehicle.type,
                brand=vehicle.brand,
                model=vehicle.model,
                color=vehicle.color,
                plate=vehicle.plate,
            ),
            location=LiveLocation(**located) if located else None,
            expires_at=link.expires_at,
        )

    # --- Ubicacion --------------------------------------------------------------------------

    async def location(self, user: User, trip_id: uuid.UUID) -> LiveLocation | None:
        trip = await participant_trip(self.session, user, trip_id)
        if trip.status != TripStatus.IN_PROGRESS:
            return None
        located = await last_location(trip.id)
        return LiveLocation(**located) if located else None

    # --- Emergencias ------------------------------------------------------------------------

    async def emergency(self, user: User, trip_id: uuid.UUID, data: EmergencyIn) -> EmergencyOut:
        """Registra la alerta con la ultima ubicacion (la del telefono o la del viaje) y la
        envia en vivo a los administradores."""
        trip = await participant_trip(self.session, user, trip_id)
        if trip.status not in LIVE_STATUSES:
            raise AppError("TRIP_NOT_ACTIVE", "The trip is not active", 409)
        lat, lon = data.lat, data.lon
        if lat is None or lon is None:
            located = await last_location(trip.id)
            lat, lon = (located["lat"], located["lon"]) if located else (None, None)
        event = EmergencyEvent(
            trip_id=trip.id, user_id=user.id, lat=lat, lon=lon, note=data.note, created_at=utcnow()
        )
        event.trip = trip
        event.user = user
        self.session.add(event)
        await self.session.flush()
        out = emergency_out(event)
        admins = await self.session.scalars(
            select(User.id).where(
                User.role.in_((UserRole.ADMIN, UserRole.SUPERADMIN)),
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        )
        notifications = NotificationService(self.session)
        for admin_id in admins.all():
            notifications.notify(
                admin_id,
                Kind.EMERGENCY_ALERT,
                {
                    "emergency_id": str(event.id),
                    "trip_id": str(trip.id),
                    "user_name": user.full_name,
                },
            )
        emit(
            self.session,
            ADMIN_CHANNEL,
            {"type": "emergency", "emergency": out.model_dump(mode="json")},
        )
        await self.session.commit()
        logger.warning("emergency_reported", trip_id=str(trip.id))
        return out

    async def open_emergencies(self, include_handled: bool) -> list[EmergencyOut]:
        query = select(EmergencyEvent).order_by(
            EmergencyEvent.handled_at.is_not(None), EmergencyEvent.created_at.desc()
        )
        if not include_handled:
            query = query.where(EmergencyEvent.handled_at.is_(None))
        rows = await self.session.scalars(query.limit(200))
        return [emergency_out(e) for e in rows.all()]

    async def handle_emergency(
        self, actor: Actor, emergency_id: uuid.UUID, resolution: str
    ) -> EmergencyOut:
        event = await self.session.get(EmergencyEvent, emergency_id)
        if event is None:
            raise NotFoundError("emergency")
        if event.handled_at is not None:
            raise AppError("EMERGENCY_HANDLED", "This emergency was already handled", 409)
        event.handled_at = utcnow()
        event.handled_by = actor.user.id
        event.resolution = resolution.strip()
        AuditService(self.session).record(
            actor,
            "emergency.handle",
            "emergency_event",
            event.id,
            None,
            {"resolution": event.resolution},
        )
        out = emergency_out(event)
        emit(
            self.session,
            ADMIN_CHANNEL,
            {"type": "emergency.handled", "emergency": out.model_dump(mode="json")},
        )
        await self.session.commit()
        return out
