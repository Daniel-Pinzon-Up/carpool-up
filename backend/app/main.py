from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.core import health
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLogMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.modules.admin import console_router
from app.modules.admin import router as admin
from app.modules.audit import router as audit
from app.modules.auth import router as auth
from app.modules.bookings import router as bookings
from app.modules.chat import router as chat
from app.modules.live import router as live
from app.modules.notifications import router as notifications
from app.modules.pico_placa import router as pico_placa
from app.modules.places import router as places
from app.modules.ratings import router as ratings
from app.modules.routing import router as routing
from app.modules.safety import router as safety
from app.modules.search import router as search
from app.modules.semesters import router as semesters
from app.modules.settings import router as settings_module
from app.modules.stats import router as stats
from app.modules.tickets import router as tickets
from app.modules.trips import router as trips
from app.modules.users import router as users
from app.modules.vehicles import router as vehicles


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    arq_pool = getattr(app.state, "arq", None)
    if arq_pool is not None:
        await arq_pool.aclose()
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(json_output=settings.environment != "development")

    app = FastAPI(
        title="Carpool Universitario API",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.limiter = limiter

    # El ultimo middleware agregado es el mas externo.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Request-ID"],
    )
    app.add_middleware(RequestLogMiddleware)

    register_error_handlers(app)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(health.router)
    for public_router in (
        auth.router,
        users.router,
        notifications.router,
        vehicles.router,
        routing.router,
        trips.router,
        search.router,
        bookings.router,
        chat.router,
        tickets.router,
        ratings.router,
        stats.router,
        safety.router,
        safety.public_router,
        settings_module.router,
        semesters.router,
        places.router,
    ):
        api.include_router(public_router)
    for admin_router in (
        settings_module.admin_router,
        semesters.admin_router,
        places.admin_router,
        pico_placa.admin_router,
        audit.admin_router,
        admin.router,
        console_router.router,
        safety.admin_router,
    ):
        api.include_router(admin_router)
    app.include_router(api)
    # El WebSocket vive en /ws (Nginx lo enruta aparte de /api).
    app.include_router(live.router)
    return app


app = create_app()
