# API de Carpool Universitario

- Prefijo: `/api/v1`
- Especificación OpenAPI: `/api/v1/openapi.json`
- Documentación interactiva: `/api/v1/docs` (en desarrollo, `http://localhost:8000/api/v1/docs`)

## Formato de error

Todas las respuestas de error usan el mismo formato. `code` es estable y la interfaz lo traduce (`errors.<code>` en los archivos de idioma).

```json
{ "code": "TRIP_FULL", "message": "No seats left", "details": { "available": 0 } }
```

| code | HTTP | Cuándo |
|------|------|--------|
| `VALIDATION_ERROR` | 422 | La petición no cumple el esquema. `details.fields` lista `loc`, `type` y `msg` de cada campo. |
| `NOT_FOUND` | 404 | El recurso o la ruta no existen. |
| `UNAUTHORIZED` | 401 | Falta autenticación o no es válida. |
| `FORBIDDEN` | 403 | El rol o la propiedad del recurso no lo permiten. |
| `RATE_LIMITED` | 429 | Se superó el límite de peticiones. |
| `INTERNAL_ERROR` | 500 | Error inesperado. Nunca expone detalles internos. |

Los códigos de negocio (`TRIP_FULL`, `PICO_PLACA_RESTRICTED`...) se documentan aquí en el paso que los introduce.

## Endpoints

### Salud (paso 0)

| Método y ruta | Descripción |
|---------------|-------------|
| `GET /health/live` | El proceso responde. Sin límite de peticiones. |
| `GET /health/ready` | Base de datos con PostGIS y Redis disponibles. Responde 503 con `status: degraded` si alguno falla. |

## Cabeceras

- `X-Request-ID`: se acepta del cliente o se genera, y se devuelve en cada respuesta para correlacionar logs.
- `Accept-Language`: el frontend la envía con el idioma activo (`es`, `en`, `pt`, `fr`).
