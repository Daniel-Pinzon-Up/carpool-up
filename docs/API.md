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

Los códigos de negocio se documentan aquí en el paso que los introduce.

| code | HTTP | Paso | Cuándo |
|------|------|------|--------|
| `ACCOUNT_NOT_ACTIVE` | 403 | 1 | La cuenta no está en estado `active`. `details.status` indica el estado. |
| `INVALID_CURSOR` | 400 | 1 | El cursor de paginación no es válido. |
| `SETTING_UNKNOWN` | 404 | 1 | La clave del parámetro no existe. |
| `SETTING_INVALID` | 422 | 1 | El valor no cumple el tipo del parámetro. `details.errors` lista los problemas. |
| `SEMESTER_OVERLAP` | 409 | 1 | Las fechas se cruzan con otro semestre (`details.conflicts_with`). |
| `SEMESTER_INVALID_DATES` | 422 | 1 | Fin antes del inicio o plazo de revalidación fuera del semestre. |
| `SEMESTER_NAME_TAKEN` | 409 | 1 | Ya existe un semestre con ese nombre. |
| `SEMESTER_IN_USE` | 409 | 1 | El semestre tiene registros asociados y no se puede borrar. |
| `NO_CURRENT_SEMESTER` | 404 | 1 | Ningún semestre contiene la fecha de hoy. |
| `PLACE_OUT_OF_AREA` | 422 | 1 | El punto está fuera de `service_area`. |
| `PLACE_NAME_TAKEN` | 409 | 1 | Ya existe un lugar con ese nombre y tipo. |
| `PICO_PLACA_INVALID_DATES` | 422 | 1 | `valid_to` queda antes de `valid_from`. |
| `LEGAL_VERSION_EXISTS` | 409 | 1 | Esa versión del documento ya está publicada. |

## Endpoints

### Salud (paso 0)

| Método y ruta | Descripción |
|---------------|-------------|
| `GET /health/live` | El proceso responde. Sin límite de peticiones. |
| `GET /health/ready` | Base de datos con PostGIS y Redis disponibles. Responde 503 con `status: degraded` si alguno falla. |

### Configuración y catálogos (paso 1)

Autenticación: `Authorization: Bearer <token de acceso>`. Todo lo que está bajo `/admin` exige rol **superadmin** con cuenta activa, y cada cambio queda en la auditoría con el valor antes y después.

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /meta/settings/public` | Público | Valor vigente de todos los parámetros de negocio. |
| `GET /meta/semesters/current` | Público | Semestre que contiene la fecha de hoy (hora de Bogotá). |
| `GET /places?kind=` | Público | Catálogo de puntos activos (campus, sectores y referencias). |
| `POST /places/custom` | Cuenta activa | Pin libre en el mapa; solo lo ve su autor. |
| `GET /legal/current?language=` | Público | Términos y política de datos vigentes; si falta el idioma se sirve el español. |
| `GET /admin/settings` | Superadmin | Todos los parámetros con descripción, fecha y autor del último cambio. |
| `PATCH /admin/settings/{key}` | Superadmin | Cambia un parámetro: `{"value": ...}`. |
| `GET, POST /admin/semesters` | Superadmin | Listar y crear semestres. |
| `PATCH, DELETE /admin/semesters/{id}` | Superadmin | Editar y borrar un semestre. |
| `GET, POST /admin/places` | Superadmin | Listar (incluye inactivos) y crear puntos del catálogo. |
| `PATCH, DELETE /admin/places/{id}` | Superadmin | Editar y desactivar un punto. |
| `GET, POST /admin/pico-placa` | Superadmin | Listar y crear reglas. |
| `PATCH, DELETE /admin/pico-placa/{id}` | Superadmin | Editar y borrar una regla. |
| `GET, POST /admin/legal` | Superadmin | Listar versiones y publicar una nueva. |
| `GET /admin/audit` | Superadmin | Auditoría, más reciente primero. Filtros: `entity`, `entity_id`, `actor_id`, `action`, `since`, `until`. Paginación con `limit` y `cursor` (`next_cursor` en la respuesta). |

## Cabeceras

- `X-Request-ID`: se acepta del cliente o se genera, y se devuelve en cada respuesta para correlacionar logs.
- `Accept-Language`: el frontend la envía con el idioma activo (`es`, `en`, `pt`, `fr`).
