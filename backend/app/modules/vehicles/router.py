import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import ActiveUser, CurrentUser
from app.core.deps import DbSession
from app.modules.vehicles.schemas import VehicleCreate, VehicleOut, VehicleUpdate
from app.modules.vehicles.service import VehicleService, to_out

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("")
async def list_vehicles(user: ActiveUser, session: DbSession) -> list[VehicleOut]:
    """Vehiculos propios (no borrados)."""
    return [to_out(v) for v in await VehicleService(session).list_own(user)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_vehicle(body: VehicleCreate, user: ActiveUser, session: DbSession) -> VehicleOut:
    return to_out(await VehicleService(session).create(user, body))


@router.patch("/{vehicle_id}")
async def update_vehicle(
    vehicle_id: uuid.UUID, body: VehicleUpdate, user: ActiveUser, session: DbSession
) -> VehicleOut:
    return to_out(await VehicleService(session).update(user, vehicle_id, body))


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: uuid.UUID, user: ActiveUser, session: DbSession) -> None:
    await VehicleService(session).delete(user, vehicle_id)


@router.put("/{vehicle_id}/photo")
async def upload_photo(
    vehicle_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    photo: Annotated[UploadFile, File(description="JPG, PNG o WebP")],
) -> VehicleOut:
    return to_out(await VehicleService(session).set_photo(user, vehicle_id, photo))


@router.get("/{vehicle_id}/photo", response_class=FileResponse)
async def get_photo(vehicle_id: uuid.UUID, user: CurrentUser, session: DbSession) -> FileResponse:
    return await VehicleService(session).photo(user, vehicle_id)
