# Infraestructura de Carpool UP

Todo el sistema corre en contenedores Docker definidos con Docker Compose. Así cualquier persona levanta exactamente las mismas versiones de PostgreSQL, Redis, OSRM y Nginx con un solo comando (`make up`), sin instalar nada más que Docker.

## Estructura

```
infra/
├── docker-compose.yml        servicios base, iguales en desarrollo y producción
├── docker-compose.dev.yml    se suma en desarrollo: puertos abiertos, código montado, Mailpit
├── nginx/
│   ├── default.conf          HTTPS, archivos de Angular, proxy de /api y /ws, mapa base, caché
│   ├── security-headers.conf cabeceras de seguridad (CSP, HSTS, X-Frame-Options…)
│   └── 10-self-signed-cert.sh crea un certificado autofirmado si no hay uno real
├── db/init/01-test-database.sql  crea la base carpool_test la primera vez que arranca PostgreSQL
├── scripts/
│   ├── backup.sh             respaldo diario con pg_dump; guarda los 7 más recientes
│   ├── restore.sh            restaura un respaldo y lo verifica, o lo aplica sobre la base en uso
│   ├── build_osrm.sh         descarga Colombia, la recorta a Pamplona y prepara el grafo de rutas
│   └── build_tiles.sh        descarga el mapa base de Pamplona en formato PMTiles
├── osrm/
│   ├── clip.py               recorte del mapa a la zona de Pamplona
│   └── data/                 grafo de OSRM generado (no se versiona)
└── tiles/                    pamplona.pmtiles (no se versiona)
```

## Servicios

| Servicio | Imagen | Para qué sirve |
|----------|--------|----------------|
| `db` | `postgis/postgis:16-3.4` | PostgreSQL con PostGIS. Los datos viven en un volumen, no en el contenedor |
| `redis` | `redis:7-alpine` | Eventos en tiempo real (WebSocket) y cola de trabajos del worker |
| `api` | `backend/Dockerfile` | FastAPI: API REST `/api/v1` y WebSocket `/ws` |
| `worker` | `backend/Dockerfile` | ARQ: envía correos y corre las tareas programadas |
| `web` | `frontend/Dockerfile` | Nginx con la app de Angular compilada; única puerta de entrada (puertos 80 y 443) |
| `backup` | `postgis/postgis:16-3.4` | Respaldos diarios en `../backups` y restauración |
| `osrm` | `osrm-backend` | Motor de rutas con el mapa de Pamplona (perfil `osrm`, arranca si existen sus datos) |
| `mailpit` | solo desarrollo | Bandeja de correo de prueba en http://localhost:8025 |

Volúmenes: los datos de PostgreSQL y Redis, `storage` (carnés, licencias y fotos de vehículos) y `certs` (certificado HTTPS).

## Cómo viaja una petición

```
Navegador ──443──► web (Nginx)
                     ├── /            → archivos compilados de Angular
                     ├── /tiles/      → mapa base de Pamplona
                     ├── /api/        → api:8000
                     └── /ws          → api:8000 (WebSocket)
api ──► db (SQL) · redis (eventos y cola) · osrm (rutas)
worker ──► redis (lee la cola) · db · servidor SMTP (correos)
```

## Comandos

Desde la raíz del repositorio (en Windows, `.\make.ps1 <objetivo>`):

| Comando | Acción |
|---------|--------|
| `make up` / `make down` | Levantar o detener todos los servicios |
| `make logs` / `make ps` | Ver logs y estado |
| `make osrm` | Preparar los datos de rutas (una vez, tarda unos minutos) |
| `make tiles` | Descargar el mapa base (una vez, cerca de 1 MB) |
| `make backup-check` | Restaurar el último respaldo en una base aparte y compararlo con la actual |
| `make restore FILE=...` | Restaurar un respaldo sobre la base en uso |
| `make clean` | Detener todo y borrar los volúmenes (se pierden los datos) |

El despliegue en producción, los certificados reales y la actualización están en [docs/DESPLIEGUE.md](../docs/DESPLIEGUE.md).
