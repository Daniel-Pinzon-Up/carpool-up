from collections.abc import Callable
from typing import Any, cast

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

# Limite global por IP. Los endpoints sensibles (login, codigos, registro) declaran el suyo.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    storage_uri=_settings.rate_limit_storage or _settings.redis_url,
)


def exempt[F: Callable[..., Any]](func: F) -> F:
    """Excluye un endpoint del limite global. Envoltorio tipado de limiter.exempt."""
    untyped_exempt: Callable[[F], object] = limiter.exempt
    return cast(F, untyped_exempt(func))
