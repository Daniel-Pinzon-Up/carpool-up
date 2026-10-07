# Guía de despliegue

Cómo poner Carpool UP en marcha desde cero, en un equipo de desarrollo o en un servidor de la universidad, y cómo mantenerlo: actualizaciones, respaldos y verificación.

## 1. Qué se instala

Todo corre en contenedores Docker, descritos en `infra/docker-compose.yml`:

| Contenedor | Qué hace |
|------------|----------|
| `web` | Nginx: sirve la app de Angular, termina HTTPS y reenvía `/api` y `/ws` al API |
| `api` | FastAPI (Gunicorn con 2 procesos Uvicorn en producción). Aplica las migraciones al arrancar |
| `worker` | ARQ: correos y tareas programadas (recordatorios, vencimientos, pico y placa, revalidación semestral, limpieza del chat) |
| `db` | PostgreSQL 16 con PostGIS 3.4 |
| `redis` | Eventos en tiempo real, colas y límites de peticiones |
| `osrm` | Rutas sobre las calles de Pamplona (perfil `osrm`) |
| `backup` | Respaldo diario de la base; conserva los 7 últimos |

En desarrollo se suma `infra/docker-compose.dev.yml`: recarga en caliente, puertos de depuración (API 8000, base 5432, Redis 6379) y Mailpit (correo de prueba en el puerto 8025).

## 2. Requisitos

- Docker Engine con Compose v2 (en Windows, Docker Desktop con WSL2).
- `make` (en Windows sin `make` se usa `.\make.ps1` con los mismos objetivos; los objetivos `osrm` y `tiles` necesitan Git Bash).
- Unos 4 GB de RAM libres y 3 GB de disco (la descarga de Colombia para OSRM se borra al terminar).
- Salida a internet la primera vez: imágenes de Docker, mapa de Colombia (Geofabrik) y teselas (Protomaps).

## 3. Primer arranque (desarrollo)

```sh
git clone <repositorio> carpool_U && cd carpool_U
make osrm     # una vez: descarga Colombia, la recorta a Pamplona y prepara el grafo de rutas (unos minutos)
make tiles    # una vez: teselas del mapa base de Pamplona (cerca de 1 MB)
make up       # crea .env desde .env.example si no existe, construye y levanta todo
make seed     # parámetros, superadmin, semestre, lugares, pico y placa, términos y política (4 idiomas)
```

Queda disponible en:

| Servicio | URL |
|----------|-----|
| Aplicación (certificado autofirmado) | https://localhost |
| Documentación del API | http://localhost:8000/api/v1/docs |
| Correo de desarrollo | http://localhost:8025 |

El superadmin inicial es `SUPERADMIN_EMAIL` con la contraseña `SUPERADMIN_PASSWORD` de `.env`. Su primer ingreso pide un código que llega por correo (en desarrollo, a Mailpit).

Este procedimiento se verificó en el paso 14 sobre un clon limpio del repositorio, con un proyecto de Docker aparte: `make up` y `make seed` dejaron la app funcionando y las 101 pruebas de extremo a extremo pasaron contra esa instalación.

## 4. Producción

### 4.1 Variables de entorno

Copia `.env.example` a `.env` y cambia, como mínimo:

| Variable | Valor en producción |
|----------|---------------------|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Cadena aleatoria larga: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` y `DATABASE_URL` | Una contraseña propia, la misma en ambas |
| `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD` | La cuenta institucional de quien administra y una contraseña fuerte |
| `CORS_ORIGINS` | La URL pública, por ejemplo `https://carpool.unipamplona.edu.co` |
| `SMTP_*` | El servidor de correo institucional (puerto 587 usa STARTTLS) |
| `SMTP_FROM` | Remitente de los códigos, por ejemplo `no-responder@unipamplona.edu.co` |
| `ALLOWED_EMAIL_SUFFIX` | `.edu.co` o, más estricto, `@unipamplona.edu.co` |
| `COOKIE_SECURE` | `true` |

Con `ENVIRONMENT=production` el API **se niega a arrancar** si `SECRET_KEY`, `SUPERADMIN_PASSWORD` o la contraseña de la base siguen con los valores de ejemplo, o si `COOKIE_SECURE` es `false`. El error explica qué cambiar.

### 4.2 Certificado HTTPS

Nginx genera un certificado autofirmado si no encuentra uno en el volumen `certs`. En producción copia el certificado real de la universidad (cadena completa) y su llave:

```sh
docker compose --env-file .env -f infra/docker-compose.yml cp fullchain.pem web:/etc/nginx/certs/server.crt
docker compose --env-file .env -f infra/docker-compose.yml cp privkey.pem  web:/etc/nginx/certs/server.key
docker compose --env-file .env -f infra/docker-compose.yml restart web
```

HTTPS es obligatorio: la ubicación del navegador (viaje en vivo y emergencias) solo funciona en contexto seguro.

### 4.3 Levantar

En producción se usa solo el archivo base (sin el de desarrollo): no publica la base, Redis ni el API, solo Nginx en 80 y 443.

```sh
make osrm && make tiles
docker compose --env-file .env -f infra/docker-compose.yml --profile osrm up -d --build
docker compose --env-file .env -f infra/docker-compose.yml exec -T api python -m app.seed
```

Después, desde **Configuración** como superadmin: revisa los parámetros, el semestre vigente, los lugares (las coordenadas de ejemplo son aproximadas), las reglas de pico y placa (las del seed son de ejemplo) y publica la versión definitiva de los términos y la política de datos cuando la oficina jurídica la apruebe.

### 4.4 Actualizar a una versión nueva

```sh
git pull
docker compose --env-file .env -f infra/docker-compose.yml --profile osrm up -d --build
```

El API aplica las migraciones pendientes al arrancar. El seed es idempotente: se puede volver a correr y nunca sobrescribe datos existentes.

## 5. Respaldos

- El contenedor `backup` hace un `pg_dump` al arrancar y luego cada 24 horas, y conserva los 7 últimos en `backups/`. Si la base no responde, reintenta cada 5 minutos.
- Conviene copiar la carpeta `backups/` fuera del servidor (otro disco o almacenamiento de la universidad).
- Los archivos privados (carnets, licencias, fotos) viven en el volumen `storage`; respáldalo junto con la base.

**Comprobar un respaldo sin tocar nada** (restaura el último en una base aparte, compara filas y la borra):

```sh
make backup-check        # Windows: .\make.ps1 backup-check
```

**Restaurar** sobre la base en uso (detiene y vuelve a levantar `api` y `worker`):

```sh
make restore FILE=carpool-20261007T155151Z.dump      # Windows: .\make.ps1 restore carpool-20261007T155151Z.dump
```

## 6. Verificar una instalación

```sh
curl -k https://localhost/api/v1/health/ready   # {"status":"ok"} con base, PostGIS y Redis
make test                                       # pruebas de backend (cobertura mínima 80 %) y frontend
make e2e-users && make test-e2e                 # solo desarrollo: recorrido completo, cuentas y accesibilidad
```

## 7. Probar desde un celular en la misma red

1. Averigua la IP del equipo en la red local (en Windows, `ipconfig`).
2. En el celular abre `https://<IP-del-equipo>`.
3. El certificado autofirmado mostrará una advertencia. Para usar la ubicación en vivo sin advertencias, genera un certificado de confianza con [mkcert](https://github.com/FiloSottile/mkcert) para esa IP, instala su autoridad en el celular y cópialo al volumen `certs` como en 4.2.

La interfaz se probó en ancho de teléfono (Pixel 7) dentro de la suite E2E; la prueba en un celular físico depende de la red local de cada equipo.

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---------|------------------|
| 502 en todas las llamadas a `/api` | El API está caído o reiniciando: `make logs`. Nginx vuelve a encontrar el API solo, aunque cambie de IP. |
| "Configuración insegura para producción" al arrancar | Faltan las variables de 4.1. |
| No llegan los códigos por correo | Revisa `SMTP_*` y los logs del `worker`. En desarrollo están en Mailpit. |
| "No hay ruta" al publicar | OSRM no tiene datos: `make osrm` y `make up`. |
| El mapa sale en blanco | Faltan las teselas: `make tiles`. |
