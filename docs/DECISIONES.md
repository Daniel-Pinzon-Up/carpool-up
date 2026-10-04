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
