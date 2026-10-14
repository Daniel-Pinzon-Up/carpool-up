# Frontend de Carpool UP

Aplicación web en Angular 22 (componentes independientes, señales y sin zone.js) con Tailwind CSS 4, Transloco para los textos en cuatro idiomas, MapLibre para los mapas e íconos de Lucide. Es una sola aplicación que se adapta al rol: pasajero, conductor, administrador o superadmin ven menús y pantallas distintas. Funciona en celular y en computador.

## Estructura

```
frontend/
├── src/
│   ├── main.ts               arranque de Angular
│   ├── index.html            página base (carga theme-init.js antes de Angular)
│   ├── styles.css            colores como variables, temas claro y oscuro, estilo glass
│   ├── testing/              utilidades compartidas por las pruebas unitarias
│   └── app/
│       ├── app.ts            componente raíz
│       ├── app.config.ts     proveedores: router, HTTP con interceptores, Transloco
│       ├── app.routes.ts     todas las rutas, con guardas por sesión, estado y rol
│       ├── core/             servicios que existen una sola vez
│       ├── features/         una carpeta por pantalla o flujo
│       └── shared/           piezas reutilizables
├── public/
│   ├── i18n/                 es.json, en.json, pt.json, fr.json: todos los textos de la app
│   ├── map/                  fuentes y sprites del mapa base
│   ├── brand/                logo, ilustraciones e íconos de la app
│   ├── manifest.webmanifest
│   └── theme-init.js         aplica el tema guardado antes de que cargue Angular
├── e2e/                      pruebas de punta a punta y de accesibilidad (Playwright)
├── scripts/generate-icons.mjs  genera shared/icons/lucide.ts con solo los íconos usados
├── angular.json · tsconfig*.json · eslint.config.js
├── proxy.conf.json           en desarrollo manda /api, /ws y /tiles al backend y a Nginx
├── playwright.config.ts
└── Dockerfile                compila la app y la sirve con Nginx
```

### `src/app/core/`

| Carpeta | Contenido |
|---------|-----------|
| `auth/` | Sesión (`AuthService`), guardas de rutas, interceptor que agrega y renueva el token, sincronización de preferencias |
| `http/` | Interceptores de errores e idioma; traduce el código de error de la API a un mensaje |
| `ws/` | `RealtimeService`: WebSocket con reconexión, por donde llegan avisos, mensajes y ubicación |
| `layout/` | Menú y estructura de la app según el rol (barra inferior en celular, lateral en computador) |
| `i18n/` · `theme/` · `storage/` | Idioma activo, tema claro/oscuro y preferencias locales |
| `notifications/` · `location/` · `meta/` · `files/` · `guards/` | Contador de avisos, compartir ubicación, configuración pública, archivos privados, rutas solo de desarrollo |

### `src/app/features/`

| Carpeta | Pantallas |
|---------|-----------|
| `auth/` · `account/` | Bienvenida, ingreso, registro en cuatro pasos, códigos, recuperación, estado de la cuenta y aceptación de términos |
| `search/` | Buscar viajes y resultados |
| `publish/` | Asistente para publicar o editar un viaje o una serie |
| `trips/` | Mis viajes del conductor, detalle del viaje, serie, viaje en curso |
| `bookings/` | Panel de reserva, Mis viajes del pasajero, bandeja de solicitudes del conductor |
| `chat/` · `notifications/` | Mensajes y avisos |
| `ratings/` · `stats/` | Calificar, historial y estadísticas |
| `vehicles/` · `license/` · `driver/` | Vehículos, licencia e inicio del conductor |
| `profile/` · `share/` · `help/` · `legal/` | Perfil, viaje compartido público, ayuda y textos legales |
| `admin/` | Panel, aprobaciones, usuarios, viajes, emergencias, moderación y configuración |
| `catalog/` | Catálogo del sistema de diseño (solo en desarrollo, `/catalogo`) |

Cada carpeta que habla con el backend tiene un archivo `*.api.ts`: es el único lugar donde esa pantalla llama a la API.

### `src/app/shared/`

| Carpeta | Contenido |
|---------|-----------|
| `ui/` | Componentes glass: botones, tarjetas, campos, selectores, pestañas, modales, avisos, estrellas, pasos |
| `map/` | Mapa (MapLibre), selector de lugares, resumen de ruta y cliente de rutas |
| `charts/` | Gráficas de columnas y medidores accesibles |
| `forms/` · `icons/` | Validación de formularios e íconos de Lucide |

## Cómo se conecta con el backend

```
Componente → *.api.ts (HttpClient) → interceptores (token, idioma, errores) → /api/v1/... → JSON
RealtimeService (WebSocket /ws) ← eventos publicados por la API en Redis
```

El token de acceso vive solo en memoria; la renovación usa una cookie que JavaScript no puede leer. Las guardas de `app.routes.ts` llevan a cada persona a su inicio según su rol y estado.

## Comandos

```sh
npm install
npm start          # http://localhost:4200 con recarga en caliente (necesita el backend levantado)
npm run build      # compilación de producción en dist/
npm test           # pruebas unitarias con Vitest
npm run lint       # ESLint
npm run e2e        # Playwright contra https://localhost (ver el README raíz para preparar las cuentas)
npm run icons      # regenera shared/icons/lucide.ts tras usar un ícono nuevo
```

Para cambiar un texto, edita `public/i18n/es.json` (y los otros idiomas); las plantillas usan claves como `{{ 'search.submit' | transloco }}`.
