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

## Paso 2. Autenticación y cuentas

| # | Decisión | Motivo |
|---|----------|--------|
| 2.1 | Registro, 2FA y recuperación devuelven un `challenge_id` (JWT firmado, tipo `challenge`, vigencia igual a la del código). La verificación recibe `challenge_id` + código de 6 dígitos. | El correo no viaja en cada paso y la recuperación responde igual exista o no la cuenta. |
| 2.2 | Verificar el correo al registrarse cuenta como el 2FA del primer ingreso: abre la sesión y deja `two_factor_required` en falso. Restablecer la contraseña lo vuelve a poner en verdadero. | El plan pide 2FA "solo en el primer ingreso"; pedir dos códigos seguidos al mismo correo no agrega seguridad. |
| 2.3 | El refresh token es `<id de sesión>.<secreto>`; se guarda solo el SHA-256 del secreto y rota en cada uso. Presentar un secreto viejo de una sesión revoca todas las sesiones del usuario (`REFRESH_REUSED`). | Detecta el robo de tokens sin guardar historial. |
| 2.4 | El token de acceso lleva el id de la sesión (`sid`) y cada petición verifica que la sesión siga activa. | "Cerrar sesión en otros dispositivos" y el cambio de contraseña cortan el acceso de inmediato, no a los 15 minutos. Cuesta una consulta por petición. |
| 2.5 | Refresh en cookie `cp_refresh`: HttpOnly, Secure, SameSite=Lax, ruta `/api/v1/auth`, 30 días. El token de acceso vive solo en memoria del navegador; al abrir la app se recupera la sesión con `POST /auth/refresh`. | Ningún token queda en `localStorage`. Los navegadores envían cookies Secure a `http://localhost`, así que funciona en desarrollo. |
| 2.6 | Un solo error `CODE_INVALID` para código equivocado, vencido, agotado o inexistente. | Distinguirlos permitiría averiguar si un correo tiene cuenta. |
| 2.7 | Bloqueo temporal tras `login_max_attempts` (5) intentos fallidos durante `login_lockout_minutes` (15). Con un correo inexistente se compara contra un hash fijo para igualar el tiempo de respuesta. | Sección 11. |
| 2.8 | Parámetros nuevos en `system_settings`: `password_min_length`, `login_max_attempts`, `login_lockout_minutes`, `auth_code_minutes`, `auth_code_max_attempts`, `auth_code_resend_seconds` (60) y `max_upload_mb`. | Toda regla configurable vive en la tabla. |
| 2.9 | Los correos los envía el worker ARQ (`send_email`, hasta 5 reintentos). La API solo encola. Plantillas en los cuatro idiomas según `preferred_language`. | Una caída del SMTP no tumba el registro; el usuario puede pedir reenvío. |
| 2.10 | Archivos: tipo detectado por los primeros bytes (JPG, PNG, WebP, PDF), tamaño máximo configurable, nombre aleatorio, permisos 600 en una carpeta 700 del volumen privado. Las imágenes se vuelven a codificar con Pillow para eliminar EXIF (GPS, cámara), respetando la orientación. | Sección 11. Servirlos a administradores llega en el paso 3. |
| 2.11 | La licencia del conductor no se pide en el registro; se sube en el paso 3 junto con la cola de aprobación. | El plan la ubica en `PUT /users/me/license` y en la cola del paso 3. |
| 2.12 | Pueden iniciar sesión las cuentas `pending_approval` y `suspended` (ven su estado y suben documentos); `blocked` no. Las funciones exigen cuenta `active`. | Sección 6.1. |
| 2.13 | Subir un documento cuando hay uno pendiente lo reemplaza (se borra el archivo anterior); si el último está aprobado, rechazado o vencido, se crea uno nuevo para el semestre vigente. | "Puede subir o reemplazar documentos". |
| 2.14 | El registro guarda la aceptación de las versiones vigentes (en el idioma del usuario, o en español si falta). Al publicarse una versión nueva aparece en `pending_legal` de `/users/me` y se acepta con `POST /legal/accept`. La interfaz no deja seguir hasta aceptarla. | Ley 1581: evidencia de qué versión se aceptó. El bloqueo por API para usuarios con versiones pendientes queda para el paso 14 (revisión de seguridad). |
| 2.15 | El usuario puede cambiar programa, idioma, tema y (solo conductores) la nota de pago. Nombre, sexo y rol los valida la administración. | El sexo habilita viajes "solo mujeres" y lo verifica el administrador. |
| 2.16 | La bienvenida de 3 pasos se muestra una vez por dispositivo (`cp.onboarded`). Rutas: `/bienvenida`, `/ingresar`, `/registro`, `/verificar`, `/recuperar`, `/restablecer`, `/cuenta/estado`, `/cuenta/terminos`, `/legal/terminos`, `/legal/datos`, `/perfil`. Cada rol tiene su inicio (`/buscar`, `/inicio`, `/admin`). | Un solo lugar (`homeFor`) decide a dónde va cada quien. |
| 2.17 | Idioma y tema se sincronizan con el perfil: al iniciar sesión manda el perfil; después, cada cambio en el dispositivo se guarda en el perfil. | Sección 12.1. |
| 2.18 | El catálogo de componentes salió del layout autenticado: `/catalogo` sigue disponible solo en desarrollo y sin sesión. | Es una herramienta de diseño, no una pantalla del producto. |

## Paso 3. Aprobaciones y revalidación

| # | Decisión | Motivo |
|---|----------|--------|
| 3.1 | Una sola cola para carnets, constancias y licencias, separada por `type` (`identity` o `license`) y atendida en orden de llegada. Los ids son UUID, así que `/admin/approvals/{id}` funciona para ambas tablas. | Es la "misma cola" del plan y simplifica el panel. |
| 3.2 | La cola muestra nombre, programa, rol, sexo declarado y estado del solicitante, pero no su correo ni su teléfono. | Sección 11: ningún endpoint devuelve datos de contacto de otros usuarios. |
| 3.3 | Al aprobar un carnet el revisor confirma el sexo; si el documento muestra otro, lo corrige y queda en la auditoría (antes y después). | Sección 2: el administrador verifica el sexo al aprobar. |
| 3.4 | Un documento aprobado queda ligado al semestre vigente y `valid_until` es el fin del semestre. Si no había semestre al subirlo, se liga al vigente al aprobarlo. | Un documento por semestre. |
| 3.5 | Nadie revisa sus propios documentos y no se puede revisar dos veces (`APPROVAL_NOT_PENDING`). | Evita conflictos de interés y carreras entre administradores. |
| 3.6 | Una licencia vencida no se puede aprobar ni subir. Subir otra reemplaza la anterior y vuelve a revisión. | "Sin licencia aprobada y vigente no pueden publicar". |
| 3.7 | `can_publish` en `/users/me`: conductor activo con licencia aprobada y vigente. El paso 4 agrega el requisito de vehículo activo. | Un solo lugar para esa regla. |
| 3.8 | Archivos: `/admin/files/{id}` para administradores y `/users/me/documents/{id}/file` y `/users/me/license/file` para el dueño, con `Cache-Control: private, no-store`. La interfaz los descarga con el token y los muestra como object URL. | El token nunca va en una URL y el archivo no queda en caché. |
| 3.9 | La CSP permite `frame-src 'self' blob:` (visor de PDF) y agrega `object-src 'none'`. | El visor usa object URLs locales. |
| 3.10 | Revalidación diaria (`semester_revalidation`, 5:05 a. m. de Pamplona, y al arrancar el worker). Con semestre vigente: vencen los carnets aprobados de otros semestres y se avisa. Pasado `revalidation_deadline`: pasajeros y conductores activos sin carnet aprobado del semestre vuelven a `pending_approval`. Administradores y superadmin no revalidan. Sin semestre vigente (vacaciones) no hace nada. | Sección 7.1. Es idempotente. |
| 3.11 | El superadmin crea administradores con una clave inicial; el primer ingreso pide el código por correo. | El plan no define el envío de invitaciones; esto es lo más simple y seguro. |
| 3.12 | El superadmin cambia roles entre pasajero, conductor y administrador. No puede cambiar el suyo ni asignar superadmin. Si deja de ser conductor se borra la nota de pago. | Sección 2. Queda en la auditoría y se avisa al usuario. |
| 3.13 | Las notificaciones internas se adelantan: tabla, bandeja (`/notifications`) y pantalla. El paso 9 agrega la entrega en tiempo real. | Aprobaciones y vencimientos deben avisar al usuario. |
| 3.14 | La campana de avisos está en el encabezado para todos los roles. | La barra del conductor no tiene "Notificaciones" entre sus 5 destinos. |
| 3.15 | La interfaz para crear administradores y cambiar roles llega en el paso 12 (panel del superadmin). | En este paso basta la API. |

## Paso 4. Vehículos

| # | Decisión | Motivo |
|---|----------|--------|
| 4.1 | Placas colombianas: carro `ABC123` y moto `ABC12D`. Se aceptan con espacios, guiones o minúsculas y se guardan normalizadas en mayúsculas. Otros formatos (diplomáticas, remolques) no se aceptan. | Son los formatos de uso particular; el resto no aplica a la comunidad universitaria. |
| 4.2 | Capacidad = puestos totales con el conductor: carro de 2 a 8, moto exactamente 2. También la valida una restricción `CHECK` en la base. Año entre 1980 y el próximo año. | Sección 5.4. |
| 4.3 | Tipo y placa no se editan: un cambio de vehículo es un vehículo nuevo. | Los viajes guardan el vehículo con el que se publicaron. |
| 4.4 | Borrado lógico (`deleted_at`) y placa única solo entre vehículos no borrados (índice único parcial). Un vehículo borrado libera su placa. | "Borrados lógicos en vehículos". |
| 4.5 | Impedir borrar vehículos con viajes programados se agrega en el paso 6, cuando existan los viajes. | Todavía no hay viajes. |
| 4.6 | Fotos de vehículos: solo imágenes (JPG, PNG, WebP), sin EXIF, visibles para cualquier usuario con sesión. | Sección 11. |
| 4.7 | Requisitos para publicar en un solo lugar (`publishing_blockers`): cuenta activa, licencia aprobada y vigente y al menos un vehículo activo. `/users/me` devuelve `publish_blockers` con los motivos y la API del paso 6 usará `require_can_publish` (`PUBLISH_NOT_ALLOWED`). | Criterio de aceptación del paso 4 y del paso 6. |
| 4.8 | El inicio del conductor (`/inicio`) muestra la lista de requisitos con su estado y el botón Publicar deshabilitado con la explicación. `/publicar` exige `can_publish` y, si no, redirige a `/inicio`. | Prevención de errores (Nielsen) y aceptación del paso. |
| 4.9 | Licencia y vehículos se gestionan desde el inicio del conductor y el perfil, no desde la barra inferior. | La barra admite cinco destinos y ya están definidos en el plan. |

## Paso 5. Rutas y mapas

| # | Decisión | Motivo |
|---|----------|--------|
| 5.1 | OSRM corre con un recorte de Pamplona (caja -72.75, 7.30, -72.55, 7.48), no con Colombia completa. `make osrm` descarga el extracto de Geofabrik, lo recorta con pyosmium (`infra/osrm/clip.py`: vías con algún nodo en la caja más sus restricciones de giro), lo procesa con el perfil `car` y MLD y borra el extracto. Quedan unos 3 MB. | El grafo de Colombia necesita varios GB de RAM; el servicio solo opera en Pamplona. |
| 5.2 | El mismo grafo (perfil `car`) sirve para carro y moto. | En vías urbanas la diferencia de tiempos es menor que el ajuste por tráfico. Un perfil de moto duplicaría datos y memoria. |
| 5.3 | El servicio `osrm` está en el perfil `osrm` de Compose y `make up` lo activa solo si existen los datos. Sin OSRM la API responde `ROUTING_UNAVAILABLE` (503) y la interfaz lo explica. | Se puede trabajar en el resto de la app sin generar el mapa. |
| 5.4 | Las rutas se guardan en Redis 24 horas, con las coordenadas redondeadas a 5 decimales (cerca de 1 m) como clave. | Mismos puntos dan la misma ruta; evita llamar a OSRM en cada cambio del formulario. |
| 5.5 | ETA = duración de OSRM por tramo × factor de tráfico. El factor sale de `traffic_factors` según el día (entre semana, sábado o domingo) y la hora de salida en la zona de Pamplona. Se siembran las 72 franjas con 1.0 y `samples = 0`; el paso 13 las recalcula con viajes reales. Sin hora de salida el factor es 1.0 y solo se dan desfases (+N min). | Sección 7.4: el factor se aprende de los viajes. |
| 5.6 | Aporte sugerido por cupo = km × `cost_per_km` del tipo de vehículo ÷ (cupos + 1), redondeado a la centena y con tope `max_price_per_seat`. El "+1" es el conductor, que también paga su parte. Si el costo no está configurado, `suggested_price` es nulo y la interfaz lo dice. | Sección 10: compartir gastos, no lucrarse. |
| 5.7 | Una ruta admite como máximo `max_trip_stops` paradas intermedias (5 por defecto, parámetro nuevo). | Muchas paradas alargan el viaje y bajan la puntualidad. |
| 5.8 | Los puntos son lugares del catálogo, pines propios o coordenadas, siempre dentro de `service_area`. Los pines de otro usuario no se pueden usar (`PLACE_NOT_FOUND`). | Ubicaciones privadas: un pin solo es visible en los viajes donde se usa. |
| 5.9 | Mapa base propio: teselas PMTiles de Protomaps recortadas a la misma caja (`make tiles`, cerca de 1 MB, servidas por Nginx con rangos), fuentes Noto Sans y sprites en `frontend/public/map`. En desarrollo `ng serve` hace proxy de `/tiles` a Nginx. | La CSP no permite recursos externos y no hay dependencia de servicios de mapas de terceros. |
| 5.10 | MapLibre (1 MB) y su hoja de estilos se cargan solo cuando una pantalla muestra un mapa. El aviso de tamaño del bundle inicial sube de 600 kB a 700 kB: ya estaba en 618 kB después del paso 4. | La carga inicial solo crece 9 kB en este paso. |
| 5.11 | El mapa es complementario: distancia, duración, paradas con hora y precio siempre están en texto, y los lugares se eligen con un combobox accesible con teclado. Elegir en el mapa crea un pin propio. | WCAG AA: la información no depende de ver el mapa. |
| 5.12 | El planificador de rutas es el primer paso del asistente de `/publicar`. El paso 6 agrega fecha, recurrencia, reglas y la publicación. | El plan pide ver la ruta antes de publicar. |

## Paso 6. Publicación de viajes y series

| # | Decisión | Motivo |
|---|----------|--------|
| 6.1 | Todos los puntos de un viaje son lugares (`place_ids`): del catálogo o pines propios. Las coordenadas sueltas solo sirven en la vista previa. | `trip_stops` y `series_stops` referencian `places`, y los pines ya son lugares de tipo `custom`. |
| 6.2 | Antelación mínima `trip_publish_min_lead_minutes` (15) y viajes puntuales hasta `trip_max_days_ahead` (60 días). Parámetros nuevos. | El plan pide "fecha y hora futuras" sin límites; estos evitan viajes imposibles de reservar o publicados por error muy lejos. |
| 6.3 | Las horas se interpretan en la zona de Pamplona (America/Bogota, sin horario de verano). La serie guarda `departure_time` local y cada ocurrencia su instante en UTC. Los días de la semana van de 0 (lunes) a 6 (domingo), como en `pico_placa_rules`. | Una sola convención en toda la app. |
| 6.4 | La serie se ancla al semestre que contiene su fecha de inicio. Ventana: `start + días - 1` o el fin del semestre, lo que llegue primero (`semester` = fin del semestre). Fuera de un semestre la serie se rechaza (`SERIES_OUTSIDE_SEMESTER`). Los viajes puntuales no necesitan semestre. | "window_end nunca supera semesters.ends_on". En vacaciones aún se pueden ofrecer viajes puntuales. |
| 6.5 | Las ocurrencias se generan de una vez, desde la primera fecha que cumple la antelación mínima y el corte de edición. Si ninguna queda reservable (todas en pico y placa o ninguna fecha) se rechaza con `SERIES_EMPTY`. | Una serie sin viajes reservables no le sirve a nadie. |
| 6.6 | Pico y placa se evalúa por fecha (el servicio `pico_placa` es la única fuente de verdad). Puntual en fecha restringida: `PICO_PLACA_RESTRICTED`. Ocurrencia: `cancelled_pico_placa`. Al crear, editar o borrar una regla y cada día (worker, 5:15 a. m.) se revisan los viajes futuros: los nuevos restringidos se cancelan y los que dejan de estarlo vuelven a `scheduled`, con aviso al conductor. | Sección 7.2 y job `recheck_pico_placa`. Restaurar evita perder viajes por una regla corregida. |
| 6.7 | Un conductor no puede tener dos viajes programados o en curso que se crucen en el tiempo (salida más duración estimada): `TRIP_OVERLAP` con las fechas en conflicto. Los tramos que solo se tocan no se cruzan. | Es físicamente imposible y confundiría a los pasajeros. |
| 6.8 | Editar un viaje (fecha, ruta, vehículo, puestos, precio o reglas) se permite hasta `trip_edit_cutoff_minutes` (30) antes de salir; la ruta y las ETA se recalculan. Cancelar exige motivo (5 a 500 caracteres). Avisar a los pasajeros con reserva y cancelar sus reservas llega en el paso 8. | Sección 7.2. |
| 6.9 | Editar una serie cambia la plantilla (días, hora, ruta, vehículo, puestos, precio, reglas; la ventana no) y rehace las ocurrencias futuras después del corte: las fechas que siguen se actualizan en su lugar, las que salen se quitan (borrado lógico) y las nuevas se crean. Pasadas, en curso y canceladas no cambian. El paso 8 agrega la confirmación cuando hay reservas. | Actualizar en su lugar conserva las reservas cuando existan. |
| 6.10 | Cancelar una serie cancela todas sus ocurrencias futuras programadas con el mismo motivo. Las series cuya ventana terminó pasan a `finished` en el job diario. | Sección 6. |
| 6.11 | Duplicar copia ruta, vehículo, puestos, precio y reglas con una fecha nueva (viaje) o un inicio y ventana nuevos (serie), y pasa por todas las validaciones de publicar. | "Duplicar viaje copia el viaje o la serie con nueva fecha". |
| 6.12 | "Solo mujeres" solo lo publica una conductora (`WOMEN_ONLY_FEMALE_DRIVERS`); se guarda solo si está activo. Las demás reglas son `allowed`/`not_allowed` o se omiten; `custom` es texto libre de hasta 200 caracteres. Cada tipo aparece una vez. | Sección 7.2 y modelo de `trip_rules`. |
| 6.13 | El detalle de un viaje lo ve cualquier usuario activo si está programado o en curso; el conductor ve también los suyos cancelados o pasados. La placa solo la ve el conductor (el paso 8 la muestra al pasajero aceptado). Del conductor solo se expone id y nombre. | Sección 11: no exponer datos privados. |
| 6.14 | Un vehículo con viajes programados o en curso no se puede borrar ni desactivar (`VEHICLE_HAS_TRIPS`). | Sección 5.4. |
| 6.15 | El asistente de publicación reemplaza al planificador del paso 5: tipo, ruta, fecha u horario (con las fechas de pico y placa marcadas), vehículo y puestos, aporte (sugerido, editable, con tope), reglas y resumen. El mismo asistente edita viajes y series. Mis viajes del conductor tiene Próximos, Series e Historial; la vista del pasajero llega en el paso 8. | Sección 13. |
| 6.16 | `driver_cancellations` se calculará en el paso 11 a partir de `trips.status = cancelled_by_driver`. | `user_stats` llega en el paso 11. |
