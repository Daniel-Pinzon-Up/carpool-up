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
| `UNAUTHORIZED` | 401 | 2 | Token ausente, inválido, vencido o de una sesión revocada. |
| `INVALID_CREDENTIALS` | 401 | 2 | Correo o contraseña incorrectos (misma respuesta si el correo no existe). |
| `ACCOUNT_LOCKED` | 429 | 2 | Demasiados intentos fallidos. `details.retry_after_seconds`. |
| `ACCOUNT_BLOCKED` | 403 | 2 | Cuenta bloqueada definitivamente. |
| `CODE_INVALID` | 400 | 2 | Código equivocado, vencido o agotado. |
| `CODE_RESEND_TOO_SOON` | 429 | 2 | Aún no se puede pedir otro código. `details.retry_after_seconds`. |
| `CHALLENGE_EXPIRED` | 400 | 2 | `challenge_id` inválido o vencido: hay que empezar de nuevo. |
| `EMAIL_NOT_INSTITUTIONAL` | 422 | 2 | El correo no termina en el sufijo permitido (`details.suffix`). |
| `EMAIL_TAKEN` | 409 | 2 | Ya existe una cuenta con ese correo. |
| `PASSWORD_TOO_SHORT` | 422 | 2 | Menos de `password_min_length` caracteres (`details.min_length`). |
| `PASSWORD_TOO_WEAK` | 422 | 2 | La contraseña coincide con el correo. |
| `TERMS_NOT_ACCEPTED` | 422 | 2 | Faltó aceptar términos o autorización de datos. |
| `LEGAL_DOCUMENTS_UNAVAILABLE` | 503 | 2 | No hay términos vigentes publicados. |
| `FILE_TOO_LARGE` | 413 | 2 | Supera `max_upload_mb` (`details.max_mb`). |
| `FILE_TYPE_NOT_ALLOWED` | 415 | 2 | El contenido no es JPG, PNG, WebP ni PDF. |
| `FILE_EMPTY` | 422 | 2 | Archivo vacío. |
| `FILE_INVALID` | 422 | 2 | La imagen está dañada. |
| `REFRESH_INVALID` | 401 | 2 | No hay cookie o la sesión ya no es válida. |
| `REFRESH_REUSED` | 401 | 2 | Se reutilizó un refresh viejo: se revocaron todas las sesiones. |
| `PAYMENT_NOTE_DRIVERS_ONLY` | 403 | 2 | Solo conductores guardan nota de pago. |
| `LEGAL_VERSION_NOT_CURRENT` | 422 | 2 | Se intentó aceptar una versión que no está vigente. |

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

### Autenticación y cuenta (paso 2)

El refresh token viaja en la cookie HttpOnly `cp_refresh` (ruta `/api/v1/auth`). Las respuestas de los pasos de autenticación usan el mismo esquema `AuthResult`:

| `result` | Trae | Siguiente paso |
|----------|------|----------------|
| `authenticated` | `access_token`, `expires_in`, `user` y la cookie | Usar el token en `Authorization: Bearer`. |
| `email_verification_required` | `challenge_id`, `email_hint`, `resend_after_seconds` | `POST /auth/verify-email` con el código del correo. |
| `two_factor_required` | igual | `POST /auth/2fa/verify`. |
| `password_reset_code_sent` | igual | `POST /auth/password/reset`. |

| Método y ruta | Acceso | Límite | Descripción |
|---------------|--------|--------|-------------|
| `POST /auth/register` | Público | 5/min | Multipart: `email`, `password`, `full_name`, `sex`, `program?`, `role` (passenger o driver), `doc_kind`, `preferred_language?`, `accept_terms`, `accept_data_policy`, `document` (archivo). |
| `POST /auth/login` | Público | 10/min | `{email, password, device_label?}`. |
| `POST /auth/verify-email` | Público | 10/min | `{challenge_id, code, device_label?}`. Pasa la cuenta a `pending_approval` y abre sesión. |
| `POST /auth/2fa/verify` | Público | 10/min | `{challenge_id, code, device_label?}`. |
| `POST /auth/codes/resend` | Público | 5/min | `{challenge_id}`. Respeta `auth_code_resend_seconds`. |
| `POST /auth/refresh` | Cookie | 30/min | Rota el refresh y devuelve un token de acceso nuevo. |
| `POST /auth/logout` | Cookie | | Revoca la sesión de la cookie. |
| `POST /auth/logout-others` | Sesión | | Revoca todas las sesiones salvo la actual. |
| `GET /auth/sessions` | Sesión | | Sesiones activas con `current`. |
| `POST /auth/password/forgot` | Público | 5/min | `{email}`. Misma respuesta exista o no la cuenta. |
| `POST /auth/password/reset` | Público | 10/min | `{challenge_id, code, new_password}`. Revoca todas las sesiones y vuelve a pedir 2FA. |
| `GET, PATCH /users/me` | Sesión (cualquier estado) | | Perfil propio con `document` y `pending_legal`. Se puede cambiar `program`, `preferred_language`, `theme_preference` y `payment_note` (solo conductores). |
| `GET, POST /users/me/documents` | Sesión (cualquier estado) | | Historial y carga de carnet o constancia (multipart: `kind`, `document`). |
| `POST /legal/accept` | Sesión | | `{document_ids}` de versiones vigentes pendientes. |

## Cabeceras

- `X-Request-ID`: se acepta del cliente o se genera, y se devuelve en cada respuesta para correlacionar logs.
- `Accept-Language`: el frontend la envía con el idioma activo (`es`, `en`, `pt`, `fr`).
