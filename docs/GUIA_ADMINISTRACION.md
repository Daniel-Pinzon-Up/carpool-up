# Guía de administración

Para quienes administran Carpool UP desde el panel (`/admin`). Hay dos roles:

- **Administrador**: aprueba documentos, atiende emergencias, monitorea viajes, modera y sanciona pasajeros y conductores.
- **Superadmin**: todo lo anterior, más la configuración completa, los administradores y la auditoría.

Toda acción del panel queda en la **auditoría** con quién la hizo, cuándo y el estado antes y después. Nadie puede actuar sobre su propia cuenta ni sobre la del superadmin, y solo el superadmin gestiona a los administradores.

## 1. Primer ingreso

1. Entra en `/ingresar` con el correo y la contraseña que te dieron.
2. El primer ingreso pide un código de 6 dígitos que llega a tu correo. Vence en 10 minutos.
3. En el computador la navegación está en la barra lateral; en el celular, en la barra inferior (el botón **Más** muestra el resto).

## 2. Panel

Resumen del periodo elegido (7, 30 o 90 días): viajes completados, cancelaciones, ausencias, viajes por día y por hora, rutas más usadas, ocupación y calificaciones. Arriba hay accesos directos a las **aprobaciones pendientes** y a las **emergencias abiertas**.

## 3. Aprobaciones

Cola en orden de llegada, con dos pestañas: **carnets y constancias**, y **licencias**.

1. Abre el documento en el visor seguro (no queda guardado en el navegador).
2. Compara el nombre y el sexo con lo que la persona declaró. Si el sexo no coincide, corrígelo al aprobar: de él depende el acceso a los viajes solo para mujeres.
3. **Aprobar** activa la cuenta (o habilita a conducir, si es una licencia) y avisa a la persona.
4. **Rechazar** pide un motivo que la persona verá. Escribe qué debe corregir.

Cada semestre las personas revalidan su carnet dentro del plazo del semestre (Configuración > Semestres).

## 4. Usuarios

Búsqueda por nombre o correo, con filtros de rol y estado. La ficha muestra documentos, métricas, calificación e historial de sanciones.

| Acción | Efecto |
|--------|--------|
| **Suspender** | Con motivo y duración (1, 3, 7 o 30 días, o hasta reactivar). No puede usar la app; se cancelan sus viajes y reservas futuros con aviso a los afectados. Con fecha de fin, vuelve sola a activa. |
| **Reactivar** | Devuelve la cuenta a activa. |
| **Bloquear** | Definitivo, con motivo. Cierra todas sus sesiones y la retira de sus viajes. |
| **Levantar suspensión de reservas** | Quita antes de tiempo la suspensión automática por ausencias. |
| **Cambiar rol** (superadmin) | Pasajero, conductor o administrador. La persona recibe un aviso. |

Las ausencias (no-show) suspenden las reservas automáticamente: 3 ausencias en 30 días suspenden 7 días (valores configurables).

## 5. Viajes

Monitoreo por estado, día y texto (lugar o conductor). En el detalle se ven las reservas y las emergencias del viaje.

- **Cancelar viaje**: solo viajes programados, con motivo. Se avisa al conductor y a los pasajeros, y cuenta como cancelación del conductor en sus estadísticas.
- **Ver el chat**: solo cuando haga falta para atender un reporte o una emergencia; pide confirmación y la lectura queda en la auditoría. Puedes **ocultar** mensajes; no se borran y se pueden volver a mostrar.

## 6. Emergencias

Llegan en tiempo real, sin recargar, con aviso a todos los administradores. Las abiertas aparecen primero.

1. Abre la ubicación del reporte (enlace al mapa).
2. Si hace falta, llama a la persona o a la línea de emergencias (por defecto 123).
3. **Marcar como atendida** exige escribir qué se hizo: queda en la auditoría.

## 7. Moderación

Comentarios de las calificaciones, en dos pestañas: **visibles** y **ocultos**. Ocultar un comentario no lo borra y no cambia las estrellas; se puede deshacer.

## 8. Configuración (solo superadmin)

| Pestaña | Para qué |
|---------|----------|
| **Parámetros** | Reglas del negocio (tabla de abajo). El servidor valida cada valor antes de guardarlo. |
| **Semestres** | Inicio, fin y plazo de revalidación. Las series y la vigencia de los carnets dependen de ellos. |
| **Lugares** | Sedes, barrios y puntos de referencia del buscador. Desactivar en vez de borrar: los viajes antiguos los siguen usando. Las coordenadas del seed son aproximadas: revísalas. |
| **Pico y placa** | Tipo de vehículo, día, dígitos restringidos y vigencia. Al guardar, los viajes futuros afectados se cancelan solos con aviso; si una regla deja de aplicar, vuelven. Las reglas del seed son de ejemplo: ajústalas al decreto vigente. |
| **Legal** | Publica una versión nueva de los términos o de la política de datos por idioma. Queda vigente de inmediato y todos deben aceptarla en su próximo ingreso. Los textos del seed son un borrador pendiente de revisión jurídica. |
| **Administradores** | Crear cuentas de administrador. La contraseña inicial debe compartirse por un canal seguro. |
| **Auditoría** | Filtra por acción o entidad; cada entrada muestra el antes y el después. |

### Parámetros principales

| Parámetro | Por defecto | Qué controla |
|-----------|-------------|--------------|
| `cancel_free_hours` | 2 | Horas antes de la salida en que el pasajero cancela sin penalización |
| `driver_late_minutes` | 15 | Retraso del conductor tras el que el pasajero cancela sin penalización |
| `no_show_wait_minutes` | 10 | Espera antes de poder marcar una ausencia |
| `no_show_limit` / `no_show_window_days` / `no_show_ban_days` | 3 / 30 / 7 | Ausencias que suspenden las reservas, en cuántos días, y por cuánto |
| `search_radius_meters` | 500 | Distancia máxima de la ruta a los puntos del pasajero |
| `search_time_window_minutes` | 60 | Tolerancia de horario en la búsqueda |
| `cost_per_km_car` / `cost_per_km_motorcycle` | vacío | Si se definen, la app sugiere el aporte según la distancia |
| `max_price_per_seat` | vacío | Tope de aporte por puesto |
| `waitlist_offer_minutes` | 15 | Tiempo para aceptar un cupo de la lista de espera |
| `rating_window_days` | 7 | Días para calificar después del viaje |
| `chat_retention_days` | 30 | Días que se conserva el chat después del viaje |
| `pending_request_hours` | 24 | Horas tras las que vence una solicitud sin respuesta |
| `revalidation_days` | 30 | Días desde el inicio del semestre para revalidar el carnet |
| `password_min_length` | 10 | Longitud mínima de la contraseña |
| `login_max_attempts` / `login_lockout_minutes` | 5 / 15 | Intentos fallidos antes del bloqueo temporal, y su duración |
| `auth_code_minutes` / `auth_code_max_attempts` / `auth_code_resend_seconds` | 10 / 5 / 60 | Vigencia, intentos y espera de los códigos por correo |
| `max_upload_mb` | 5 | Tamaño máximo de documentos e imágenes |
| `max_trip_stops` | 5 | Paradas intermedias por viaje |
| `trip_publish_min_lead_minutes` / `trip_max_days_ahead` | 15 / 60 | Antelación mínima y máxima para publicar |
| `trip_edit_cutoff_minutes` | 30 | Minutos antes de la salida en que un viaje ya no se edita |
| `trip_start_lead_minutes` / `trip_not_held_hours` | 30 / 3 | Desde cuándo se inicia un viaje y cuándo pasa a no realizado |
| `trip_reminder_minutes` | 30 | Aviso antes de la salida |
| `share_link_extra_minutes` | 30 | Minutos que el enlace compartido sigue activo tras el viaje |
| `live_location_ttl_seconds` | 120 | Segundos que se conserva la última ubicación del conductor |
| `trusted_contacts_max` | 5 | Contactos de confianza por persona |
| `emergency_phone` | 123 | Línea de emergencias que muestra la app |
| `service_area` | Pamplona | Caja geográfica donde se aceptan puntos |

## 9. Datos personales (Ley 1581)

- Nadie ve el correo, el teléfono, el carnet ni la licencia de otra persona. La placa solo la ven los pasajeros con reserva aceptada y quien tenga el enlace de un viaje compartido.
- Cada persona puede **eliminar su cuenta** desde su perfil: se anonimizan sus datos, se borran sus documentos y contactos, y se conservan solo los registros operativos de los viajes. Una cuenta eliminada ya no aparece en el panel.

## 10. Mantenimiento

Ver la [guía de despliegue](DESPLIEGUE.md): correo real, respaldos diarios (`make backup-check` para comprobarlos), restauración, actualizaciones y problemas frecuentes.
