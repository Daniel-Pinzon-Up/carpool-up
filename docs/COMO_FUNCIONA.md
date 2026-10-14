# Cómo funciona por dentro

Este documento explica, paso a paso y con referencias al código, cómo están hechas algunas funciones de Carpool UP.

## 1. Código de verificación por correo

Se usa para tres cosas (`AuthPurpose`): verificar el correo al registrarse, el segundo factor al iniciar sesión y recuperar la contraseña.

**Paso a paso**

1. **Se genera el código** (`backend/app/core/security.py`, `new_code`): 6 dígitos al azar con `secrets.randbelow`, un generador seguro para criptografía.
2. **No se guarda el código, sino su huella** (`hash_code`): un HMAC-SHA256 de `propósito:usuario:código` firmado con la clave secreta del servidor. Si alguien roba la base de datos, no puede probar códigos.
3. **Se registra en `auth_codes`** (`backend/app/modules/auth/codes.py`, `CodeService.issue`):
   - se anulan los códigos anteriores del mismo propósito;
   - se guarda la fecha de vencimiento (`auth_code_minutes`, 10 minutos por defecto).
4. **Hay una espera mínima entre envíos** (`auth_code_resend_seconds`, 60 s). Si alguien pide otro antes, recibe `CODE_RESEND_TOO_SOON` con los segundos que faltan.
5. **El correo se envía en segundo plano** (`backend/app/core/email.py`):
   - la API solo encola el trabajo `send_email` en Redis;
   - el worker ARQ lo envía por SMTP con `aiosmtplib`;
   - así la petición responde rápido y un fallo del correo no tumba el registro.
6. **El correo está en español** (`code_email` en `backend/app/core/email.py`): asunto y cuerpo según el propósito del código.
7. **Por dónde sale el correo** lo decide `.env` (`SMTP_*`): con Mailpit (`infra/docker-compose.dev.yml`) los correos quedan en una bandeja de prueba local; con un servidor real, como Gmail con una contraseña de aplicación, llegan al buzón de la persona. Si el servidor falla un momento, el worker reintenta a los 30, 60, 90 y 120 segundos.
8. **El navegador nunca recibe el correo ni el id del usuario**:
   - recibe un `challenge_id` (un token firmado de corta vida);
   - recibe también el correo enmascarado (`email_hint`, por ejemplo `su********@unipamplona.edu.co`).
9. **Al escribir el código** (`CodeService.check`):
   - se compara la huella con `hmac.compare_digest`, que tarda lo mismo acierte o falle;
   - cada error suma un intento, y con `auth_code_max_attempts` (5) el código deja de servir;
   - el error siempre es el mismo (`CODE_INVALID`), así no se puede averiguar qué correos tienen cuenta.

**Protecciones extra**

- **Ingreso:** tras `login_max_attempts` (5) contraseñas fallidas, la cuenta se bloquea `login_lockout_minutes` (15).
- **Correo que no existe:** el servidor gasta el mismo tiempo verificando una contraseña falsa, así la demora no delata si la cuenta existe.
- **Recuperar contraseña** (`forgot_password`): responde lo mismo exista o no la cuenta.
- **Al cambiar la contraseña:**
  - se cierran todas las sesiones;
  - se vuelve a pedir el código en el siguiente ingreso.
- **Las contraseñas** se guardan con argon2id.

Todos los números se pueden cambiar desde Configuración, porque viven en `system_settings`.

## 2. Textos centralizados en español

La app está solo en español, pero los textos no están escritos dentro de los componentes: siguen en un único archivo con **Transloco**.

1. **Un solo archivo de textos:** `frontend/public/i18n/es.json`, organizado por claves (por ejemplo `search.submit`). Las plantillas usan `{{ 'search.submit' | transloco }}`. Cambiar una frase es editar ese archivo, sin tocar el código.
2. **Se carga al abrir la app** (`core/i18n/transloco-loader.ts`) y la configuración (`app.config.ts`) declara `es` como único idioma.
3. **Los errores del servidor también tienen texto:** el backend responde un código (por ejemplo `TRIP_FULL`) y el frontend lo busca en `errors.*`.
4. **Fechas y números** se formatean con la constante `LOCALE = 'es'` (`core/i18n/locale.ts`) y la zona horaria de Bogotá.
5. **Una prueba automática** (`core/i18n/translations.spec.ts`) revisa que ningún texto quede vacío.

## 3. Apariencia

Hay un solo tema, claro, con el estilo de vidrio de la marca.

1. **Los colores son variables CSS** (`frontend/src/styles.css`): cada color es un token como `--bg`, `--text` o `--primary`, y los componentes nunca escriben un color fijo.
2. **El mapa** usa un único estilo claro (`shared/map/map-style.ts`) con la ruta en el azul de la marca.
3. **Accesibilidad:** el contraste está medido (WCAG AA) y las pruebas E2E pasan axe en las pantallas principales.

## 4. Avisos y chat en tiempo real

Cuando un conductor acepta una reserva, el pasajero se entera sin recargar la página.

1. **Al abrir la app** (`core/ws/realtime.service.ts`):
   - el navegador abre un WebSocket a `/ws`;
   - lo primero que envía es su token;
   - si el token no sirve, el servidor cierra la conexión (códigos 4401 y 4001).
2. **Cada conexión escucha sus canales** (`backend/app/modules/live/connection.py`):
   - `user:{id}` para los avisos personales;
   - `conv:{id}` para cada chat donde participa;
   - `trip:{id}:loc` para la ubicación del viaje en curso;
   - `admin:emergencies` si es administrador.
3. **Los servicios no envían directamente** (`backend/app/core/realtime.py`, `emit`):
   - dejan el evento en una cola ligada a la transacción de la base;
   - si la transacción se confirma, el evento se publica en Redis;
   - si se deshace, se descarta; así nadie recibe un aviso de algo que no ocurrió.
4. **Redis reparte el evento** (pub/sub) a todas las conexiones interesadas, aunque estén en procesos distintos de la API.
5. **En Angular**, las pantallas se suscriben con `realtime.on('tipo')`. Por ejemplo, la de emergencias escucha `emergency` y `emergency.handled`.
6. **Si se cae la conexión**, el servicio reconecta solo al volver internet o al regresar a la pestaña, y las pantallas recargan lo que haga falta.

## 5. Subida segura de documentos (carnet y licencia)

`backend/app/core/storage.py`, `save_private_file`

1. **Tamaño máximo:** se lee el archivo con un límite (`max_upload_mb`). Si lo pasa, la lectura se corta sin cargarlo entero (`FILE_TOO_LARGE`).
2. **Tipo real del archivo:** no se confía en el nombre ni en lo que declara el navegador.
   - Se revisan los primeros bytes, la "firma" del archivo, y solo se aceptan JPG, PNG, WebP y PDF.
   - Cualquier otro tipo se rechaza con `FILE_TYPE_NOT_ALLOWED`.
3. **Imágenes limpias:**
   - se borran los metadatos EXIF, como la ubicación GPS de la foto;
   - se endereza la imagen;
   - hay un tope de píxeles para que una imagen gigante no tumbe el servidor.
4. **Almacenamiento privado:**
   - el nombre del archivo es aleatorio (`secrets.token_hex`);
   - se guarda en una carpeta privada con permisos solo para el servidor;
   - no hay URL pública.
5. **Solo los administradores pueden verlo** (`private_file_response`):
   - se sirve únicamente por una ruta protegida;
   - va con `Cache-Control: private, no-store`, así el navegador no guarda copia;
   - lleva una cabecera que impide al navegador "adivinar" el tipo;
   - se valida que la ruta no se salga de la carpeta.

## 6. Búsqueda de viajes cerca de la ruta

`backend/app/modules/search/service.py`

1. **La ruta de cada viaje** es una línea geográfica (PostGIS, `LINESTRING`) calculada con OSRM sobre las calles de Pamplona. Se guarda con un índice espacial.
2. **Un viaje aparece en los resultados si cumple todo esto, en una sola consulta SQL:**
   - pasa a menos de `search_radius_meters` (500 m) de tu recogida y de tu bajada (`ST_DWithin`);
   - te recoge antes de dejarte: la posición de la recogida a lo largo de la línea es menor que la de la bajada (`ST_LineLocatePoint`);
   - sale dentro de `search_time_window_minutes` (60) de la hora pedida;
   - está programado, tiene cupo y sus reglas son compatibles con tus preferencias.
3. **Punto de encuentro:** se calcula el punto exacto de la ruta más cercano a ti (`ST_LineInterpolatePoint`) y cuántos metros caminas hasta él.
4. **Orden de los resultados:** primero la recogida más cercana, después la menor diferencia de hora y luego la mejor calificación del conductor.

## 7. Pico y placa automático

`backend/app/modules/pico_placa/service.py` y `backend/app/modules/trips/service.py`

1. **Las reglas** están en `pico_placa_rules`:
   - tipo de vehículo, día de la semana y dígitos restringidos;
   - fechas de vigencia;
   - el superadmin las edita desde Configuración.
2. **El dígito que cuenta** es el último dígito numérico de la placa (`last_digit`). En las motos, la placa termina en letra, así que se toma el número anterior: ABC12D → 2.
3. **Al publicar:** si ese día el vehículo tiene pico y placa, no deja publicar (`PICO_PLACA_RESTRICTED`). 
4. **Revisión diaria** (`recheck_pico_placa`): el worker revisa todos los viajes futuros, y también lo hace cuando cambian las reglas.
   - Si un viaje cae en pico y placa, pasa a `cancelled_pico_placa`.
   - Sus reservas se cancelan con aviso a cada pasajero.
   - Si una regla deja de aplicar, el viaje se restaura.

## 8. Ubicación en vivo

1. **Solo comparte el conductor:** el viaje debe estar en curso y él lo inicia.
2. **El navegador del conductor:**
   - toma el GPS (`navigator.geolocation`);
   - envía `location.update` por el WebSocket cada 5 segundos;
   - mantiene la pantalla encendida con Wake Lock mientras comparte.
3. **El servidor** (`modules/live/connection.py`):
   - verifica que quien envía sea el conductor de ese viaje;
   - acepta como máximo una posición cada 2 segundos.
4. **Solo se guarda la última posición:**
   - va en Redis y vence sola (`live_location_ttl_seconds`, 120 s);
   - no se guarda el historial del recorrido, por privacidad.
5. **Quién la ve:** se difunde por `trip:{id}:loc` a los pasajeros aceptados, que ven el carro moverse en el mapa (MapLibre).
6. **Al finalizar el viaje** se borra la ubicación y los enlaces compartidos dejan de funcionar poco después.
