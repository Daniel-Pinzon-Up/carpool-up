"""Catalogo de parametros de negocio (seccion 5.4).

Aqui solo viven el tipo, la validacion y el valor inicial que carga el seed. El valor vigente
siempre se lee de la tabla system_settings y lo cambia el superadmin.
"""

from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, TypeAdapter, model_validator

DayCount = Annotated[int, Field(ge=1, le=200)]


class ServiceArea(BaseModel):
    """Caja que delimita Pamplona y alrededores. Solo se aceptan puntos dentro de ella."""

    min_lat: float = Field(ge=-90, le=90)
    max_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lon: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def check_order(self) -> "ServiceArea":
        if self.min_lat >= self.max_lat or self.min_lon >= self.max_lon:
            raise ValueError("min values must be lower than max values")
        return self

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    adapter: TypeAdapter[Any]
    default: Any
    description: str


def _define(key: str, type_: Any, default: Any, description: str) -> SettingDefinition:
    return SettingDefinition(key, TypeAdapter(type_), default, description)


_SERIES_OPTIONS = Annotated[list[DayCount | Literal["semester"]], Field(min_length=1)]
_SUBSCRIPTION_OPTIONS = Annotated[list[DayCount | Literal["series"]], Field(min_length=1)]
_OPTIONAL_PESOS = NonNegativeInt | None

DEFINITIONS: dict[str, SettingDefinition] = {
    d.key: d
    for d in [
        _define(
            "cancel_free_hours",
            NonNegativeInt,
            2,
            "Horas de antelacion para que el pasajero cancele sin penalizacion.",
        ),
        _define(
            "driver_late_minutes",
            PositiveInt,
            15,
            "Minutos de retraso del conductor tras los que el pasajero cancela sin penalizacion.",
        ),
        _define(
            "no_show_wait_minutes",
            PositiveInt,
            10,
            "Minutos de espera antes de poder marcar no-show.",
        ),
        _define("no_show_limit", PositiveInt, 3, "No-shows que generan suspension de reservas."),
        _define("no_show_window_days", PositiveInt, 30, "Ventana de conteo de no-shows."),
        _define("no_show_ban_days", PositiveInt, 7, "Dias de suspension de reservas."),
        _define(
            "series_window_options_days",
            _SERIES_OPTIONS,
            [15, 28, "semester"],
            "Ventanas disponibles al publicar una serie.",
        ),
        _define(
            "subscription_options_days",
            _SUBSCRIPTION_OPTIONS,
            [8, 15, "series"],
            "Rangos que puede elegir el pasajero al unirse a una serie.",
        ),
        _define(
            "search_radius_meters",
            Annotated[int, Field(ge=50, le=5000)],
            500,
            "Distancia maxima a la ruta para considerar un viaje en la busqueda.",
        ),
        _define(
            "search_time_window_minutes",
            Annotated[int, Field(ge=5, le=360)],
            60,
            "Tolerancia horaria de la busqueda.",
        ),
        _define(
            "cost_per_km_car",
            _OPTIONAL_PESOS,
            None,
            "Costo por kilometro en carro (COP) para estimar el precio. Lo define el superadmin.",
        ),
        _define(
            "cost_per_km_motorcycle",
            _OPTIONAL_PESOS,
            None,
            "Costo por kilometro en moto (COP) para estimar el precio. Lo define el superadmin.",
        ),
        _define(
            "max_price_per_seat",
            _OPTIONAL_PESOS,
            None,
            "Tope de precio por puesto (COP). Lo define el superadmin.",
        ),
        _define("waitlist_offer_minutes", PositiveInt, 15, "Vigencia de la oferta de cupo."),
        _define("rating_window_days", PositiveInt, 7, "Plazo para calificar tras el viaje."),
        _define("chat_retention_days", PositiveInt, 30, "Retencion del chat tras el viaje."),
        _define(
            "pending_request_hours",
            PositiveInt,
            24,
            "Horas tras las que vence una solicitud sin respuesta.",
        ),
        _define(
            "revalidation_days",
            PositiveInt,
            30,
            "Dias desde el inicio del semestre para revalidar el carnet.",
        ),
        _define(
            "password_min_length",
            Annotated[int, Field(ge=8, le=64)],
            10,
            "Longitud minima de la contrasena.",
        ),
        _define(
            "login_max_attempts",
            Annotated[int, Field(ge=3, le=20)],
            5,
            "Intentos fallidos de contrasena antes del bloqueo temporal.",
        ),
        _define(
            "login_lockout_minutes",
            PositiveInt,
            15,
            "Minutos de bloqueo tras agotar los intentos de contrasena.",
        ),
        _define(
            "auth_code_minutes",
            Annotated[int, Field(ge=1, le=60)],
            10,
            "Vigencia de los codigos enviados por correo.",
        ),
        _define(
            "auth_code_max_attempts",
            Annotated[int, Field(ge=1, le=10)],
            5,
            "Intentos para escribir un codigo antes de que deje de servir.",
        ),
        _define(
            "auth_code_resend_seconds",
            Annotated[int, Field(ge=10, le=600)],
            60,
            "Espera minima entre dos envios de codigo al mismo usuario.",
        ),
        _define(
            "max_upload_mb",
            Annotated[int, Field(ge=1, le=20)],
            5,
            "Tamano maximo de documentos e imagenes subidos.",
        ),
        _define(
            "max_trip_stops",
            Annotated[int, Field(ge=0, le=10)],
            5,
            "Paradas intermedias permitidas entre origen y destino.",
        ),
        _define(
            "service_area",
            ServiceArea,
            {"min_lat": 7.33, "max_lat": 7.43, "min_lon": -72.70, "max_lon": -72.59},
            "Caja geografica de Pamplona y alrededores donde se aceptan puntos.",
        ),
    ]
}
