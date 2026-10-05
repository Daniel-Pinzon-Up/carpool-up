# Carpool Universitario

Plataforma web para que la comunidad de la Universidad de Pamplona comparta trayectos en carro o moto dentro de Pamplona. El plan completo está en el documento maestro; las decisiones tomadas durante la construcción están en [docs/DECISIONES.md](docs/DECISIONES.md).

## Estado

| Paso | Contenido | Estado |
|------|-----------|--------|
| 0 | Cimientos: monorepo, Docker Compose, FastAPI modular, Angular con sistema de diseño glass | Hecho |
| 1 | Configuración y catálogos: parámetros, semestres, lugares, pico y placa, documentos legales y auditoría | Hecho |
| 2 | Autenticación y cuentas: registro con documento, verificación de correo, 2FA, sesiones, recuperación, términos y pantallas | Hecho |
| 3 | Aprobaciones y revalidación: cola de carnets y licencias, visor seguro, revalidación semestral, administradores, roles y notificaciones | Hecho |
| 4 | Vehículos: CRUD con foto, reglas de placa y capacidad, requisitos para publicar e inicio del conductor | Hecho |
| 5 | Rutas y mapas: OSRM con el mapa de Pamplona, ETA con factor de tráfico, aporte sugerido, mapa base propio y planificador de rutas | Hecho |
| 6 a 14 | Ver plan maestro, sección 16 | Pendiente |

## Requisitos

- Docker Desktop con WSL2 (Windows) o Docker Engine con Compose v2
- Node.js 24 o superior (para trabajar en el frontend fuera de Docker)
- uv (para trabajar en el backend fuera de Docker)

## Arranque rápido

```sh
make up          # Windows: .\make.ps1 up
```

`make up` crea `.env` desde `.env.example` si no existe y levanta:

| Servicio | URL |
|----------|-----|
| Aplicación web (HTTPS, certificado autofirmado) | https://localhost |
| API y documentación | http://localhost:8000/api/v1/docs |
| Correo de desarrollo (Mailpit) | http://localhost:8025 |
| PostgreSQL con PostGIS | localhost:5432 |
| Redis | localhost:6379 |

El catálogo de componentes del sistema de diseño está en `/catalogo` en modo desarrollo.

### Mapa y rutas

```sh
make osrm     # descarga Colombia (unos 330 MB), la recorta a Pamplona y genera el grafo de OSRM; tarda unos minutos
make tiles    # descarga solo el recorte de Pamplona del mapa base de Protomaps (cerca de 1 MB)
make up       # levanta OSRM si ya existen sus datos
```

En Windows: `.\make.ps1 osrm` y `.\make.ps1 tiles` (necesitan Git Bash). Los datos quedan en `infra/osrm/data` e `infra/tiles` y no se versionan.

### Primeros pasos con datos

```sh
make seed                                         # parametros, superadmin, semestre, lugares, pico y placa y terminos
make token EMAIL=superadmin@unipamplona.edu.co    # token para probar /admin/* desde /api/v1/docs (boton Authorize)
```

En Windows: `.\make.ps1 seed` y `.\make.ps1 token superadmin@unipamplona.edu.co`.

El superadmin inicial se toma de `SUPERADMIN_EMAIL` y `SUPERADMIN_PASSWORD` en `.env`.

Los correos de verificación y recuperación llegan a Mailpit en desarrollo: http://localhost:8025.

## Desarrollo

### Frontend con recarga en caliente

```sh
cd frontend
npm install
npm start        # http://localhost:4200, con proxy de /api y /ws hacia localhost:8000 y de /tiles hacia Nginx
```

### Backend fuera de Docker

```sh
cd backend
uv sync --python 3.12
uv run python -m pytest -m "not integration"   # pruebas que no necesitan servicios
```

## Comandos

| Comando | Acción |
|---------|--------|
| `make up` / `make down` | Levantar o detener todo |
| `make logs` | Ver logs |
| `make migrate` | Aplicar migraciones |
| `make seed` | Cargar datos semilla (idempotente) |
| `make token EMAIL=...` | Token de acceso de desarrollo para probar la API |
| `make test` | Pruebas de backend (con PostGIS real) y frontend |
| `make lint` | ruff, mypy, ESLint y Prettier |
| `make clean` | Detener y borrar volúmenes |

En Windows sin `make`, usa `.\make.ps1 <objetivo>` con los mismos nombres.

## Estructura

```
backend/    FastAPI, SQLAlchemy asíncrono, Alembic, ARQ
frontend/   Angular 22, Tailwind 4, Transloco, Lucide
infra/      Docker Compose, Nginx, scripts, datos de OSRM y teselas
docs/       Decisiones y API
```

## Notas para Windows

Si Smart App Control está activo, puede bloquear binarios nativos como `ruff` y `mypy` dentro de `backend/.venv`. Por eso el lint del backend corre dentro de Docker (`make lint`).
