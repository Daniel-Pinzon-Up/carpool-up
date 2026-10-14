# Backend de Carpool UP

API REST y WebSocket en Python 3.12 con FastAPI, SQLAlchemy asíncrono sobre PostgreSQL 16 + PostGIS, migraciones con Alembic, y tareas en segundo plano con ARQ sobre Redis. Toda la lógica de negocio vive aquí: el frontend nunca decide por su cuenta si algo está permitido.

## Estructura

```
backend/
├── app/
│   ├── main.py               crea la app FastAPI, middlewares, manejo de errores y registra los routers
│   ├── models_registry.py    importa todos los models.py para que Alembic vea las tablas
│   ├── seed.py               datos iniciales idempotentes (make seed)
│   ├── cli.py                comandos de desarrollo: token, e2e-users, email-test, verify-email…
│   ├── seed_data/            términos y política de datos (es, en, pt, fr)
│   ├── core/                 piezas compartidas por todos los módulos
│   ├── modules/              un paquete por tema de negocio
│   └── workers/main.py       worker ARQ: cola de correos y tareas programadas
├── alembic/
│   ├── env.py
│   └── versions/             migraciones 0001 a 0013
├── tests/                    pruebas con pytest contra PostgreSQL real (base carpool_test)
├── pyproject.toml            dependencias, ruff, mypy, pytest y cobertura mínima de 80 %
├── uv.lock                   versiones exactas de las dependencias
├── alembic.ini
└── Dockerfile
```

### `app/core/`

| Archivo | Para qué sirve |
|---------|----------------|
| `config.py` | Variables de entorno (`.env`) validadas con Pydantic; en producción se niega a arrancar con secretos de ejemplo |
| `db.py` | Motor y sesión de SQLAlchemy, base de los modelos, mixins `Timestamps` y `Authorship` (`created_by`, `updated_by` automáticos) |
| `deps.py` | Dependencias de FastAPI: sesión de base de datos por petición |
| `auth.py` | Usuario actual desde el token, cuenta activa, roles (`AdminActor`, `SuperAdminActor`…) |
| `security.py` | Contraseñas (Argon2), tokens JWT, códigos por correo y huellas HMAC |
| `errors.py` | `AppError`: todos los errores salen con el mismo formato y un código estable |
| `enums.py` | Estados y tipos del dominio (rol, estado del viaje, de la reserva…) |
| `email.py` | Plantillas de correo y encolado en Redis |
| `realtime.py` · `redis.py` | Publicación de eventos en Redis para el WebSocket |
| `rate_limit.py` | Límites de peticiones (inicio de sesión, registro, renovación) |
| `middleware.py` | Cabeceras de seguridad y registro de cada petición |
| `geo.py` · `clock.py` · `pagination.py` · `storage.py` · `logging.py` · `health.py` | Geometría, hora de Pamplona, paginación por cursor, archivos privados, logs y `/health` |

### `app/modules/`

Cada módulo repite la misma estructura, así es fácil encontrar dónde está cada cosa:

| Archivo | Capa |
|---------|------|
| `router.py` | Recibe la petición HTTP, exige el rol y devuelve la respuesta. No decide reglas |
| `schemas.py` | Modelos Pydantic: validan lo que entra y definen lo que sale |
| `service.py` | **Reglas del negocio.** Es la única capa que decide si algo se puede hacer |
| `repository.py` / `queries.py` | Consultas a la base cuando son reutilizables o complejas |
| `models.py` | Tablas de SQLAlchemy |
| `jobs.py` | Tareas programadas del módulo, que el worker ejecuta |

| Módulo | Contenido |
|--------|-----------|
| `auth` | Registro, ingreso, códigos por correo, segundo factor, sesiones y recuperación de contraseña |
| `users` | Perfil propio y eliminación de cuenta con anonimización |
| `documents` | Carné o constancia y licencia de conducción; revalidación semestral |
| `legal` | Términos y política de datos versionados y su aceptación |
| `semesters` · `places` · `pico_placa` · `settings` | Catálogos y parámetros que configura el superadmin |
| `vehicles` | Vehículos del conductor y requisitos para publicar |
| `routing` | Rutas con OSRM, tiempo estimado, factor de tráfico y aporte sugerido |
| `trips` · `series` | Viajes puntuales y series recurrentes: publicar, editar, cancelar, ciclo del viaje |
| `search` | Búsqueda geográfica de viajes cerca de la ruta del pasajero |
| `bookings` · `cancellations` · `waitlist` | Reservas, suscripciones a series, cancelaciones tardías y lista de espera |
| `tickets` | Tickets de aporte al finalizar el viaje |
| `chat` · `notifications` · `live` | Chat por viaje, avisos y el WebSocket `/ws` |
| `safety` | Ubicación en vivo, enlace para compartir, contactos de confianza y emergencias |
| `ratings` · `stats` | Calificaciones por criterio, reputación, historial y estadísticas |
| `suspensions` | Sanciones de cuenta y de reservas |
| `audit` | Registro inmutable de acciones de administración |
| `admin` | Consola de administración: aprobaciones, usuarios, viajes, emergencias, moderación |

### `app/workers/main.py`

El worker ARQ consume la cola de correos y ejecuta tareas cada cierto tiempo: vencer solicitudes sin respuesta, cancelar por retraso del conductor, ofrecer cupos de la lista de espera, marcar viajes no realizados, recordatorios de salida, revalidación semestral, recálculo de pico y placa, factores de tráfico, retención del chat, cierre del plazo de calificación y fin de suspensiones.

## Cómo fluye una petición

```
HTTP → main.py (middlewares) → router.py (rol) → schemas.py (validación) → service.py (reglas)
     → models.py / repository.py → PostgreSQL → (evento en Redis) → respuesta JSON
```

Al autenticar la petición se registra quién la hace, y la base guarda ese usuario en `created_by` y `updated_by` de cada fila que se crea o cambia. Los cambios del worker, del seed o del CLI quedan sin autor.

## Comandos

Desde la raíz del repositorio (en Windows, `.\make.ps1 <objetivo>`):

| Comando | Acción |
|---------|--------|
| `make migrate` | Aplica las migraciones pendientes |
| `make seed` | Carga los datos iniciales |
| `make test-backend` | Pruebas con cobertura contra PostgreSQL real |
| `make lint` | ruff (formato y reglas) y mypy, más ESLint y Prettier del frontend |
| `make token EMAIL=...` | Token de acceso para probar la API en `/api/v1/docs` |

Una migración nueva, desde el contenedor:

```sh
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml \
  exec api alembic revision --autogenerate -m "descripcion"
```

Fuera de Docker (solo pruebas que no necesitan servicios):

```sh
cd backend
uv sync --python 3.12
uv run python -m pytest -m "not integration"
```

La referencia completa de la API está en [docs/API.md](../docs/API.md) y en `/api/v1/docs` con la app levantada.
