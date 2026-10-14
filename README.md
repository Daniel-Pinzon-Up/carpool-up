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
- [Casos de uso de prueba](docs/CASOS_DE_USO.md): 20 recorridos completos con datos concretos y resultados esperados.
- [Decisiones](docs/DECISIONES.md), [diagrama entidad-relación](docs/DIAGRAMA_ER.md) y [cómo funciona por dentro](docs/COMO_FUNCIONA.md).
- Por carpeta: [backend](backend/README.md), [frontend](frontend/README.md), [infraestructura](infra/README.md) y [documentación](docs/README.md).

## Estructura del repositorio

Monorepo: el backend, el frontend, la infraestructura y la documentación viven juntos y se levantan con un solo comando. Cada carpeta principal tiene su propio README con el detalle.

```
carpool_U/
├── backend/                  API en Python (FastAPI) → backend/README.md
│   ├── app/
│   │   ├── core/             piezas compartidas: configuración, base de datos, seguridad, errores, Redis
│   │   ├── modules/          26 módulos de negocio (auth, trips, bookings, chat, admin…)
│   │   ├── workers/          tareas en segundo plano y programadas (ARQ)
│   │   ├── seed_data/        términos y política de datos en cuatro idiomas
│   │   ├── main.py           crea la aplicación FastAPI y registra los routers
│   │   ├── seed.py           datos iniciales (parámetros, superadmin, lugares…)
│   │   └── cli.py            comandos de desarrollo (token, e2e-users, email-test…)
│   ├── alembic/versions/     13 migraciones que crean y evolucionan las 35 tablas
│   ├── tests/                341 pruebas con PostgreSQL real
│   ├── pyproject.toml        dependencias y configuración de ruff, mypy y pytest
│   └── Dockerfile
├── frontend/                 aplicación web en Angular → frontend/README.md
│   ├── src/app/
│   │   ├── core/             lo que existe una sola vez: sesión, HTTP, WebSocket, menú, idioma, tema
│   │   ├── features/         una carpeta por pantalla o flujo (buscar, publicar, reservas, admin…)
│   │   └── shared/           componentes reutilizables: interfaz glass, mapa, gráficas, íconos
│   ├── public/               traducciones (i18n), recursos del mapa, marca y script de tema
│   ├── e2e/                  pruebas de punta a punta y accesibilidad con Playwright
│   ├── angular.json · package.json · proxy.conf.json · playwright.config.ts
│   └── Dockerfile            compila Angular y lo sirve con Nginx
├── infra/                    contenedores y servidores → infra/README.md
│   ├── docker-compose.yml        servicios base (db, redis, api, worker, web, backup, osrm)
│   ├── docker-compose.dev.yml    puertos abiertos, recarga en caliente y Mailpit para desarrollo
│   ├── nginx/                HTTPS, proxy hacia la API y cabeceras de seguridad
│   ├── db/init/              crea la base de pruebas al iniciar PostgreSQL
│   ├── scripts/              respaldos, restauración y preparación de mapas
│   ├── osrm/                 recorte del mapa de Colombia a Pamplona (datos no versionados)
│   └── tiles/                mapa base de Pamplona en PMTiles (no versionado)
├── docs/                     documentación del proyecto → docs/README.md
│   ├── diagrama-er/          vistas del modelo entidad-relación en PNG
│   └── mockups/              bosquejos de todas las pantallas (celular y PC)
├── design/brand/             logo, nombre e ilustraciones originales de la marca
├── .github/workflows/ci.yml  integración continua: backend, frontend, imágenes y E2E
├── Makefile · make.ps1       atajos de comandos (make en Linux/Mac, make.ps1 en Windows)
├── .env.example              plantilla de variables de entorno (.env no se versiona)
└── README.md
```

## Cómo se conectan las piezas

```
Navegador (Angular) ──HTTPS──► Nginx (web) ──/api y /ws──► API FastAPI ──► PostgreSQL + PostGIS
                                   │                          │      ├────► Redis (eventos y cola)
                                   └─ archivos de Angular     │      └────► OSRM (rutas de Pamplona)
                                      y mapa base             ▼
                                                        Worker ARQ (correos y tareas programadas)
```

1. **El navegador solo habla con Nginx.** Nginx entrega los archivos compilados de Angular y el mapa base, y pasa a la API todo lo que empieza por `/api` (peticiones REST) o `/ws` (WebSocket).
2. **El frontend llama a la API** desde los archivos `*.api.ts` de cada pantalla. Un interceptor agrega el token de acceso y lo renueva con la cookie de sesión cuando vence. Las respuestas son JSON; los errores traen un código (por ejemplo `TRIP_FULL`) que el frontend muestra traducido.
3. **La API aplica las reglas** en la capa `service.py` de cada módulo y guarda en **PostgreSQL**. Las búsquedas geográficas las resuelve PostGIS dentro de la base.
4. **Tiempo real:** cuando algo cambia (una reserva aceptada, un mensaje nuevo), la API publica un evento en **Redis** y el WebSocket lo entrega a los navegadores interesados, sin recargar.
5. **El worker** toma de Redis los trabajos pendientes (enviar correos) y corre tareas programadas: recordatorios, viajes no realizados, vencimiento de solicitudes, revalidación semestral.
6. **OSRM** calcula rutas, distancias y tiempos con el mapa de Pamplona.

Todo corre en contenedores Docker y la base de datos guarda sus datos en un volumen, así se puede borrar y recrear cualquier contenedor sin perder información.

## Modelo de datos

35 tablas en PostgreSQL 16 con PostGIS, creadas por las migraciones de Alembic. Todas tienen `created_at` y `updated_at`, y `created_by` y `updated_by` (quién creó la fila y quién la cambió por última vez), que se llenan solos con el usuario de cada petición. Las acciones de administración quedan además en `audit_log`, que la base no deja modificar. Diagrama completo: [docs/DIAGRAMA_ER.md](docs/DIAGRAMA_ER.md).

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

Los correos de verificación y recuperación llegan a Mailpit en desarrollo: http://localhost:8025. Para enviarlos a buzones reales (Gmail, Brevo o Resend, gratis) ver [DESPLIEGUE.md, sección 5](docs/DESPLIEGUE.md#5-correo-real) y probar con `make email-test TO=correo`.

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


## Notas para Windows

Si Smart App Control está activo, puede bloquear binarios nativos como `ruff` y `mypy` dentro de `backend/.venv`. Por eso el lint del backend corre dentro de Docker (`make lint`).
