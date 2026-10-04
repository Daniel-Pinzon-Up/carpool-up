# Carpool Universitario

Plataforma web para que la comunidad de la Universidad de Pamplona comparta trayectos en carro o moto dentro de Pamplona. El plan completo está en el documento maestro; las decisiones tomadas durante la construcción están en [docs/DECISIONES.md](docs/DECISIONES.md).

## Estado

| Paso | Contenido | Estado |
|------|-----------|--------|
| 0 | Cimientos: monorepo, Docker Compose, FastAPI modular, Angular con sistema de diseño glass | Hecho |
| 1 a 14 | Ver plan maestro, sección 16 | Pendiente |

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

## Desarrollo

### Frontend con recarga en caliente

```sh
cd frontend
npm install
npm start        # http://localhost:4200, con proxy de /api y /ws hacia localhost:8000
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
| `make seed` | Cargar datos semilla |
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
