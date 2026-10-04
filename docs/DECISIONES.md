# Decisiones del proyecto

Registro de decisiones tomadas durante la construcción que no estaban cerradas en el plan maestro, o que lo ajustan. Cada entrada indica el paso en que se tomó.

## Paso 0. Cimientos

| # | Decisión | Motivo |
|---|----------|--------|
| 0.1 | El repositorio Git vive en `carpool_U/` con rama `main`. | La carpeta personal del usuario ya era un repositorio; el proyecto necesita el suyo propio. |
| 0.2 | La raíz del monorepo es `carpool_U/` (equivale a `carpool/` del plan). | Nombre de carpeta existente. |
| 0.3 | Python 3.12 se gestiona con `uv` (dependencias en `pyproject.toml` y `uv.lock`). | El sistema tiene Python 3.14; uv instala 3.12 aislado y fija versiones. |
| 0.4 | Además del `Makefile` existe `make.ps1` con los mismos objetivos. | Windows no trae `make`. |
| 0.5 | Los iconos usan `@lucide/angular` (no `lucide-angular`). | `lucide-angular` no es compatible con Angular 22; `@lucide/angular` es el paquete oficial actual, standalone y basado en Signals. |
| 0.6 | El frontend fija `vite@8.3.0` y `rolldown@1.2.8` con `overrides` en `package.json`. | Smart App Control de Windows bloquea el binario nativo de rolldown 1.2.12 que traía Vitest; 1.2.8 es la versión que ya usa Angular. Se puede quitar cuando ambas versiones coincidan. |
| 0.7 | El catálogo de componentes vive en `/catalogo` y solo existe en modo desarrollo. | Es una herramienta interna del paso 0, no una pantalla del producto. |
| 0.8 | `map-view`, `place-picker` y `route-summary` se construyen en el paso 5. | Dependen de MapLibre, PMTiles y del módulo de rutas. |
| 0.9 | Prefijo de componentes y directivas: `cp` (`cp-glass-card`, `button[cp-button]`). | Prefijo corto y propio del proyecto. |
| 0.10 | Los colores salen solo de variables CSS (`--bg`, `--text`, `--accent`...); no se usan variantes `dark:` de Tailwind. | Permite forzar un tema en un contenedor (`.theme-light`, `.theme-dark`) y simplifica el contraste. |
| 0.11 | Ajustes de color para contraste AA en tema claro: `--accent` #0B7A5A (antes #0E9F75) y `--warning` #865C00 (antes #9A6A00). | Con los valores originales el texto blanco sobre menta daba 3,4:1 y el texto de advertencia 4,2:1; los nuevos superan 4,5:1. El plan permite afinar los valores. |
| 0.12 | La barra inferior móvil usa etiquetas cortas (`navShort.*`, por ejemplo "Avisos" en lugar de "Notificaciones"). | Las etiquetas completas no caben en 400 px; la barra lateral sigue usando las completas. |
| 0.13 | El script que aplica tema, transparencia e idioma antes de arrancar Angular está en `public/theme-init.js`, no inline. | Permite una CSP con `script-src 'self'` sin hashes ni `unsafe-inline`. |
| 0.14 | Se desactiva `inlineCritical` en el build de producción. | El CSS crítico inline usa un manejador `onload` que la CSP bloquearía. |
| 0.15 | `style-src` incluye `'unsafe-inline'`. | Angular inyecta los estilos de componentes en etiquetas `<style>`. Se puede endurecer más adelante con nonce (`ngCspNonce`). |
| 0.16 | Nginx genera un certificado autofirmado al arrancar si no hay uno montado en `/etc/nginx/certs`. | La geolocalización exige HTTPS incluso en local. |
| 0.17 | OSRM está en el perfil `osrm` de Compose y no arranca con `make up` hasta el paso 5. | Necesita los datos preprocesados de Pamplona. |
| 0.18 | El contenedor `backup` hace `pg_dump` diario y conserva los 7 últimos en `backups/`. | Requisito de respaldo diario. |
| 0.19 | Las pruebas de backend usan la base `carpool_test` (creada por `infra/db/init`); las que necesitan servicios reales llevan la marca `integration`. | Separar datos de desarrollo y de pruebas. |
| 0.20 | Las rutas de la interfaz están en español (`/buscar`, `/mis-viajes`); los títulos de página se traducen. | Público principal hispanohablante; las URL no cambian con el idioma. |

## Paso 1. Configuración y catálogos

| # | Decisión | Motivo |
|---|----------|--------|
| 1.1 | La tabla `users` (completa según la sección 5.3) y la validación del token de acceso JWT se adelantan a este paso. Login, registro, sesiones y 2FA siguen en el paso 2. | Los endpoints del superadmin necesitan autorización por rol y la auditoría necesita `actor_id`. |
| 1.2 | Para probar la API a mano antes del paso 2 existe `python -m app.cli token <correo>` (`make token EMAIL=...`), que se niega a correr en producción. | No hay login todavía. |
| 1.3 | Módulos nuevos además de los del plan: `audit`, `semesters` y `pico_placa`. | Cada tabla de configuración tiene sus propias reglas y su propio router; meterlas en `settings` o `admin` mezclaría responsabilidades. |
| 1.4 | `system_settings` usa la clave como llave primaria (sin `id` uuid). | Es un identificador natural, estable y único. |
| 1.5 | El tipo y la validación de cada parámetro viven en `settings/definitions.py`; el valor vigente siempre se lee de la tabla. La validación es estricta (`true` no vale como `1`, `"2"` no vale como `2`). | Cumple "toda regla configurable vive en system_settings" sin perder validación. |
| 1.6 | `cost_per_km_car`, `cost_per_km_motorcycle` y `max_price_per_seat` se siembran vacíos (`null`). | El plan dice que los define el superadmin; no se inventan valores. El paso 5 debe rechazar el cálculo de precio mientras estén vacíos. |
| 1.7 | Parámetro nuevo `service_area`: caja geográfica de Pamplona y alrededores (lat 7.33 a 7.43, lon -72.70 a -72.59). Los puntos fuera de ella se rechazan con `PLACE_OUT_OF_AREA`. | "Solo trayectos dentro de Pamplona" necesita un límite configurable. |
| 1.8 | Todos los parámetros se exponen en `GET /meta/settings/public`. | Ninguno es secreto y la interfaz los necesita para explicar reglas y prevenir errores. |
| 1.9 | Los semestres no se pueden solapar: lo valida el servicio (`SEMESTER_OVERLAP`) y, ante carreras, una restricción de exclusión `EXCLUDE USING gist` en PostgreSQL. Dos semestres sí pueden ser contiguos. | Requisito del plan; la base tiene la última palabra. |
| 1.10 | `revalidation_deadline` por defecto es `starts_on + revalidation_days`, sin pasar de `ends_on`. | El plan dice "por defecto starts_on + 1 mes, configurable". |
| 1.11 | El "hoy" del semestre actual y de pico y placa se calcula en hora de `America/Bogota`. Se agrega la dependencia `tzdata`. | La base guarda UTC; las fechas de calendario son locales. Windows y algunas imágenes no traen la base de zonas horarias. |
| 1.12 | Los lugares no se borran: `DELETE /admin/places/{id}` los desactiva. | Viajes y reservas pasadas pueden apuntar a ellos. |
| 1.13 | Los pines libres (`kind = custom`) solo los crean cuentas activas, nunca aparecen en el catálogo y el superadmin no los edita desde el catálogo. | Sección 5.4: "no aparecen en el catálogo público". |
| 1.14 | Pico y placa: `weekday` 0 = lunes (igual que Python). Se usa el último dígito numérico de la placa. Una regla tiene vigencia `valid_from`/`valid_to` y puede desactivarse. | Las placas de moto terminan en letra. |
| 1.15 | El job `recheck_pico_placa` al editar reglas se conecta en el paso 6. | Todavía no existen viajes que recalcular. |
| 1.16 | Los documentos legales no se editan: cada cambio es una versión nueva (`1.0`, `1.1`...). Publicar una versión la deja vigente y retira la anterior del mismo tipo e idioma. Si falta un idioma se sirve el español. | Evidencia de qué versión aceptó cada usuario (Ley 1581). |
| 1.17 | El seed publica la versión 1.0 en español de los términos y de la autorización de datos como **borradores pendientes de revisión jurídica**. | El plan recomienda revisión de la oficina jurídica. |
| 1.18 | `audit_log` es inmutable: un trigger bloquea UPDATE y DELETE. La única excepción es el `SET NULL` de `actor_id` al borrar un usuario. Su `created_at` usa `clock_timestamp()`. | "Solo se inserta". `now()` es igual para toda la transacción y desordenaba las entradas de una misma operación. |
| 1.19 | Datos semilla de ejemplo: semestre por mes (febrero a junio, agosto al 15 de diciembre), 7 puntos con **coordenadas aproximadas** y pico y placa de ejemplo de lunes a viernes, dos dígitos por día, para carro y moto. | El equipo debe cargar los datos reales desde el panel. |
| 1.20 | `SECRET_KEY` debe tener al menos 32 caracteres. | HS256 requiere claves de 32 bytes o más (RFC 7518). |
| 1.21 | La cobertura se mide con `concurrency = ["greenlet", "thread"]`. | Sin esto coverage pierde las líneas que SQLAlchemy asíncrono ejecuta en greenlets. |
