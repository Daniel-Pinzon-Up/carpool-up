import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import ActiveUser, CurrentUser
from app.core.deps import DbSession
from app.core.errors import AppError
from app.modules.pico_placa.service import PicoPlacaService
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


@router.get("/{vehicle_id}/pico-placa")
async def pico_placa_dates(
    vehicle_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
) -> list[date]:
    """Fechas del rango (maximo 200 dias) en que el vehiculo propio tiene pico y placa."""
    if end < start or end - start > timedelta(days=200):
        raise AppError("INVALID_RANGE", "Invalid date range", 422, {"max_days": 200})
    vehicle = await VehicleService(session).get_own(user, vehicle_id)
    dates = await PicoPlacaService(session).restricted_dates(
        vehicle.type, vehicle.plate, start, end
    )
    return sorted(dates)
