# API de Carpool Universitario

- Prefijo: `/api/v1`
- Especificación OpenAPI: `/api/v1/openapi.json`
- Documentación interactiva: `/api/v1/docs` (en desarrollo, `http://localhost:8000/api/v1/docs`)

## Formato de error

Todas las respuestas de error usan el mismo formato. `code` es estable y la interfaz lo traduce (`errors.<code>` en `es.json`).

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
| `FILE_TOO_LARGE` | 413 | 2 | Supera `max_upload_mb` (`details.max_mb`). |
| `FILE_TYPE_NOT_ALLOWED` | 415 | 2 | El contenido no es JPG, PNG, WebP ni PDF. |
| `FILE_EMPTY` | 422 | 2 | Archivo vacío. |
| `FILE_INVALID` | 422 | 2 | La imagen está dañada. |
| `REFRESH_INVALID` | 401 | 2 | No hay cookie o la sesión ya no es válida. |
| `REFRESH_REUSED` | 401 | 2 | Se reutilizó un refresh viejo: se revocaron todas las sesiones. |
| `PAYMENT_NOTE_DRIVERS_ONLY` | 403 | 2 | Solo conductores guardan nota de pago. |
| `APPROVAL_NOT_PENDING` | 409 | 3 | El elemento ya fue revisado. |
| `LICENSE_EXPIRED` | 422 | 3 | La licencia está vencida (al subirla o al aprobarla). |
| `LICENSE_DRIVERS_ONLY` | 403 | 3 | Solo los conductores suben licencia. |
| `FILE_NOT_FOUND` | 404 | 3 | El archivo no existe en el almacenamiento. |
| `VEHICLES_DRIVERS_ONLY` | 403 | 4 | Solo los conductores registran vehículos. |
| `VEHICLE_PLATE_TAKEN` | 409 | 4 | La placa ya está registrada en un vehículo no borrado. |
| `VEHICLE_INVALID` | 422 | 4 | Una edición rompe las reglas del tipo (`details.rule`). |
| `PUBLISH_NOT_ALLOWED` | 403 | 4 | El conductor no cumple los requisitos para publicar (`details.blockers`). |
| `PLACE_NOT_FOUND` | 404 | 5 | El lugar no existe, está inactivo o es un pin de otro usuario (`details.index`). |
| `TOO_MANY_STOPS` | 422 | 5 | Más paradas intermedias que `max_trip_stops` (`details.max_stops`). |
| `ROUTE_NOT_FOUND` | 422 | 5 | No hay ruta por carretera entre los puntos. |
| `ROUTING_UNAVAILABLE` | 503 | 5 | OSRM no responde o no está levantado. |
| `DEPARTURE_TOO_SOON` | 422 | 6 | La salida no cumple la antelación mínima (`details.min_lead_minutes`). |
| `DEPARTURE_TOO_FAR` | 422 | 6 | Viaje puntual más allá de `trip_max_days_ahead` (`details.max_days`). |
| `SEATS_INVALID` | 422 | 6 | Más puestos que capacidad - 1 (`details.max_seats`). |
| `PRICE_ABOVE_MAX` | 422 | 6 | Aporte por encima de `max_price_per_seat` (`details.max`). |
| `VEHICLE_INACTIVE` | 422 | 6 | El vehículo está inactivo. |
| `WOMEN_ONLY_FEMALE_DRIVERS` | 403 | 6 | Solo conductoras publican viajes solo para mujeres. |
| `PICO_PLACA_RESTRICTED` | 422 | 6 | El vehículo tiene pico y placa ese día (`details.date`). |
| `TRIP_OVERLAP` | 409 | 6 | El conductor ya tiene un viaje a esa hora (`details.dates`). |
| `TRIP_NOT_EDITABLE` | 409 | 6 | El viaje no está programado o ya pasó el corte de edición. |
| `VEHICLE_HAS_TRIPS` | 409 | 6 | El vehículo tiene viajes programados o en curso. |
| `INVALID_RANGE` | 422 | 6 | Rango de fechas inválido o mayor a 200 días. |

## Endpoints

### Salud (paso 0)

| Método y ruta | Descripción |
|---------------|-------------|
| `GET /health/live` | El proceso responde. Sin límite de peticiones. |
| `GET /health/ready` | Base de datos con PostGIS y Redis disponibles. Responde 503 con `status: degraded` si alguno falla. |

### Configuración y catálogos (paso 1)

Autenticación: `Authorization: Bearer <token de acceso>`. Las rutas `/admin` de esta sección exigen rol **superadmin** con cuenta activa (las de aprobaciones, emergencias y el panel del paso 12 admiten también al administrador), y cada cambio queda en la auditoría con el valor antes y después.

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /meta/settings/public` | Público | Valor vigente de todos los parámetros de negocio. |
| `GET /meta/semesters/current` | Público | Semestre que contiene la fecha de hoy (hora de Bogotá). |
| `GET /places?kind=` | Público | Catálogo de puntos activos (campus, sectores y referencias). |
| `POST /places/custom` | Cuenta activa | Pin libre en el mapa; solo lo ve su autor. |
| `GET /admin/settings` | Superadmin | Todos los parámetros con descripción, fecha y autor del último cambio. |
| `PATCH /admin/settings/{key}` | Superadmin | Cambia un parámetro: `{"value": ...}`. |
| `GET, POST /admin/semesters` | Superadmin | Listar y crear semestres. |
| `PATCH, DELETE /admin/semesters/{id}` | Superadmin | Editar y borrar un semestre. |
| `GET, POST /admin/places` | Superadmin | Listar (incluye inactivos) y crear puntos del catálogo. |
| `PATCH, DELETE /admin/places/{id}` | Superadmin | Editar y desactivar un punto. |
| `GET, POST /admin/pico-placa` | Superadmin | Listar y crear reglas. |
| `PATCH, DELETE /admin/pico-placa/{id}` | Superadmin | Editar y borrar una regla. |
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
| `POST /auth/register` | Público | 5/min | Multipart: `email`, `password`, `full_name`, `sex`, `program?`, `role` (passenger o driver), `doc_kind`, `accept_terms`, `accept_data_policy`, `document` (archivo). |
| `POST /auth/login` | Público | 10/min | `{email, password, device_label?}`. |
| `POST /auth/verify-email` | Público | 10/min | `{challenge_id, code, device_label?}`. Pasa la cuenta a `pending_approval` y abre sesión. |
| `POST /auth/2fa/verify` | Público | 10/min | `{challenge_id, code, device_label?}`. |
| `POST /auth/codes/resend` | Público | 5/min | `{challenge_id}`. Respeta `auth_code_resend_seconds`. |
| `POST /auth/refresh` | Cookie | 30/min por sesión y 300/min por IP | Rota el refresh y devuelve un token de acceso nuevo. Presentar uno ya usado revoca todas las sesiones (`REFRESH_REUSED`). |
| `POST /auth/logout` | Cookie | | Revoca la sesión de la cookie. |
| `POST /auth/logout-others` | Sesión | | Revoca todas las sesiones salvo la actual. |
| `GET /auth/sessions` | Sesión | | Sesiones activas con `current`. |
| `POST /auth/password/forgot` | Público | 5/min | `{email}`. Misma respuesta exista o no la cuenta. |
| `POST /auth/password/reset` | Público | 10/min | `{challenge_id, code, new_password}`. Revoca todas las sesiones y vuelve a pedir 2FA. |
| `GET, PATCH /users/me` | Sesión (cualquier estado) | | Perfil propio con `document`, `license` y `booking_ban_until`. Se puede cambiar `program` y `payment_note` (solo conductores). |
| `GET, POST /users/me/documents` | Sesión (cualquier estado) | | Historial y carga de carnet o constancia (multipart: `kind`, `document`). |
| `POST /users/me/delete` | Sesión | | `{password}`. Elimina la cuenta propia (Ley 1581): anonimiza nombre, correo, foto, programa y contraseña; borra documentos, licencia, contactos de confianza y avisos; cancela sus viajes y reservas futuros con aviso; cierra todas sus sesiones. Conserva los registros operativos. 204. Errores `PASSWORD_INCORRECT` (422), `ACCOUNT_DELETE_TRIP_IN_PROGRESS` y `ACCOUNT_DELETE_NOT_ALLOWED` (superadmin) (409). |

### Aprobaciones, licencias y notificaciones (paso 3)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /admin/approvals?type=&status=&limit=&cursor=` | Admin o superadmin | Cola en orden de llegada. `type`: `identity` (por defecto) o `license`; `status`: `pending` por defecto. |
| `GET /admin/approvals/counts` | Admin o superadmin | Pendientes por tipo. |
| `GET /admin/approvals/{id}` | Admin o superadmin | Detalle de un elemento. |
| `POST /admin/approvals/{id}/approve` | Admin o superadmin | `{sex?}` para corregir el sexo en carnets. Activa la cuenta si estaba en `pending_approval`. |
| `POST /admin/approvals/{id}/reject` | Admin o superadmin | `{reason}` (5 a 300 caracteres); el usuario lo ve. |
| `GET /admin/files/{id}` | Admin o superadmin | Archivo del carnet, constancia o licencia, sin caché. |
| `POST /admin/admins` | Superadmin | `{email, full_name, sex, password}`. |
| `PATCH /admin/users/{id}/role` | Superadmin | `{role}`: `passenger`, `driver` o `admin`. |
| `GET /users/me/documents/{id}/file` | Dueño | Archivo propio. |
| `GET, PUT /users/me/license` | Dueño (PUT solo conductores) | Multipart: `expires_on`, `document`. |
| `GET /users/me/license/file` | Dueño | Archivo propio. |
| `GET /notifications?unread_only=&limit=&cursor=` | Sesión | Bandeja propia, más reciente primero. |
| `GET /notifications/unread-count` | Sesión | `{unread}`. |
| `POST /notifications/{id}/read`, `POST /notifications/read-all` | Sesión | Marcar como leídas. |

Tipos de notificación de este paso: `document_approved`, `document_rejected` (`reason`), `document_expired` (`semester`, `deadline`), `license_approved`, `license_rejected` (`reason`), `account_revalidation_required` (`semester`), `role_changed` (`role`).

### Vehículos (paso 4)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /vehicles` | Conductor activo | Vehículos propios no borrados (incluye la placa). |
| `POST /vehicles` | Conductor activo | `{type, plate, brand, model, color, year, capacity, luggage_space}`. |
| `PATCH /vehicles/{id}` | Dueño | `{brand?, model?, color?, year?, capacity?, luggage_space?, is_active?}`. |
| `DELETE /vehicles/{id}` | Dueño | Borrado lógico. |
| `PUT /vehicles/{id}/photo` | Dueño | Multipart `photo` (JPG, PNG o WebP). |
| `GET /vehicles/{id}/photo` | Sesión | Foto del vehículo. |

`GET /users/me` incluye `can_publish` y `publish_blockers` (`account_not_active`, `license_missing`, `license_pending`, `license_rejected`, `license_expired`, `no_active_vehicle`).

### Rutas (paso 5)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `POST /routing/preview` | Usuario activo, 30 por minuto | Ruta, distancia, ETA por parada y aporte sugerido. |

Cuerpo:

```json
{
  "points": [{"place_id": "uuid"}, {"lat": 7.376, "lon": -72.646}, {"place_id": "uuid"}],
  "departs_at": "2026-10-06T07:30:00-05:00",
  "vehicle_type": "car",
  "seats": 3
}
```

`points` tiene origen, paradas intermedias y destino (al menos 2). Cada punto lleva `place_id` o `lat` y `lon`, nunca ambos. `departs_at`, `vehicle_type` y `seats` son opcionales.

Respuesta: `geometry` (GeoJSON `[[lon, lat], ...]`), `distance_m`, `duration_s` (de OSRM), `points` (cada uno con `eta_offset_s` y `eta` si hubo hora de salida), `pricing_configured`, `suggested_price` y `max_price_per_seat`.

### Viajes (paso 6)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `POST /trips` | Conductor que puede publicar, 20 por minuto | Viaje puntual. |
| `GET /trips/mine?scope=upcoming\|history&limit&cursor` | Conductor | Viajes propios, paginados por salida. |
| `GET /trips/{id}` | Usuario activo | Detalle con geometría, paradas con ETA, reglas, vehículo y conductor. Los demás solo ven viajes programados o en curso; la placa solo la ve el conductor. |
| `PATCH /trips/{id}` | Dueño | `{place_ids?, departs_at?, vehicle_id?, seats?, price_per_seat?, rules?}` hasta el corte de edición. |
| `POST /trips/{id}/cancel` | Dueño | `{reason}`. |
| `POST /trips/{id}/duplicate` | Dueño | `{departs_at}`. Publica una copia. |
| `GET /vehicles/{id}/pico-placa?from&to` | Dueño | Fechas del rango en que el vehículo tiene pico y placa. |

Viaje puntual:

```json
{
  "place_ids": ["origen", "parada", "destino"],
  "departs_at": "2026-10-06T07:30:00-05:00",
  "vehicle_id": "uuid",
  "seats": 3,
  "price_per_seat": 2000,
  "rules": [{"kind": "pets", "value": "not_allowed"}, {"kind": "custom", "value": "Espero 5 minutos"}]
}
```


Reglas: `women_only`, `pets`, `luggage`, `smoking`, `music` con `allowed` o `not_allowed`, y `custom` con texto libre.

### Búsqueda (paso 7)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /search/trips` | Usuario activo, 60 por minuto | Viajes programados que pasan cerca del origen y destino pedidos. |

Parámetros: `origin_place_id` u `origin_lat` y `origin_lon`; lo mismo para el destino; `date` (`YYYY-MM-DD`), `time` (`HH:MM`, hora de Pamplona), `seats` (1 a 7) y las preferencias booleanas `pets`, `luggage`, `no_smoking`, `music` y `women_only` (esta última solo para usuarias).

Cada resultado trae `trip_id`, `departs_at`, `arrives_at`, `origin`, `destination`, `price_per_seat`, `seats_available`, `pickup` y `dropoff` (`kind` `stop` o `route`, `name`, `lat`, `lon`, `eta`, `walk_m`), `minutes_from_requested`, `driver` (`id`, `full_name`, `rating`, `trips_as_driver`), `vehicle` sin placa y `rules`. Error propio: `SEARCH_IN_PAST` (422).

### Reservas, suscripciones y lista de espera (paso 8)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `POST /trips/{id}/bookings` | Pasajero, 20 por minuto | `{seats, pickup_place_id, dropoff_place_id, preferences}`. Queda `requested` sin apartar cupo. |
| `GET /trips/{id}/bookings` | Conductor dueño | Todas las reservas del viaje con el punto de encuentro de cada pasajero. |
| `GET /bookings/mine?scope=upcoming\|history&limit&cursor` | Pasajero | Reservas propias por hora de recogida. |
| `GET /bookings/inbox` | Conductor | `{bookings, cancellations}` por decidir. |
| `GET /bookings/{id}` | Pasajero o conductor del viaje | Detalle; placa y nota de pago solo con la reserva aceptada. |
| `POST /bookings/{id}/accept` | Conductor dueño | Acepta con el viaje bloqueado. |
| `POST /bookings/{id}/reject` | Conductor dueño | `{reason?}`. |
| `POST /bookings/{id}/cancel` | Pasajero | `{reason?}`. Directa o solicitud de cancelación tardía (motivo obligatorio). |
| `POST /bookings/{id}/cancellation/accept`, `/reject` | Conductor dueño | Decide la cancelación tardía de esa reserva (`cancel_requested`). |

Estados de la reserva: `requested`, `accepted`, `rejected`, `cancel_requested`, `cancelled_by_passenger`, `cancelled_by_driver`, `auto_cancelled_late`, `auto_cancelled_pico_placa`, `expired`, `no_show`, `completed`. Cada respuesta trae `free_cancel`: si es falso, cancelar crea una solicitud al conductor.

Errores propios: `TRIP_FULL`, `TRIP_NOT_BOOKABLE`, `BOOKING_EXISTS`, `BOOKING_OVERLAP`, `BOOKING_OWN_TRIP`, `WOMEN_ONLY_TRIP`, `BOOKING_SUSPENDED`, `PREFERENCES_CONFLICT`, `POINTS_OFF_ROUTE`, `BOOKING_NOT_PENDING`, `BOOKING_NOT_CANCELLABLE`, `CANCELLATION_PENDING`, `CANCEL_REASON_REQUIRED`, `CANCELLATION_NOT_PENDING`. Al editar viajes: `SEATS_BELOW_BOOKED` y `WOMEN_ONLY_CONFLICT`.

El detalle del viaje (`GET /trips/{id}`) agrega `seats_available`, `pending_requests` (conductor), `passengers`, `payment_note` y `my_booking`. La búsqueda descuenta los puestos aceptados.

### Chat y tiempo real (paso 9)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /conversations` | Usuario activo | Chats propios (uno por viaje; su id es el id del viaje) con último mensaje, sin leer y si está cerrado. |
| `GET /conversations/unread` | Usuario activo | `{unread, conversations}` para el contador de la navegación. |
| `GET /conversations/{id}` | Miembro | Detalle con miembros (id, nombre, si es el conductor). |
| `GET /conversations/{id}/messages?before&after&limit` | Miembro | Historial cronológico. `before` pagina hacia atrás; `after` trae lo nuevo desde el último visto. |
| `POST /conversations/{id}/messages` | Miembro, 30 por minuto | `{body}` (1 a 1000 caracteres). Respaldo HTTP del envío. Error `CONVERSATION_CLOSED`. |
| `POST /conversations/{id}/read` | Miembro | Marca el chat y su aviso de mensajes nuevos como leídos. |
| `GET /notifications/unread-count` | Usuario | Contador de avisos sin leer. |

El detalle del viaje agrega `chat_id` (el chat grupal) para el conductor y los pasajeros aceptados.

**WebSocket `/ws`** (detrás de Nginx en el mismo origen; `ws://` en desarrollo a través del proxy de `ng serve`).

1. El cliente abre la conexión y envía `{"type": "auth", "token": "<access token>"}` en menos de 10 s.
2. El servidor responde `{"type": "ready", "conversations": [...]}`.
3. Cliente a servidor: `ping`, `chat.send {conversation_id, body, client_id}`, `chat.read {conversation_id}` y `typing {conversation_id}`.
4. Servidor a cliente:
   - `pong`;
   - `notification {notification}`, `notification.read {id}` y `notification.read_all`;
   - `message {message}`, `typing {conversation_id, user_id, name}` y `conversation.joined {conversation_id}`;
   - `chat.ack {client_id, message}` y `error {code, client_id}` (`NOT_FOUND`, `RATE_LIMITED`, `MESSAGE_INVALID`, `CONVERSATION_CLOSED`, `BAD_REQUEST`).
5. Cierres: `4401` sin autenticación válida, `4001` token vencido (renovar y reconectar). Un origen no permitido se rechaza con HTTP 403.

### Ciclo del viaje y seguridad (paso 10)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `POST /trips/{id}/start` | Conductor dueño | Inicia el viaje. Errores `TRIP_START_TOO_EARLY`, `TRIP_START_TOO_LATE`, `TRIP_NOT_STARTABLE`, `PICO_PLACA_RESTRICTED`. |
| `POST /bookings/{id}/boarded` | Conductor dueño | Marca que el pasajero subió (viaje en curso). |
| `POST /bookings/{id}/no-show` | Conductor dueño | Desde la salida más la espera. Puede crear una suspensión automática. `NO_SHOW_TOO_EARLY`. |
| `POST /trips/{id}/finish` | Conductor dueño | Emite los tickets. `PASSENGERS_UNMARKED`. |
| `GET /tickets/mine?role=passenger\|driver&trip_id` | Usuario activo | Tickets propios o de los viajes que conduce. |
| `POST /tickets/{id}/paid` | Conductor del viaje | `{paid}`: confirma (o desmarca) que recibió el aporte. |
| `GET /trips/{id}/location` | Participante | Última ubicación del conductor (nula si no hay). |
| `POST /trips/{id}/share-links` | Participante, 10 por minuto | `{token, path, expires_at}`; el token se muestra una sola vez. |
| `GET /public/share/{token}` | Público, 60 por minuto | Ruta, paradas, vehículo con placa, hora estimada y ubicación. Sin datos personales. |
| `POST /trips/{id}/emergency` | Participante, 5 por minuto | `{lat?, lon?, note?}` → `{emergency, phone}`. Alerta en vivo a los administradores. |
| `GET /me/trusted-contacts`, `POST`, `PATCH /{id}`, `DELETE /{id}` | Usuario activo | `{name, phone, relationship?}`, máximo 5. `TRUSTED_CONTACTS_LIMIT`. |
| `GET /admin/emergencies?include_handled` | Administrador | Abiertas primero. |
| `POST /admin/emergencies/{id}/handle` | Administrador | `{resolution}`. Queda en la auditoría. `EMERGENCY_HANDLED`. |

WebSocket: el conductor envía `location.update {trip_id, lat, lon, accuracy?, heading?, speed?}`. Los participantes reciben `location`, `trip.started` y `trip.finished`; los administradores, `emergency` y `emergency.handled`.

### Calificaciones, historial y estadísticas (paso 11)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /ratings/pending` | Usuario activo | Personas que aún puede calificar, con los criterios y el cierre del plazo. |
| `POST /trips/{id}/ratings` | Participante | `{target_id, scores: {criterio: 1..5}, comment?}`. Errores `RATING_NOT_OPEN`, `RATING_WINDOW_CLOSED`, `RATING_TARGET_INVALID`, `RATING_CRITERIA_INVALID`, `RATING_EXISTS`. |
| `GET /users/{id}/ratings?limit&cursor` | Usuario activo | Calificaciones recibidas, sin autor; los comentarios ocultos salen sin texto. |
| `GET /users/{id}/rating-summary` | Usuario activo | Promedio general, por criterio, número de calificaciones y viajes hechos. |
| `GET /history/passenger?limit&cursor` | Pasajero | Viajes pasados con estado, ticket y estado de la calificación. |
| `GET /history/driver?limit&cursor` | Conductor | Viajes pasados con pasajeros, aportes y calificaciones pendientes. |
| `GET /stats/passenger` | Pasajero | Viajes, aporte total, cancelaciones, ausencias, lugares de salida y meses. |
| `GET /stats/driver` | Conductor | Viajes, pasajeros, ocupación, aportes, cancelaciones, calificación y meses. |

Criterios: conductor `punctuality`, `safe_driving`, `courtesy`, `cleanliness`; pasajero `punctuality`, `courtesy`, `compliance`. En la búsqueda, `driver.rating` y `driver.trips_as_driver` se calculan con consultas agrupadas sobre viajes, reservas y calificaciones.

### Panel de administración (paso 12)

| Método y ruta | Acceso | Descripción |
|---------------|--------|-------------|
| `GET /admin/stats?days` | Administrador | Indicadores de los últimos `days` (7 a 180, por defecto 30). |
| `GET /admin/users?q&role&status&limit&cursor` | Administrador | Búsqueda por nombre o correo. |
| `GET /admin/users/{id}` | Administrador | Ficha: documentos, métricas, suspensiones y suspensión de reservas vigente. |
| `POST /admin/users/{id}/suspend` | Administrador | `{reason, days?}` (1 a 365; sin `days`, hasta reactivarla). `USER_STATUS_INVALID`. |
| `POST /admin/users/{id}/reinstate` | Administrador | `{reason?}`. |
| `POST /admin/users/{id}/block` | Administrador | `{reason}`. Cierra sus sesiones. |
| `POST /admin/users/{id}/lift-ban` | Administrador | `{reason?}`. Levanta la suspensión de reservas por ausencias. `SUSPENSION_ENDED`. |
| `GET /admin/trips?status&day&q&limit&cursor` | Administrador | Viajes con conductor, ocupación y emergencias abiertas. |
| `GET /admin/trips/{id}` | Administrador | Detalle con reservas y emergencias. |
| `POST /admin/trips/{id}/cancel` | Administrador | `{reason}`. Solo viajes programados (`TRIP_NOT_EDITABLE`). |
| `GET /admin/trips/{id}/messages` | Administrador | Chat del viaje. Cada lectura queda en la auditoría. |
| `POST /admin/messages/{id}/hide` | Administrador | `{hidden}`. |
| `GET /admin/ratings?hidden&limit&cursor` | Administrador | Calificaciones con comentario. |
| `POST /admin/ratings/{id}/hide` | Administrador | `{hidden}`. |

"Administrador" incluye al superadmin. Sobre otro administrador solo actúa el superadmin, y nadie sobre un superadmin ni sobre sí mismo (`FORBIDDEN`). Las entradas de `GET /admin/audit` traen `actor_name`.

## Límites de peticiones

- Límite general por IP: `RATE_LIMIT_DEFAULT` (120 por minuto por defecto). Los endpoints de autenticación declaran el suyo (columna Límite).
- La renovación de sesión se cuenta **por sesión**: en el campus muchas personas salen por la misma IP pública.
- La IP es la que ve Nginx: reemplaza `X-Forwarded-For`, así un cliente no puede inventar otra para esquivar los límites.
- Al superarlo se responde 429 con `RATE_LIMITED`.

## Autorización por propiedad

Además del rol, cada ruta que recibe un id comprueba que el recurso sea de quien lo pide (o de su viaje). Una prueba recorre todas esas rutas como un extraño y exige 403 o 404; una ruta nueva sin clasificar hace fallar la prueba (`tests/test_ownership.py`).

## Cabeceras

- `X-Request-ID`: se acepta del cliente o se genera, y se devuelve en cada respuesta para correlacionar logs.
