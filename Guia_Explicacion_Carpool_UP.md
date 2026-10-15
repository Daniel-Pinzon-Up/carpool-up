# Guía de explicación técnica de Carpool UP

Documento de estudio que acompaña a `Presentacion_Tecnica_Carpool_UP.pptx`. Explica con más detalle la arquitectura, cómo se conectan las piezas del backend, cómo se habla con la base de datos, los endpoints más importantes, el recorrido de las peticiones principales y las preguntas que puede hacer el docente.

Todo lo que aparece aquí sale del código de la rama `main` del repositorio (revisado el 14 y 15 de octubre de 2026). Los nombres de archivos, funciones, tablas y rutas son los reales. Los datos de los ejemplos (identificadores, nombres de lugares) son ficticios.

---

## 1. Qué es y qué problema resuelve

Carpool UP es una aplicación web para que la comunidad de la Universidad de Pamplona comparta trayectos en carro o moto dentro de Pamplona. Resuelve tres problemas: el costo del transporte diario, los puestos vacíos de quienes ya hacen la misma ruta y la desconfianza de viajar con desconocidos.

- **Solo entra la comunidad:** registro con correo institucional (sufijo configurable, `ALLOWED_EMAIL_SUFFIX`) y carné o constancia que aprueba un administrador.
- **Cuatro roles:** pasajero, conductor, administrador y superadmin. Es una sola aplicación; el menú y lo permitido cambian según el rol.
- **Lo que no hace:** no procesa pagos. El conductor fija un aporte por puesto (la app sugiere uno según la distancia) y el pago se acuerda por fuera; la app emite un ticket y el conductor marca "aporte recibido". Tampoco envía notificaciones push al celular: los avisos llegan dentro de la app.

---

## 2. Tecnologías (encontradas en el código)

| Capa | Tecnología | Archivo donde se ve | Para qué |
|------|------------|---------------------|----------|
| Frontend | Angular 22, Tailwind CSS 4, Transloco, MapLibre GL | `frontend/package.json` | Interfaz, estilos, textos en 4 idiomas, mapa |
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn/Gunicorn | `backend/pyproject.toml`, `backend/Dockerfile` | API REST y WebSocket, validación |
| Acceso a datos | SQLAlchemy 2 (asíncrono) + asyncpg, GeoAlchemy2, Alembic | `backend/pyproject.toml` | ORM, columnas geográficas, migraciones |
| Tareas | ARQ sobre Redis | `backend/app/workers/main.py` | Cola de correos y 12 tareas programadas |
| Seguridad | argon2-cffi, PyJWT, slowapi | `backend/app/core/security.py`, `rate_limit.py` | Contraseñas, tokens, límites de peticiones |
| Datos | PostgreSQL 16 + PostGIS 3.4, Redis 7 | `infra/docker-compose.yml` | Base de datos, eventos y cola |
| Rutas | OSRM 5.27 | `infra/docker-compose.yml`, `backend/app/modules/routing/osrm.py` | Rutas reales por las calles de Pamplona |
| Entrada | Nginx | `infra/nginx/default.conf` | HTTPS, archivos de Angular, proxy de `/api` y `/ws` |
| Operación | Docker Compose, GitHub Actions | `infra/`, `.github/workflows/ci.yml` | Levantar todo igual, integración continua |
| Pruebas | pytest, Vitest, Playwright | `backend/tests`, `frontend/e2e` | Backend, componentes y punta a punta |

---

## 3. Arquitectura

```
Navegador (Angular) ──HTTPS──► Nginx (web) ──/api y /ws──► API FastAPI ──► PostgreSQL + PostGIS
                                   │                          │      ├────► Redis (eventos y cola)
                                   └─ archivos de Angular     │      └────► OSRM (rutas)
                                      y mapa base             ▼
                                                        Worker ARQ ──► servidor SMTP (correos)
```

1. El navegador solo habla con **Nginx**. Nginx entrega el frontend compilado y reenvía `/api/` (REST) y `/ws` (WebSocket) al contenedor `api` (`infra/nginx/default.conf`).
2. La **API** es el único componente que toca la base de datos. Aplica las reglas en la capa `service.py` de cada módulo.
3. **PostgreSQL** guarda todo; **PostGIS** resuelve las consultas geográficas (rutas y distancias).
4. **Redis** cumple tres funciones: canal de eventos en tiempo real (publicar/suscribir), cola de trabajos del worker y almacén de los contadores de límites de peticiones.
5. El **worker** (`app/workers/main.py`) es otro proceso con el mismo código: envía los correos encolados y corre tareas programadas (vencer solicitudes, cancelar por retraso del conductor, ofrecer cupos de la lista de espera, marcar viajes no realizados, recordatorios, revalidación semestral, recálculo de pico y placa, factores de tráfico, retención del chat, cierre de calificaciones y fin de suspensiones).
6. **OSRM** calcula la ruta real por las calles; la API la consulta al publicar un viaje.

Todo corre en contenedores (`infra/docker-compose.yml`). Los datos de PostgreSQL viven en un volumen, así que un contenedor se puede recrear sin perder información.

---

## 4. Cómo arranca el backend

| Paso | Qué pasa | Dónde |
|------|----------|-------|
| 1 | Docker ejecuta `alembic upgrade head && uvicorn app.main:app --reload` (desarrollo) o `alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2` (producción) | `infra/docker-compose.dev.yml`, `backend/Dockerfile` |
| 2 | Alembic aplica las migraciones pendientes (13 en total) | `backend/alembic/versions/` |
| 3 | Uvicorn importa `app.main` y toma `app = create_app()` | `backend/app/main.py` |
| 4 | `get_settings()` lee y valida el `.env`; en producción rechaza claves de ejemplo | `backend/app/core/config.py` |
| 5 | Logs estructurados, middlewares y manejadores de errores | `core/logging.py`, `core/middleware.py`, `core/errors.py` |
| 6 | Se registra un `APIRouter` con prefijo `/api/v1` que incluye 20 routers públicos, 9 de administración y el de salud; el WebSocket se registra aparte en `/ws` | `backend/app/main.py` |
| 7 | Al apagar, `lifespan` cierra ARQ, Redis y el pool de PostgreSQL (`engine.dispose()`) | `backend/app/main.py` |

**Detalle importante:** la conexión a PostgreSQL no se abre al arrancar. `create_async_engine` crea el motor y el pool de forma perezosa; la primera consulta abre la primera conexión.

**Middlewares** (el último agregado es el más externo, así que la petición los atraviesa en este orden):

1. `RequestLogMiddleware`: asigna `X-Request-ID` y registra método, ruta, estado y duración.
2. `CORSMiddleware`: solo acepta los orígenes de `CORS_ORIGINS`.
3. `SecurityHeadersMiddleware`: `nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`, HSTS en producción.
4. `SlowAPIMiddleware`: límite global (`RATE_LIMIT_DEFAULT`, 120/minuto por IP) con contadores en Redis.

---

## 5. Conexiones internas del backend

Cada módulo de `backend/app/modules/` repite las mismas capas:

| Archivo | Responsabilidad |
|---------|-----------------|
| `router.py` | Recibe la petición, declara dependencias (rol, sesión) y devuelve la respuesta. No decide reglas |
| `schemas.py` | Modelos Pydantic: validan la entrada y definen la salida |
| `service.py` | Reglas del negocio: la única capa que decide si algo se puede hacer |
| `repository.py` / `queries.py` | Consultas reutilizables o complejas |
| `models.py` | Tablas de SQLAlchemy |
| `jobs.py` | Tareas programadas del módulo |

Piezas compartidas en `backend/app/core/`:

- `auth.py`: `get_current_user` lee el token JWT, comprueba que la sesión no esté revocada ni vencida y que la cuenta no esté bloqueada. `require_roles(...)` crea dependencias como `Passenger`, `Driver`, `AdminActor` o `SuperAdminActor`.
- `deps.py`: `DbSession = Annotated[AsyncSession, Depends(get_session)]`, la sesión de base de datos de cada petición.
- `errors.py`: `AppError` y el formato común de errores.
- `realtime.py`: `emit(...)` encola eventos que se publican en Redis solo después del commit.
- `db.py`: motor, sesiones, `add_unique` (inserción con savepoint) y el mixin `Authorship` (`created_by`, `updated_by`).

### 5.1 Flujo "pedir cupo" (`POST /api/v1/trips/{trip_id}/bookings`)

1. **Evento:** la pasajera pulsa "Solicitar cupo" (`frontend/src/app/features/bookings/booking-panel.ts`, `submit()`).
2. **Frontend:** `bookings.api.ts` → `request(tripId, body)` hace el POST. `auth.interceptor.ts` agrega `Authorization: Bearer <token>`.
3. **Ruta:** `bookings/router.py`, función `request_booking`, con `@limiter.limit("20/minute")`.
4. **Dependencias:** `Passenger` (usuario activo con rol pasajero) y `DbSession`.
5. **Validación:** el cuerpo se convierte en `BookingCreate` (`seats`, `pickup_place_id`, `dropoff_place_id`, `preferences`). Si falla → 422 `VALIDATION_ERROR`.
6. **Servicio:** `BookingService.request(passenger, trip_id, data)`:
   - `require_bookable`: el viaje existe, está programado, no ha salido y no es propio;
   - `check_compatibility`: viaje solo para mujeres y preferencias;
   - `require_can_book`: sin suspensión de reservas por ausencias;
   - `has_active`: no tener ya una reserva en ese viaje (`BOOKING_EXISTS`);
   - `seats_left`: cupo suficiente (`TRIP_FULL`);
   - `resolve_places` y `meeting`: punto de recogida sobre la ruta.
7. **Base de datos:** `add_unique(session, booking, error)` inserta en `bookings` dentro de un savepoint; `NotificationService.notify` agrega la fila en `notifications` y encola el evento; `session.commit()` confirma todo junto.
8. **Respuesta:** 201 con `BookingOut`. Después del commit, el evento sale por Redis y el conductor recibe el aviso por WebSocket.
9. **Error:** cualquier `AppError` interrumpe antes del commit; la sesión se cierra sin guardar y `app_error_handler` responde `{code, message, details}`.

### 5.2 Flujo "aceptar" (`POST /api/v1/bookings/{booking_id}/accept`)

`BookingService.accept` en `bookings/service.py`:

1. `get_for_driver`: la reserva debe ser de un viaje del conductor (si no, 404).
2. `lock_trip` (`bookings/queries.py`): `SELECT ... FOR UPDATE` sobre la fila del viaje. Las aceptaciones del mismo viaje se ejecutan de una en una.
3. Se recarga la reserva y se comprueba que siga `requested` (`BOOKING_NOT_PENDING`) y que el viaje siga abierto (`TRIP_NOT_BOOKABLE`).
4. `seats_left`: se cuentan los puestos ya aceptados dentro del bloqueo (`TRIP_FULL`).
5. Estado `accepted`, `decided_at`, `join_trip_chats` (entra al chat del viaje) y notificación al pasajero.
6. `commit()` libera el bloqueo; el evento `after_commit` publica en el canal `user:{id}` de Redis y el WebSocket del pasajero lo recibe.

La prueba `backend/tests/test_booking_concurrency.py` acepta 6 solicitudes en paralelo sobre 2 puestos y comprueba que solo 2 quedan aceptadas.

---

## 6. Conexión con la base de datos

**Sistema:** PostgreSQL 16 con PostGIS 3.4 (imagen `postgis/postgis:16-3.4`).

**Cadena de conexión:**

```
.env                DATABASE_URL=postgresql+asyncpg://<usuario>:<contraseña>@db:5432/carpool
core/config.py      Settings.database_url  (Pydantic Settings lee la variable)
core/db.py          engine = create_async_engine(database_url, pool_pre_ping=True)
core/db.py          SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
core/db.py          get_session(): async with SessionLocal() as session: yield session
core/deps.py        DbSession = Annotated[AsyncSession, Depends(get_session)]
service.py          self.session.execute(...) · add(...) · commit()
```

- `postgresql+asyncpg`: dialecto PostgreSQL con el driver asíncrono asyncpg.
- `db`: nombre del contenedor de PostgreSQL en la red interna de Docker; `5432`: puerto; `carpool`: base.
- `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB` crean ese usuario y esa base cuando arranca el contenedor `db`.
- Hay **un solo engine por proceso** con un **pool** de conexiones que se reutilizan.
- `pool_pre_ping=True` comprueba que una conexión siga viva antes de usarla.
- `get_session` entrega **una sesión por petición**; al terminar, `async with` la cierra y devuelve la conexión al pool. Si no hubo commit, lo pendiente se descarta.

**Operaciones reales:**

| Operación | Ejemplo en el código |
|-----------|----------------------|
| Crear | `TripService.create`: `self.session.add(trip)` y `await self.session.commit()` |
| Consultar | `lock_trip`: `select(Trip).where(Trip.id == trip_id).with_for_update(of=Trip)`; `session.get(Booking, id)` |
| Actualizar | `BookingService.accept`: `booking.status = BookingStatus.ACCEPTED` y `commit()` |
| Eliminar | Físico donde no hay historial (`SafetyService`: `await self.session.delete(contacto)`; reglas de pico y placa; semestres sin documentos). Lógico (`deleted_at`) en usuarios, vehículos y viajes |
| Geográfica | `SearchService.search`: `ST_Distance(trips.route::geography, punto)` y `ST_LineLocatePoint(trips.route, punto)` |

**Transacciones:** el servicio decide cuándo hacer `commit()`; un `AppError` antes del commit deja la base sin cambios. `add_unique` usa `begin_nested()` (savepoint) para convertir un choque de índice único en un error de negocio. `lock_trip` usa `FOR UPDATE` para la concurrencia.

**Credenciales:** el `.env` real está en `.gitignore`; en el repositorio solo hay `.env.example` sin valores. `config.py` (`safe_for_production`) impide arrancar en producción con la `SECRET_KEY` o las contraseñas de ejemplo. La contraseña del superadmin es `SecretStr` (no se imprime). El puerto 5432 solo se publica en desarrollo (`docker-compose.dev.yml`).

**Migraciones:** 13 archivos en `backend/alembic/versions/`, del `0001` (extensiones postgis, pgcrypto y citext) al `0013` (autoría en todas las tablas). Se aplican solas al arrancar la API.

---

## 7. Modelo de datos

35 tablas agrupadas por tema:

| Grupo | Tablas |
|-------|--------|
| Usuarios y acceso | `users`, `user_sessions`, `auth_codes`, `notifications`, `trusted_contacts`, `user_stats`, `suspensions` |
| Documentos y legal | `identity_documents`, `driver_licenses`, `semesters`, `legal_documents`, `terms_acceptances` |
| Vehículos, lugares y viajes | `vehicles`, `places`, `pico_placa_rules`, `trips`, `trip_stops`, `trip_rules`, `trip_series`, `series_stops`, `traffic_factors` |
| Reservas | `bookings`, `series_subscriptions`, `waitlist_entries`, `cancellation_requests`, `tickets` |
| Comunidad y control | `ratings`, `rating_scores`, `conversations`, `conversation_members`, `messages`, `emergency_events`, `share_links`, `system_settings`, `audit_log` |

**Relaciones centrales** (la llave foránea está en la segunda tabla):

- `users` 1 → N `trips` (`driver_id`), `vehicles` (`owner_id`), `bookings` (`passenger_id`).
- `vehicles` 1 → N `trips` (`vehicle_id`).
- `trips` 1 → N `trip_stops` (`trip_id`), `bookings` (`trip_id`), `ratings` (`trip_id`), `emergency_events`, `share_links`.
- `places` 1 → N `trip_stops` (`place_id`) y `bookings` (`pickup_place_id`, `dropoff_place_id`).
- `ratings` apunta a `users` dos veces (`author_id`, `target_id`); `rating_scores` guarda una nota por criterio.
- `conversations` cuelga del viaje o de la serie; `conversation_members` (llave compuesta) y `messages` la completan.

**Claves:** llave primaria UUID en casi todas; `system_settings` usa la clave de texto y las tablas puente (`conversation_members`, `rating_scores`) usan llave compuesta.

**Auditoría:** todas las tablas tienen `created_at`, `updated_at`, `created_by` y `updated_by`. Los dos últimos son llaves foráneas a `users` que se llenan solas con el usuario de la petición (mixin `Authorship` y eventos de SQLAlchemy en `core/db.py`). `audit_log` registra cada acción de administración con el estado antes y después, y un trigger de PostgreSQL impide modificarla o borrarla.

**Columnas geográficas:** `trips.route` (LineString) y `places.point` (Point), con SRID 4326.

Diagrama completo con todas las columnas: `docs/DIAGRAMA_ER.md` y `docs/diagrama-er/`.

---

## 8. Endpoints más importantes

La API expone **144 operaciones HTTP en 124 rutas** (63 GET, 63 POST, 10 PATCH, 2 PUT, 6 DELETE), todas bajo `/api/v1`, más el WebSocket `/ws`. Referencia completa: `/api/v1/docs` y `docs/API.md`.

| Método y ruta | Archivo · función | Recibe | Servicio | Base de datos | Responde |
|---------------|-------------------|--------|----------|---------------|----------|
| `POST /auth/register` | `auth/router.py` | multipart: datos + carné | `AuthService.register` | `users`, `identity_documents`, `terms_acceptances`, `auth_codes` | 201 con `challenge_id` |
| `POST /auth/login` | `auth/router.py · login` | `LoginRequest` (10/min) | `AuthService.login` | `users`, `user_sessions` | `AuthResult` + cookie de renovación |
| `POST /trips` | `trips/router.py · publish_trip` | `TripCreate` (20/min) | `TripService.create` | `trips`, `trip_stops` | 201 `TripOut` |
| `GET /search/trips` | `search/router.py · search_trips` | `SearchQuery` (60/min) | `SearchService.search` | consulta PostGIS sobre `trips` | lista de `SearchResult` |
| `POST /trips/{trip_id}/bookings` | `bookings/router.py · request_booking` | `BookingCreate` (20/min) | `BookingService.request` | `bookings`, `notifications` | 201 `BookingOut` |
| `POST /bookings/{booking_id}/accept` | `bookings/router.py · accept_booking` | rol `Driver` | `BookingService.accept` | `FOR UPDATE` en `trips`; `bookings` | `BookingOut` |
| `POST /admin/approvals/{approval_id}/approve` | `admin/router.py · approve` | rol administrador | `ApprovalService.approve` | documento, `users.status`, `audit_log` | aprobación |
| `GET /health/ready` | `core/health.py · ready` | — | — | `SELECT postgis_version()` + ping a Redis | 200 o 503 |

**Ejemplo de petición y respuesta (datos ficticios):**

```http
POST /api/v1/trips/7f3c…/bookings
Authorization: Bearer <token>
Content-Type: application/json

{ "seats": 1, "pickup_place_id": "2a91…", "dropoff_place_id": "c4d0…",
  "preferences": { "pets": false, "luggage": false, "no_smoking": true, "music": false } }
```

```json
HTTP/1.1 201 Created
{ "id": "b18e…", "status": "requested", "seats": 1, "amount": 2000,
  "trip": { "origin": "Barrio El Carmen", "destination": "Ciudad Universitaria" },
  "pickup": { "name": "Parque Águeda", "walk_m": 120 },
  "expires_at": "2026-10-15T12:30:00Z" }
```

---

## 9. Recorridos principales

### Registro e inicio de sesión
1. `register.ts` envía un formulario multipart a `POST /auth/register`.
2. `AuthService.register` valida el sufijo del correo, la aceptación de términos y política, y la política de contraseña. Guarda el carné en almacenamiento privado y crea el usuario en `pending_email`, el documento, las aceptaciones y un código (solo su huella HMAC). El worker envía el correo.
3. `verify-code.ts` → `POST /auth/verify-email` → `CodeService.check` (máximo de intentos) → la cuenta pasa a `pending_approval`.
4. Un administrador aprueba en `approvals.ts` → `POST /admin/approvals/{id}/approve` → la cuenta queda `active` y la acción va a `audit_log`.
5. `login.ts` → `POST /auth/login`: argon2 verifica la contraseña; tras varios fallos la cuenta se bloquea unos minutos; si corresponde, se pide un segundo factor por correo. Al final se crea una fila en `user_sessions`, se envía la cookie HttpOnly de renovación y un JWT de acceso de 15 minutos que vive solo en memoria.

### Publicar un viaje
`publish-wizard.ts` → `trips.api.ts` → `POST /trips` → `TripService.create`: `require_can_publish` (licencia aprobada y vigente, vehículo activo), puestos, aporte (tope `max_price_per_seat` → `PRICE_ABOVE_MAX`), reglas, fecha y pico y placa; `planner.plan_route` consulta OSRM; se guardan `trips` (ruta) y `trip_stops`; cruce con otro viaje del mismo conductor → `TRIP_OVERLAP`.

### Buscar
`search-page.ts` → `GET /search/trips?...` → `SearchService.search`: viajes programados con cupo cuya ruta pasa a menos de `search_radius_meters` (500 m por defecto) de la recogida y de la bajada, con la recogida antes de la bajada (`ST_LineLocatePoint`) y dentro de la ventana horaria (`search_time_window_minutes`).

### Tiempo real
El servicio llama a `emit(...)` o `NotificationService.notify(...)`; el evento queda pendiente hasta el commit; `after_commit` lo publica en Redis (canales `user:{id}`, `conv:{id}`, `trip:{id}:loc`, `admin:emergencies`); `live/connection.py` lo entrega al navegador por `/ws`; `realtime.service.ts` y `notifications.store.ts` actualizan la pantalla.

---

## 10. Seguridad y errores

**Implementado:** argon2id para contraseñas; JWT HS256 de 15 minutos en memoria; cookie HttpOnly `SameSite=Lax` de 30 días que rota en cada renovación y revoca todas las sesiones si se reutiliza (`REFRESH_REUSED`); códigos por correo guardados como huella HMAC; segundo factor; roles y verificación de propiedad en cada ruta (40 pruebas en `tests/test_ownership.py`); límites de peticiones en Redis; cabeceras de seguridad; validación Pydantic; archivos privados; auditoría inmutable; autoría en todas las tablas; validación de secretos en producción.

**Riesgos identificados:** una sola `SECRET_KEY` firma todos los tokens; el correo real depende de un SMTP externo (Gmail tiene límites diarios); certificado autofirmado en desarrollo; textos legales sin revisión jurídica.

**Errores:** todos salen como `{"code", "message", "details"}`. `register_error_handlers` registra cinco manejadores: `AppError` (código propio), `HTTPException` (por estado), `RequestValidationError` (422 con los campos), `RateLimitExceeded` (429) y `Exception` (500 `INTERNAL_ERROR`, sin detalles internos, con log). El frontend traduce `code` con `errors.<code>` de `es.json`. Si PostgreSQL no responde, las peticiones terminan en 500 y `/api/v1/health/ready` responde 503 (Docker usa ese endpoint como healthcheck).

---

## 11. Ejecución local

```sh
make up        # crea .env desde .env.example y levanta todo (Windows: .\make.ps1 up)
make osrm      # una vez: datos de rutas de Pamplona
make tiles     # una vez: mapa base
make seed      # parámetros, superadmin, semestre, lugares, pico y placa, términos
make test      # pruebas de backend y frontend
make lint      # ruff, mypy, ESLint y Prettier
```

- Aplicación: https://localhost · API: http://localhost:8000/api/v1/docs · correo de prueba: http://localhost:8025.
- `make clean` borra los volúmenes (y con ellos los datos). `make restore` sobrescribe la base: usar solo con un respaldo verificado (`make backup-check`).

---

## 12. Estado verificado

- Suite del backend: 341 pruebas aprobadas, 95 % de cobertura, ruff y mypy sin errores (14 y 15 de octubre de 2026).
- Migración `0013`: probada subiendo, bajando y volviendo a subir; `alembic check` sin diferencias.
- Integración continua en GitHub (rama `main`): éxito en la ejecución anterior.
- **No se ejecutaron en esta revisión** las pruebas E2E ni las unitarias del frontend.
- La prueba E2E de registro lee el código en Mailpit y falla si el `.env` envía los correos por Gmail.

---

## 13. Preguntas probables del docente

**¿Dónde está la lógica de negocio?**
En el `service.py` de cada módulo (`backend/app/modules/<módulo>/service.py`). El router solo recibe y responde; así las reglas se prueban sin HTTP.

**¿Cómo se conecta el backend a la base de datos?**
`DATABASE_URL` (en `.env`) → `Settings.database_url` (`core/config.py`) → `create_async_engine` con pool (`core/db.py`) → una `AsyncSession` por petición con `get_session`, inyectada como `DbSession` (`core/deps.py`).

**¿Por qué SQLAlchemy y no SQL a mano?**
Porque traduce las clases a tablas, evita inyección SQL (parámetros siempre ligados), permite componer consultas y Alembic genera las migraciones comparando modelos y base. Para lo geográfico se usan funciones de PostGIS (`func.ST_Distance`) dentro de la misma consulta.

**¿Qué es una migración?**
Un archivo versionado que crea o cambia tablas. `alembic upgrade head` aplica las que falten; así cualquier máquina tiene el mismo esquema.

**¿Cómo evitan que dos personas tomen el último puesto?**
Pedir cupo no aparta el puesto. Al aceptar, `lock_trip` hace `SELECT ... FOR UPDATE` sobre el viaje y los puestos se recuentan dentro de esa transacción. Hay una prueba de concurrencia que lo comprueba.

**¿Cómo llegan los avisos sin recargar la página?**
Después del commit se publica el evento en Redis y el WebSocket `/ws` lo envía al navegador del destinatario.

**¿Qué pasa si falla algo a mitad de una operación?**
Nada queda a medias: sin `commit()` la transacción se descarta, y los eventos en tiempo real solo se publican si el commit ocurre.

**¿Cómo protegen las contraseñas y la sesión?**
argon2id para contraseñas. El token de acceso dura 15 minutos y vive en memoria; la renovación usa una cookie HttpOnly que JavaScript no puede leer y que rota en cada uso.

**¿Cómo saben quién cambió un registro?**
Cada tabla tiene `created_by` y `updated_by`, llenados automáticamente con el usuario de la petición. Las acciones de administración quedan además en `audit_log`, que la base no deja modificar.

**¿Cómo funciona la búsqueda por cercanía?**
La ruta de cada viaje se guarda como una línea de PostGIS. La consulta mide en metros la distancia de esa línea a tu punto de recogida y de bajada (`ST_Distance` sobre `geography`) y comprueba con `ST_LineLocatePoint` que el carro pase primero por la recogida.

**¿Qué pasa si se cae la base de datos?**
Las peticiones responden 500 `INTERNAL_ERROR` sin exponer detalles, el error queda en el log y `/api/v1/health/ready` responde 503.

**¿Qué no está implementado?**
Pagos en línea y notificaciones push. Los textos legales y algunos datos iniciales (reglas de pico y placa, coordenadas de lugares) son de ejemplo.

**¿Cuántas tablas y endpoints tiene?**
35 tablas y 144 operaciones HTTP (más el WebSocket), contadas desde el esquema OpenAPI de la aplicación.
