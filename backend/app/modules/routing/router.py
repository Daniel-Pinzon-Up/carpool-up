from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.modules.routing.osrm import OsrmClient, RouteProvider
from app.modules.routing.schemas import RoutePreview, RoutePreviewRequest
from app.modules.routing.service import RoutingService

router = APIRouter(prefix="/routing", tags=["routing"])


def get_route_provider() -> RouteProvider:
    """OSRM autoalojado. Las pruebas lo reemplazan por un proveedor en memoria."""
    return OsrmClient(redis_client)


Provider = Annotated[RouteProvider, Depends(get_route_provider)]


@router.post("/preview", responses={503: {"description": "ROUTING_UNAVAILABLE"}})
@limiter.limit("30/minute")
async def preview(
    request: Request,
    body: RoutePreviewRequest,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> RoutePreview:
    """Ruta por origen, paradas y destino; distancia, ETA por parada y precio sugerido.

    La ETA usa la duracion de OSRM por el factor de trafico de la franja de salida. No hay
    trafico en tiempo real.
    """
    return await RoutingService(session, provider).preview(
        body.points, user, body.departs_at, body.vehicle_type, body.seats
    )
