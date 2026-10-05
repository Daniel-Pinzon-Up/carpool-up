import uuid

from fastapi import UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import UserRole
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.storage import delete_private_file, private_file_response, save_private_file
from app.modules.settings.service import SettingsService
from app.modules.trips.queries import vehicle_has_upcoming_trips
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.vehicles.schemas import VehicleCreate, VehicleOut, VehicleUpdate, check_vehicle

PHOTO_FOLDER = "vehicles"


def to_out(vehicle: Vehicle) -> VehicleOut:
    return VehicleOut(
        id=vehicle.id,
        type=vehicle.type,
        plate=vehicle.plate,
        brand=vehicle.brand,
        model=vehicle.model,
        color=vehicle.color,
        year=vehicle.year,
        capacity=vehicle.capacity,
        luggage_space=vehicle.luggage_space,
        is_active=vehicle.is_active,
        has_photo=vehicle.photo_path is not None,
        created_at=vehicle.created_at,
    )


class VehicleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _require_driver(user: User) -> None:
        if user.role != UserRole.DRIVER:
            raise AppError("VEHICLES_DRIVERS_ONLY", "Only drivers manage vehicles", 403)

    async def list_own(self, user: User) -> list[Vehicle]:
        query = (
            select(Vehicle)
            .where(Vehicle.owner_id == user.id, Vehicle.deleted_at.is_(None))
            .order_by(Vehicle.is_active.desc(), Vehicle.created_at)
        )
        return list((await self.session.scalars(query)).all())

    async def get_own(self, user: User, vehicle_id: uuid.UUID) -> Vehicle:
        vehicle = await self.session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.deleted_at is not None or vehicle.owner_id != user.id:
            raise NotFoundError("vehicle")
        return vehicle

    async def _require_no_trips(self, vehicle: Vehicle) -> None:
        if await vehicle_has_upcoming_trips(self.session, vehicle.id):
            raise AppError(
                "VEHICLE_HAS_TRIPS",
                "The vehicle has scheduled trips; cancel them or change their vehicle first",
                409,
            )

    async def _commit_plate(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("VEHICLE_PLATE_TAKEN", "This plate is already registered", 409) from exc

    async def create(self, user: User, data: VehicleCreate) -> Vehicle:
        self._require_driver(user)
        taken = await self.session.scalar(
            select(Vehicle.id).where(Vehicle.plate == data.plate, Vehicle.deleted_at.is_(None))
        )
        if taken is not None:
            raise AppError("VEHICLE_PLATE_TAKEN", "This plate is already registered", 409)
        vehicle = Vehicle(owner_id=user.id, **data.model_dump())
        self.session.add(vehicle)
        await self._commit_plate()
        await self.session.refresh(vehicle)
        return vehicle

    async def update(self, user: User, vehicle_id: uuid.UUID, data: VehicleUpdate) -> Vehicle:
        vehicle = await self.get_own(user, vehicle_id)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        try:
            check_vehicle(
                vehicle.type,
                vehicle.plate,
                changes.get("capacity", vehicle.capacity),
                changes.get("year", vehicle.year),
            )
        except ValueError as exc:
            raise AppError(
                "VEHICLE_INVALID", "Invalid vehicle data", 422, {"rule": str(exc)}
            ) from exc
        if changes.get("is_active") is False and vehicle.is_active:
            await self._require_no_trips(vehicle)
        for field, value in changes.items():
            setattr(vehicle, field, value)
        await self.session.commit()
        await self.session.refresh(vehicle)
        return vehicle

    async def delete(self, user: User, vehicle_id: uuid.UUID) -> None:
        """Borrado logico. No se borran vehiculos con viajes programados."""
        vehicle = await self.get_own(user, vehicle_id)
        await self._require_no_trips(vehicle)
        vehicle.deleted_at = utcnow()
        vehicle.is_active = False
        await self.session.commit()

    async def set_photo(self, user: User, vehicle_id: uuid.UUID, upload: UploadFile) -> Vehicle:
        vehicle = await self.get_own(user, vehicle_id)
        max_mb = int(await SettingsService(self.session).get("max_upload_mb"))
        stored = await save_private_file(upload, PHOTO_FOLDER, max_mb)
        if not stored.content_type.startswith("image/"):
            delete_private_file(stored.path)
            raise AppError(
                "FILE_TYPE_NOT_ALLOWED",
                "Vehicle photos must be images",
                415,
                {"allowed": ["jpg", "png", "webp"]},
            )
        old = vehicle.photo_path
        vehicle.photo_path = stored.path
        vehicle.photo_content_type = stored.content_type
        await self.session.commit()
        if old:
            delete_private_file(old)
        await self.session.refresh(vehicle)
        return vehicle

    async def photo(self, viewer: User, vehicle_id: uuid.UUID) -> FileResponse:
        """Fotos de vehiculos: visibles para cualquier usuario autenticado (seccion 11)."""
        vehicle = await self.session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.photo_path is None or vehicle.photo_content_type is None:
            raise NotFoundError("photo")
        if vehicle.deleted_at is not None and vehicle.owner_id != viewer.id:
            raise ForbiddenError()
        return private_file_response(vehicle.photo_path, vehicle.photo_content_type)

    async def has_active(self, user_id: uuid.UUID) -> bool:
        query = select(Vehicle.id).where(
            Vehicle.owner_id == user_id, Vehicle.is_active.is_(True), Vehicle.deleted_at.is_(None)
        )
        return await self.session.scalar(query.limit(1)) is not None
