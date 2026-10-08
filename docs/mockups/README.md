# Mockups de Carpool UP

Wireframes de fidelidad media de las pantallas reales de la app: mismos textos, rutas, estados y reglas que el código (`frontend/public/i18n/es.json`). Escala de grises con el azul de Carpool UP como único acento e iconos de Lucide, la misma librería de la app. Pasajero y conductor en móvil; administración en escritorio.

- `png/`: una imagen por pantalla (móvil 960×2000, escritorio 3200×1800), lista para insertar en un PDF o una presentación.
- `Carpool-UP-mockups.pdf`: todas las pantallas, una por página (A4 horizontal).
- `mockups.html`: fuente editable. Cada `<section class="frame">` es una pantalla; los componentes comunes (barra superior, navegación, mapa, menú lateral) se generan con el script del final para que todas sean consistentes.
- `render.mjs`: vuelve a exportar las imágenes y el PDF: `cd frontend && node ../docs/mockups/render.mjs`.

## Pantallas

| # | Pantalla | Ruta |
|---|----------|------|
| 01 | Inicio de sesión | `/ingresar` |
| 02a–02d | Registro en 4 pasos: tus datos, tu rol, tu documento, confirmación | `/registro` |
| 02e | Verificación del correo con código de 6 números | `/verificar` |
| 02f | Cuenta en revisión | `/cuenta/estado` |
| 03 | Pasajero: buscar viaje y resultados | `/buscar` |
| 04a–04b | Pasajero: detalle del viaje y solicitud de cupo | `/viajes/:id` |
| 05a–05b | Pasajero: mis viajes, próximos e historial | `/mis-viajes` |
| 06a–06b | Conductor: panel con requisitos pendientes y listo para publicar | `/inicio` |
| 06c | Conductor: mis viajes publicados | `/mis-viajes` |
| 07a–07h | Conductor: asistente de publicación (tipo, ruta, fecha puntual o serie, vehículo y puestos, aporte, reglas, resumen) | `/publicar` |
| 08 | Conductor: solicitudes de pasajeros | `/solicitudes` |
| 09 | Conductor: viaje en curso | `/viajes/:id` |
| 10a–10c | Pasajero: viaje en curso, emergencia y compartir el viaje | `/viajes/:id` |
| 11a–11b | Mensajes: conversaciones y chat del viaje | `/mensajes` |
| 12 | Notificaciones | `/notificaciones` |
| 13a–13b | Calificar: el pasajero al conductor y el conductor a sus pasajeros | `/calificar/:tripId` |
| 14a–14b | Perfil | `/perfil` |
| 15 | Administrador: panel | `/admin` |
| 16a–16b | Administrador: aprobación de carnets y licencias, y rechazo con motivo | `/admin/aprobaciones` |
| 17a–17c | Administrador: usuarios, detalle con sanciones y suspensión | `/admin/usuarios` |
| 18 | Administrador: emergencias | `/admin/emergencias` |
| 19a–19f | Superadmin: configuración (parámetros, semestres, lugares, pico y placa, legal, administradores) | `/admin/configuracion` |
| 20 | Superadmin: auditoría | `/admin/configuracion` |

## Fidelidad con la app

Los mockups muestran lo que está implementado, también donde difiere de lo que suele esperarse:

- El panel del conductor muestra el estado de la licencia y del vehículo, o los accesos a Publicar, Solicitudes y Estadísticas. Los próximos viajes están en Mis viajes (06c) y las solicitudes en su propia pantalla (08).
- El conductor comparte su ubicación de forma automática al iniciar el viaje; "Compartir viaje" genera el enlace público para terceros.
- El chat se abre desde el detalle del viaje o desde Mensajes, no desde la tarjeta de la reserva.
- La placa solo aparece cuando la reserva está aceptada; ninguna pantalla muestra el correo o el teléfono de otra persona, salvo el panel de administración.
- El valor del viaje es un aporte para compartir gastos, nunca una tarifa.

Personas de los mockups: las de [CASOS_DE_USO.md](../CASOS_DE_USO.md).
