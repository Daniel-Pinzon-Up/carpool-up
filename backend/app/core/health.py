from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.db import engine
from app.core.rate_limit import exempt
from app.core.redis import redis_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
@exempt
async def live(request: Request) -> dict[str, str]:
    """El proceso responde."""
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "Alguna dependencia no responde"}})
@exempt
async def ready(request: Request) -> JSONResponse:
    """Base de datos con PostGIS y Redis disponibles."""
    checks: dict[str, Any] = {}
    try:
        async with engine.connect() as conn:
            checks["postgis"] = (await conn.execute(text("SELECT postgis_version()"))).scalar()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
    healthy = checks["database"] == "ok" and checks["redis"] == "ok"
    body = {"status": "ok" if healthy else "degraded", "checks": checks}
    return JSONResponse(body, 200 if healthy else 503)
