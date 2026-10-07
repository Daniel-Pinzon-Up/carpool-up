"""Eliminacion de la propia cuenta (Ley 1581 de 2012, seccion 15 del plan).

Anonimiza los datos personales y conserva los registros operativos:

- Se anonimizan nombre, correo, programa, foto, nota de pago y contrasena. Viajes, reservas,
  tickets, calificaciones y estadisticas siguen existiendo, pero ya no identifican a nadie.
- Se borran los documentos de identidad y la licencia (archivos y filas), los contactos de
  confianza (son datos de terceros) y los avisos.
- Los vehiculos quedan dados de baja y sin foto; la placa se conserva como registro operativo
  de los viajes ya hechos (solo la ven los administradores).
- Antes se retira a la persona de sus viajes futuros, con aviso a los afectados, y se cierran
  todas sus sesiones.
"""

import secrets
import uuid

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import utcnow
from app.core.enums import BookingStatus, TripStatus, UserRole, UserStatus
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.core.storage import delete_private_file
from app.modules.admin.users import withdraw_from_trips
from app.modules.audit.service import AuditService
from app.modules.auth.repository import SessionRepository
from app.modules.bookings.models import Booking
from app.modules.documents.models import DriverLicense, IdentityDocument
from app.modules.notifications.models import Notification
from app.modules.safety.models import TrustedContact
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

logger = structlog.get_logger("users")

DELETED_NAME = "Cuenta eliminada"
DELETED_DOMAIN = "cuenta-eliminada.invalid"
WITHDRAW_REASON = "La persona elimino su cuenta."


def anonymous_email(user_id: uuid.UUID) -> str:
    """Unico y fuera de cualquier dominio institucional: no se puede registrar ni entrar."""
    return f"eliminada-{user_id.hex}@{DELETED_DOMAIN}"


class AccountDeletion:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _in_trip_now(self, user: User) -> bool:
        driving = await self.session.scalar(
            select(Trip.id).where(Trip.driver_id == user.id, Trip.status == TripStatus.IN_PROGRESS)
        )
        if driving is not None:
            return True
        riding = await self.session.scalar(
            select(Booking.id)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(
                Booking.passenger_id == user.id,
                Booking.status == BookingStatus.ACCEPTED,
                Trip.status == TripStatus.IN_PROGRESS,
            )
        )
        return riding is not None

    async def delete(self, actor: Actor, password: str) -> None:
        user = actor.user
        if not verify_password(password, user.password_hash):
            raise AppError("PASSWORD_INCORRECT", "The password is not correct", 422)
        if user.role == UserRole.SUPERADMIN:
            # El superadmin es quien administra la plataforma; su cuenta no se borra sola.
            raise AppError("ACCOUNT_DELETE_NOT_ALLOWED", "This account cannot be deleted", 409)
        if await self._in_trip_now(user):
            raise AppError("ACCOUNT_DELETE_TRIP_IN_PROGRESS", "Finish the current trip first", 409)

        now = utcnow()
        before = {"role": user.role.value, "status": user.status.value}
        withdrawn = await withdraw_from_trips(self.session, user, WITHDRAW_REASON)

        paths: list[str] = list(
            await self.session.scalars(
                select(IdentityDocument.file_path).where(IdentityDocument.user_id == user.id)
            )
        )
        paths += await self.session.scalars(
            select(DriverLicense.file_path).where(DriverLicense.user_id == user.id)
        )
        await self.session.execute(
            delete(IdentityDocument).where(IdentityDocument.user_id == user.id)
        )
        await self.session.execute(delete(DriverLicense).where(DriverLicense.user_id == user.id))
        await self.session.execute(delete(TrustedContact).where(TrustedContact.user_id == user.id))
        await self.session.execute(delete(Notification).where(Notification.user_id == user.id))

        vehicles = (
            await self.session.scalars(select(Vehicle).where(Vehicle.owner_id == user.id))
        ).all()
        for vehicle in vehicles:
            if vehicle.photo_path:
                paths.append(vehicle.photo_path)
                vehicle.photo_path = None
                vehicle.photo_content_type = None
            vehicle.is_active = False
            vehicle.deleted_at = vehicle.deleted_at or now

        if user.avatar_path:
            paths.append(user.avatar_path)
        user.email = anonymous_email(user.id)
        user.full_name = DELETED_NAME
        user.program = None
        user.avatar_path = None
        user.payment_note = None
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.status = UserStatus.BLOCKED
        user.two_factor_required = True
        user.deleted_at = now
        await SessionRepository(self.session).revoke_all(user.id, now)

        AuditService(self.session).record(
            actor, "user.delete_self", "user", user.id, before, {"anonymized": True, **withdrawn}
        )
        await self.session.commit()
        # Los archivos se borran despues de confirmar: si la transaccion fallara, seguirian ahi.
        for path in paths:
            delete_private_file(path)
        logger.info("account_deleted", files=len(paths), **withdrawn)
