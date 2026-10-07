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
| 6 | Publicación de viajes y series: asistente, ocurrencias, pico y placa, edición, cancelación, duplicado y Mis viajes del conductor | Hecho |
| 7 | Búsqueda de viajes: coincidencia geográfica con la ruta, ventana horaria, preferencias, solo mujeres y punto de recogida | Hecho |
| 8 | Reservas y suscripciones: aprobación con bloqueo, cancelaciones libres y tardías, retraso del conductor, lista de espera, suscripción a series y bandeja del conductor | Hecho |
| 9 | Tiempo real, chat y notificaciones: WebSocket con Redis, chat grupal por viaje y directo por serie, retención, avisos en vivo y bandeja de mensajes | Hecho |
| 10 | Ciclo del viaje y seguridad: iniciar, abordaje, no-show con sanción, tickets, ubicación en vivo, enlace público, contactos de confianza, emergencias y factores de tráfico | Hecho |
| 11 | Calificaciones, historial y estadísticas: calificación por criterio con plazo, reputación en búsqueda, historial con tickets y métricas por rol | Hecho |
| 12 | Panel de administración: indicadores, usuarios con suspensión y bloqueo, monitoreo de viajes, emergencias en vivo, moderación y configuración completa del superadmin, todo auditado | Hecho |
| 13 | Internacionalización y pulido: cuatro idiomas revisados, pantalla de ayuda, estados de error con reintento, contraste AA en ambos temas, sesión estable ante fallos pasajeros y axe sin errores graves en 24 pantallas | Hecho |
| 14 | Calidad final y entrega: eliminación de cuenta (Ley 1581), términos en cuatro idiomas, carga inicial de 745 a 436 kB, revisión de seguridad (propiedad, límites, cabeceras, dependencias), respaldos verificados, E2E de punta a punta, CI y guías de despliegue y administración | Hecho |

## Documentación

- [Guía de despliegue](docs/DESPLIEGUE.md): arranque desde cero, producción, certificados, respaldos y actualizaciones.
- [Guía de administración](docs/GUIA_ADMINISTRACION.md): panel, aprobaciones, sanciones, emergencias, moderación y parámetros.
- [API](docs/API.md): endpoints, errores, límites y autorización. La documentación interactiva está en `/api/v1/docs`.
- [Decisiones](docs/DECISIONES.md), [diagrama entidad-relación](docs/DIAGRAMA_ER.md) y [cómo funciona por dentro](docs/COMO_FUNCIONA.md).

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

### Pruebas de extremo a extremo y accesibilidad

Corren con Playwright contra la app levantada (`make up`) y usan el Chrome instalado en el equipo.

```bash
# 1. Cuentas de prueba (solo desarrollo). La contrasena es aleatoria y queda en un archivo ignorado por git.
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml \
  exec -T api python -m app.cli e2e-users > frontend/e2e/.auth/credentials.json

# 2. Pruebas: axe en 24 pantallas, ambos temas, escritorio y telefono; idioma y tema sin recargar.
cd frontend && npm run e2e
```

Para probar otro servidor, define `E2E_BASE_URL` (por defecto `https://localhost`).

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
| `make e2e-users` / `make test-e2e` | Cuentas de prueba y suite E2E con accesibilidad (solo desarrollo) |
| `make backup-check` | Restaura el último respaldo en una base aparte y lo compara con la actual |
| `make restore FILE=...` | Restaura un respaldo sobre la base en uso |
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
