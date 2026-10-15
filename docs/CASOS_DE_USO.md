# Casos de uso de prueba

Veinte casos que recorren la aplicación de punta a punta, con datos concretos y los resultados exactos que debe dar. Sirven como guion de pruebas manuales antes de presentar o desplegar, y cada uno indica qué prueba automatizada cubre una parte.

## Cómo usar este documento

- Los valores entre paréntesis son los de fábrica (Configuración > Parámetros). Si se cambian, los resultados cambian con ellos.
- Los correos salen por Gmail (ver [DESPLIEGUE.md, sección 5](DESPLIEGUE.md#5-correo-real)): los códigos llegan al buzón real de quien tiene uno. Si no aparecen en la bandeja de entrada, revisa spam.
- Las horas son de Pamplona. Hoy es jueves 8 de octubre de 2026; las fechas usadas son de la semana siguiente (lunes 12 a domingo 18) y la otra (lunes 19 a domingo 25).
- Pico y placa de ejemplo del seed (carros y motos), por último dígito de la placa: lunes 0 y 1, martes 2 y 3, miércoles 4 y 5, jueves 6 y 7, viernes 8 y 9.
- Para adelantar el reloj en los casos que esperan minutos u horas, se puede publicar el viaje con la salida cerca o editar `departs_at` en la base de desarrollo.

## Personas y datos de prueba

Hay tres buzones institucionales reales y el Gmail del superadmin. Las otras cinco personas son ficticias: su correo no existe, así que nunca reciben un código; para ellas se usa `verify-email` (ver la preparación). Ningún paso de los casos le pide un código a una persona ficticia.

| Persona | Rol | Correo | Buzón | Datos |
|---------|-----|--------|-------|-------|
| Linda Rodríguez | Conductora | `linda.rodrigueztol@unipamplona.edu.co` | Real | Mujer. Renault 9 rojo, modelo 1987, placa `ABC123` (termina en 3: pico y placa los martes), 4 puestos para pasajeros. Licencia aprobada |
| Jhonatan Vera | Pasajero | `jhonatan.veraric@unipamplona.edu.co` | Real | Hombre. Cuenta activa |
| Daniel Pinzón | Pasajero nuevo | `daniel.pinzonqui@unipamplona.edu.co` | Real | Hombre. Se registra desde cero en el caso 1 |
| Laura Gómez | Pasajera | `laura.gomez@unipamplona.edu.co` | Ficticio | Mujer, Ingeniería de Sistemas |
| Valentina Ruiz | Pasajera | `valentina.ruiz@unipamplona.edu.co` | Ficticio | Mujer |
| Lucía Herrera | Pasajera | `lucia.herrera@unipamplona.edu.co` | Ficticio | Mujer |
| Andrés Rojas | Conductor | `andres.rojas@unipamplona.edu.co` | Ficticio | Hombre. Renault Logan gris placa `RJS583` (termina en 3: pico y placa los martes), 4 puestos para pasajeros |
| Sofía Martínez | Administradora | `sofia.martinez@unipamplona.edu.co` | Ficticio | La crea el superadmin |
| Superadmin | Superadmin | `danipinqui1@gmail.com` | Real | Contraseña en `SUPERADMIN_PASSWORD` del `.env` |

Lugares del seed: Barrio El Carmen, Barrio Cariongo, Barrio Chapinero, Parque Principal Agueda Gallardo, Terminal de Transportes, Sede Casona y Ciudad Universitaria (campus principal).

## Preparación de las cuentas

En PowerShell, desde la carpeta del proyecto (con `make` en Git Bash los comandos son `make verify-email EMAIL=...` y `make forget-unverified EMAIL=...`). Los dos comandos solo existen en desarrollo.

1. **Superadmin.** Entra en https://localhost/ingresar con `danipinqui1@gmail.com`; el código llega a ese Gmail.
2. **Sofía.** El superadmin la crea en Configuración > Administradores con `sofia.martinez@unipamplona.edu.co` y una contraseña inicial. Como su buzón no existe, se le quita el código del primer ingreso:
   ```powershell
   .\make.ps1 verify-email sofia.martinez@unipamplona.edu.co
   ```
3. **Laura, Valentina, Lucía y Andrés.** Cada uno se registra en `/registro` como cualquier estudiante (Andrés con el rol Conductor), con sexo y documento de identidad correctos. En `/verificar` el código nunca llega; en su lugar:
   ```powershell
   .\make.ps1 verify-email laura.gomez@unipamplona.edu.co
   ```
   La cuenta queda "En revisión", igual que si hubiera escrito el código. Al entrar con su correo y contraseña ve `/cuenta/estado`, y Sofía aprueba su documento de identidad en Aprobaciones. A Andrés no se le registra licencia ni vehículo todavía: eso es el caso 2.
4. **Linda y Jhonatan** ya están activos. Linda tiene la licencia aprobada y el Renault 9 `ABC123`.
5. **Daniel** tiene un registro anterior que nunca se verificó. Antes del caso 1 se borra para registrarse desde cero (solo borra cuentas sin verificar):
   ```powershell
   .\make.ps1 forget-unverified daniel.pinzonqui@unipamplona.edu.co
   ```

## Índice

| # | Caso | Roles |
|---|------|-------|
| 1 | Registro de un pasajero hasta su primer viaje posible | Pasajero (Daniel), administradora |
| 2 | Un conductor nuevo queda listo para publicar | Conductor, administradora |
| 3 | Publicar un viaje con parada, pico y placa y cruce de horarios | Conductor |
| 4 | Búsqueda geográfica: radio, dirección, horario y preferencias | Pasajeros, conductores |
| 5 | Tres personas compiten por los dos últimos puestos | Pasajeros, conductor |
| 6 | Lista de espera con oferta que vence y oferta aceptada | Pasajeros, conductor |
| 7 | Cancelación libre, cancelación tardía y su decisión | Pasajeros, conductor |
| 8 | El conductor no llega: cancelación automática por retraso | Conductor, pasajeros |
| 9 | Editar un viaje con reservas: avisos, límites y corte de edición | Conductor, pasajeros |
| 10 | Serie semanal con pico y placa y suscripción por 15 días | Conductora, pasajera |
| 11 | Editar y cancelar una serie con suscriptores | Conductora, pasajera |
| 12 | El viaje en vivo: iniciar, abordar, ausencia, finalizar y tickets | Conductor, pasajeros |
| 13 | Ausencias repetidas suspenden las reservas | Pasajero, conductor, administradora |
| 14 | Compartir el viaje y atender una emergencia | Pasajera, administradora |
| 15 | Chat del viaje de principio a fin | Conductor, pasajeros |
| 16 | Calificaciones anónimas, reputación y moderación | Pasajeros, conductor, administradora |
| 17 | Viaje solo para mujeres | Conductora, conductor, pasajeros, administradora |
| 18 | El superadmin cambia una regla de pico y placa | Superadmin, conductores, pasajera |
| 19 | Nuevo semestre y nueva versión de los términos | Superadmin, pasajeros |
| 20 | Seguridad de la cuenta: bloqueo, recuperación, sanción y eliminación | Pasajero (Jhonatan), administradora |

El caso 20 elimina la cuenta de Jhonatan: conviene dejarlo para el final.

---

## Caso 1. Registro de un pasajero hasta su primer viaje posible

**Objetivo:** el registro en cuatro pasos, la verificación del correo con sus límites y la aprobación del documento de identidad con corrección del sexo.

**Precondiciones:** Daniel no tiene cuenta (preparación, paso 5). Hay un semestre vigente (2026-2).

**Pasos y resultados esperados**

1. Abre https://localhost en una ventana privada: ve la bienvenida de 3 pasos (propuesta, cómo funciona, seguridad) y elige "Crear cuenta".
2. Paso 1, Tus datos: escribe `daniel.pinzonqui@gmail.com`. Al continuar el campo lo rechaza (debe terminar en `.edu.co`; si llegara al servidor, `EMAIL_NOT_INSTITUTIONAL`: "Usa tu correo institucional"). Corrige a `daniel.pinzonqui@unipamplona.edu.co`. Con una contraseña de 8 caracteres ve "Mínimo 10 caracteres". Por error elige sexo "Mujer".
3. Paso 2, Tu rol: elige Pasajero.
4. Paso 3, Tu documento: sube una foto JPG de 7 MB de su documento de identidad: "El archivo pesa más de 5 MB. Usa uno más liviano." (`FILE_TOO_LARGE`). Sube una foto de 2 MB.
5. Paso 4, Confirmación: sin marcar las dos casillas no puede crear la cuenta. Las marca y la crea.
6. Llega a `/verificar` con el correo enmascarado (`da**************@unipamplona.edu.co`). En su buzón institucional llega "Verifica tu correo" con un código de 6 dígitos. Escribe 5 códigos equivocados: al quinto el código deja de servir y cualquier intento responde "El código no es correcto o ya venció" (`CODE_INVALID`), aunque luego escriba el correcto que le llegó.
7. Pide un código nuevo: el botón está deshabilitado hasta pasar 60 s. Llega un segundo correo con otro código; el primero ya no sirve. Con el nuevo verifica.
8. Queda en `/cuenta/estado`: "Tu cuenta está en revisión". No puede entrar a Buscar.
9. Sofía (administradora) abre Aprobaciones > Documentos de identidad: ve el nombre, el programa y "Declarado al registrarse: Mujer", pero no el correo. Corrige el sexo a Hombre y aprueba.
10. Daniel recibe el aviso "Tu documento fue aprobado" y, al recargar, entra a `/buscar`.

**Verificación adicional:** en Configuración > Auditoría aparece la aprobación con el sexo antes (`female`) y después (`male`). La foto del documento ya no tiene metadatos EXIF (ubicación GPS). Al cerrar sesión y volver a entrar, Daniel no recibe código: la verificación del correo contó como segundo factor.

**Prueba automatizada relacionada:** `frontend/e2e/account.spec.ts` (registro, código y aprobación), `backend/tests/test_auth.py`, `backend/tests/test_approvals.py`.

---

## Caso 2. Un conductor nuevo queda listo para publicar

**Objetivo:** requisitos para publicar: licencia aprobada y vigente, y un vehículo activo con placa y capacidad válidas.

**Precondiciones:** Andrés se registró como Conductor y su documento de identidad está aprobado (preparación, paso 3).

**Pasos y resultados esperados**

1. Entra a `/inicio`: "Completa estos pasos para publicar", con Licencia "Súbela con su fecha de vencimiento" y Vehículo sin registrar. El botón Publicar no está; al abrir `/publicar` a mano vuelve a `/inicio`.
2. Sube la licencia con vencimiento 1 de octubre de 2026 (ya pasó): `LICENSE_EXPIRED`.
3. La sube con vencimiento 30 de junio de 2028: queda "Un administrador la está revisando".
4. Registra una moto con 3 puestos: el formulario lo impide (una moto tiene exactamente 2). Registra el carro con la placa escrita ` rjs-583 `: se guarda como `RJS583`.
5. Intenta registrar otro carro con `ABC123`, la placa de Linda: `VEHICLE_PLATE_TAKEN`. La respuesta no dice de quién es.
6. Sofía aprueba la licencia en Aprobaciones > Licencias.
7. Andrés recarga `/inicio`: "Todo listo para publicar" y aparece el botón Publicar.

**Verificación adicional:** si Andrés desactiva su único carro, el inicio vuelve a mostrar el requisito pendiente y Publicar desaparece.

**Prueba automatizada relacionada:** `backend/tests/test_vehicles.py`, `backend/tests/test_approvals.py`; el recorrido `frontend/e2e/journey.spec.ts` prepara un conductor así desde cero.

---

## Caso 3. Publicar un viaje con parada, pico y placa y cruce de horarios

**Objetivo:** el asistente de 7 pasos, el cálculo de ruta y hora de llegada, pico y placa por fecha, antelación mínima y cruce de viajes del mismo conductor.

**Precondiciones:** Andrés puede publicar (caso 2). Su carro `RJS583` termina en 3: tiene pico y placa los martes.

**Pasos y resultados esperados**

1. Publicar > Tipo: viaje puntual. Ruta: origen Barrio El Carmen, parada Parque Principal, destino Ciudad Universitaria. El mapa dibuja la ruta con distancia y duración estimada.
2. Fecha: martes 13 de octubre a las 6:30. El calendario marca ese martes como pico y placa y no deja continuar; si se envía igual, la API responde `PICO_PLACA_RESTRICTED`.
3. Cambia a jueves 15 de octubre a las 6:30. Vehículo: `RJS583`, 3 puestos. Aporte: 2.000. Reglas: sin mascotas, sin humo. Resumen y Publicar.
4. En Mis viajes > Próximos aparece "Jue 15 oct · 6:30", con las horas estimadas de cada parada.
5. Publica otro viaje el mismo jueves a las 6:45 (se cruza con el anterior): `TRIP_OVERLAP`, con la fecha en conflicto.
6. Intenta publicar uno para dentro de 10 minutos: `DEPARTURE_TOO_SOON` (mínimo 15). Para dentro de 70 días: `DEPARTURE_TOO_FAR` (máximo 60).
7. Agrega 6 paradas intermedias: `TOO_MANY_STOPS` (máximo 5).
8. Duplica el viaje del jueves para el viernes 16 a las 6:30: se publica la copia con la misma ruta, puestos, aporte y reglas.

**Verificación adicional:** con el superadmin define `max_price_per_seat` = 3.000 y publica con aporte 3.500: `PRICE_ABOVE_MAX`. Después vuelve a dejarlo vacío.

**Prueba automatizada relacionada:** `backend/tests/test_trips.py`, `backend/tests/test_pico_placa.py`, `backend/tests/test_routing.py`.

---

## Caso 4. Búsqueda geográfica: radio, dirección, horario y preferencias

**Objetivo:** la búsqueda solo devuelve viajes cuya ruta pasa cerca de los dos puntos, en el sentido correcto y dentro de la ventana de horario, y respeta las preferencias.

**Precondiciones:**
- Viaje A de Andrés: jueves 15 a las 6:30, Barrio El Carmen → Ciudad Universitaria, sin mascotas (caso 3).
- Viaje B de Linda: jueves 15 a las 7:10, Ciudad Universitaria → Barrio El Carmen (sentido contrario), en el Renault 9 `ABC123` (los jueves no tiene pico y placa).

**Pasos y resultados esperados**

1. Laura busca jueves 15, 6:45, de Barrio El Carmen a Ciudad Universitaria, 1 puesto. Aparece solo el viaje A, con "A N m de tu punto", la hora de recogida, el aporte y la calificación del conductor.
2. El viaje B no aparece: pasa por los dos puntos, pero recoge en el campus y deja en El Carmen (la recogida debe ir antes que la bajada en la ruta). Si Laura invierte origen y destino a las 7:10, aparece el B y no el A.
3. Cambia la hora a 8:00 con la ruta original: el viaje A ya no aparece (sale 90 minutos antes; la tolerancia es de 60).
4. Vuelve a 6:45 y marca "Viajo con mascota": el viaje A desaparece porque prohíbe mascotas.
5. Elige como recogida un pin en el mapa a unos 2 km de la ruta: no hay resultados ("No encontramos viajes" con sugerencias). El radio es de 500 m.
6. Busca el miércoles 30 de septiembre: `SEARCH_IN_PAST`.

**Verificación adicional:** con dos viajes del mismo horario, primero sale el de recogida más cercana; con la misma distancia, el de menor diferencia horaria; luego el de mejor calificación.

**Prueba automatizada relacionada:** `backend/tests/test_search.py`.

---

## Caso 5. Tres personas compiten por los dos últimos puestos

**Objetivo:** una solicitud no aparta cupo; al aceptar, el viaje se bloquea y nunca se acepta más gente que puestos.

**Precondiciones:** viaje A con 3 puestos y Valentina ya aceptada (quedan 2).

**Pasos y resultados esperados**

1. Laura y Jhonatan piden 1 puesto cada uno y Lucía pide 2. Las tres solicitudes quedan "Solicitada" y la búsqueda sigue mostrando 2 puestos libres.
2. Andrés abre Solicitudes y ve las 3, con la calificación de cada pasajero y dónde lo recoge, sin correos ni teléfonos.
3. Acepta a Lucía (2 puestos): quedan 0 libres.
4. Intenta aceptar a Laura: `TRIP_FULL`. Laura ve el viaje lleno con la opción de unirse a la lista de espera.
5. Laura intenta pedir el viaje B de Linda, que se cruza en horario con su solicitud del viaje A: `BOOKING_OVERLAP`.

**Verificación adicional:** una prueba de backend acepta 6 solicitudes en paralelo sobre 2 puestos y solo 2 quedan aceptadas. Si Andrés no responde en 24 horas (o antes de la salida), la solicitud vence con aviso.

**Prueba automatizada relacionada:** `backend/tests/test_booking_concurrency.py`, `backend/tests/test_bookings.py`.

---

## Caso 6. Lista de espera con oferta que vence y oferta aceptada

**Objetivo:** el cupo liberado se ofrece en orden de llegada, la oferta dura 15 minutos y confirmar crea una solicitud normal.

**Precondiciones:** viaje A lleno (caso 5).

**Pasos y resultados esperados**

1. Laura se anota en la lista de espera (posición 1) y después Jhonatan (posición 2). Si el viaje tuviera cupo, anotarse respondería `WAITLIST_NOT_NEEDED`.
2. Valentina cancela su reserva con más de 2 horas de antelación: se libera 1 puesto.
3. En menos de un minuto Laura recibe "Se liberó un cupo" con 15 minutos para responder. Jhonatan no recibe oferta todavía.
4. Laura no responde. A los 15 minutos su oferta vence y pasa a Jhonatan.
5. Jhonatan confirma: se crea una solicitud y Andrés la ve en su bandeja.
6. Andrés la acepta: Jhonatan queda aceptado y la lista de espera de Laura sigue abierta por si se libera otro cupo.

**Verificación adicional:** las ofertas vigentes nunca suman más que el cupo libre. Si el viaje se cancela, la lista de espera vence.

**Prueba automatizada relacionada:** `backend/tests/test_bookings.py` (`test_waitlist_offers_freed_seats_in_order`).

---

## Caso 7. Cancelación libre, cancelación tardía y su decisión

**Objetivo:** cancelar con más de 2 horas es directo; con menos, exige motivo y la decide el conductor.

**Precondiciones:** Laura y Jhonatan aceptados en el viaje A, que sale el jueves 15 a las 6:30.

**Pasos y resultados esperados**

1. Miércoles 14 a las 20:00, Laura cancela: queda "Cancelada por ti" de inmediato y se libera el puesto.
2. Jueves 15 a las 5:00 (faltan 90 minutos), Jhonatan cancela sin motivo: `CANCEL_REASON_REQUIRED`. Con el motivo "Me enfermé", la reserva pasa a "Cancelación pendiente" y conserva el puesto.
3. Andrés ve la solicitud en Cancelaciones por decidir, con la nota "Faltan menos de 2 horas: si aceptas, el cupo se libera".
   - Si acepta: Jhonatan queda cancelado y el cupo pasa a la lista de espera.
   - Si rechaza: Jhonatan vuelve a "Aceptada".
   - Si no responde y el viaje sale: la solicitud se rechaza sola.
4. Si Andrés marca a Jhonatan "A bordo" con la cancelación pendiente, la solicitud se rechaza; si lo marca "No se presentó", cuenta como ausencia.

**Verificación adicional:** pedir una segunda cancelación con una pendiente responde `CANCELLATION_PENDING`.

**Prueba automatizada relacionada:** `backend/tests/test_bookings.py`, `backend/tests/test_trip_lifecycle.py`.

---

## Caso 8. El conductor no llega: cancelación automática por retraso

**Objetivo:** si el conductor no inicia el viaje, las reservas se cancelan solas sin penalizar a nadie, y el viaje pasa a no realizado.

**Precondiciones:** viaje A del jueves 15 a las 6:30 con Laura aceptada y Jhonatan con una solicitud sin responder.

**Pasos y resultados esperados**

1. A las 6:35 Laura ve el viaje como "Programado" y aún puede esperar.
2. A las 6:45 (15 minutos tarde) y sin haber iniciado, las dos reservas pasan a "Cancelada por retraso" (`auto_cancelled_late`) y los dos reciben aviso. No cuenta como cancelación del pasajero.
3. A las 9:30 (3 horas después de la salida) el viaje pasa a "No realizado". Su chat se cierra más tarde, cuando pasan 3 horas desde la llegada estimada.
4. Si Andrés intenta iniciarlo después de las 9:30: `TRIP_START_TOO_LATE`.

**Verificación adicional:** la ausencia del conductor no le genera una suspensión al pasajero.

**Prueba automatizada relacionada:** `backend/tests/test_bookings.py`, `backend/tests/test_trip_lifecycle.py`.

---

## Caso 9. Editar un viaje con reservas: avisos, límites y corte de edición

**Objetivo:** las ediciones que afectan a los pasajeros se avisan y les permiten cancelar sin penalización; algunas están prohibidas.

**Precondiciones:** viaje A (3 puestos, jueves 15 a las 6:30) con Laura y Jhonatan aceptados.

**Pasos y resultados esperados**

1. El miércoles 14 Andrés cambia la salida a las 6:45: los dos reciben "El conductor cambió el viaje", su punto y hora de recogida se recalculan, y pueden cancelar sin penalización aunque falten menos de 2 horas.
2. Intenta bajar los puestos a 1: `SEATS_BELOW_BOOKED` (hay 2 aceptados).
3. Intenta activar "Solo mujeres": `WOMEN_ONLY_FEMALE_DRIVERS`, porque solo una conductora puede. Si fuera Linda con Jhonatan aceptado en su viaje, la respuesta sería `WOMEN_ONLY_CONFLICT`.
4. El jueves 15 a las 6:20 (25 minutos antes) intenta cambiar el aporte: `TRIP_NOT_EDITABLE` (corte de 30 minutos).
5. Cancela el viaje con el motivo "Se dañó el carro": las reservas pasan a "Cancelada por el conductor", los pasajeros reciben el motivo, el chat se cierra y cuenta en sus estadísticas como cancelación.

**Verificación adicional:** un vehículo con viajes programados no se puede desactivar ni borrar (`VEHICLE_HAS_TRIPS`).

**Prueba automatizada relacionada:** `backend/tests/test_trips.py`, `backend/tests/test_bookings.py`.

---

## Caso 10. Serie semanal con pico y placa y suscripción por 15 días

**Objetivo:** una serie genera viajes repetidos dentro del semestre, salta los días de pico y placa, y una suscripción reserva varias fechas con una sola aprobación.

**Precondiciones:** Linda puede publicar. Su Renault 9 `ABC123` termina en 3: tiene pico y placa los martes.

**Pasos y resultados esperados**

1. Linda publica una serie: lunes, martes y miércoles a las 6:30, Barrio Cariongo → Sede Casona, desde el lunes 19 de octubre, ventana de 28 días, 4 puestos, aporte 1.500.
2. En el detalle de la serie, los martes aparecen como "Pico y placa" (cancelados) y los lunes y miércoles como "Programado".
3. Laura abre la serie y elige "15 días" desde el lunes 19: el calendario marca los martes tachados y las fechas reservables.
4. Linda aprueba la suscripción una sola vez. Laura recibe un aviso con cuántos viajes se reservaron y las fechas omitidas (los martes).
5. Mis viajes > Series de Laura muestra la suscripción "Activa"; Próximos muestra cada fecha como reserva aceptada.
6. Se crea un chat directo Linda-Laura para toda la serie, además del grupal de cada viaje.

**Verificación adicional:** una serie que empieza fuera de un semestre responde `SERIES_OUTSIDE_SEMESTER`; una solo de martes (todas las fechas en pico y placa), `SERIES_EMPTY`. Si Linda no responde en 24 horas, la suscripción vence.

**Prueba automatizada relacionada:** `backend/tests/test_trips.py` (series), `backend/tests/test_subscriptions.py`.

---

## Caso 11. Editar y cancelar una serie con suscriptores

**Objetivo:** editar una serie con reservas exige confirmación; las fechas que desaparecen cancelan sus reservas con aviso.

**Precondiciones:** la serie y la suscripción del caso 10.

**Pasos y resultados esperados**

1. Linda quita el miércoles de la serie: el asistente avisa que hay reservas afectadas y pide confirmar (la API responde `SERIES_HAS_BOOKINGS` hasta recibir `confirm: true`).
2. Confirma: los miércoles futuros desaparecen y las reservas de Laura en esos días quedan canceladas por la conductora, con aviso. Los lunes siguen reservados.
3. Cambia la hora a 6:15: Laura recibe el aviso de cambio en sus viajes de los lunes.
4. Laura cancela la suscripción: sus reservas futuras se cancelan con las reglas de cancelación de cada fecha.
5. Linda cancela la serie con el motivo "Fin de mis clases presenciales": todas las ocurrencias futuras se cancelan y los chats se cierran.

**Verificación adicional:** las fechas pasadas o en curso nunca cambian al editar la serie.

**Prueba automatizada relacionada:** `backend/tests/test_subscriptions.py`, `backend/tests/test_trips.py`.

---

## Caso 12. El viaje en vivo: iniciar, abordar, ausencia, finalizar y tickets

**Objetivo:** el ciclo completo del viaje con ubicación en vivo, marcaje de cada pasajero y emisión de tickets.

**Precondiciones:** viaje A del jueves 15 a las 6:30, 2.000 por puesto, con Laura (1 puesto) y Jhonatan (1 puesto) aceptados.

**Pasos y resultados esperados**

1. A las 5:50 Andrés intenta iniciar: `TRIP_START_TOO_EARLY` (se puede desde 30 minutos antes).
2. A las 6:00 inicia: "Viaje iniciado. Tus pasajeros ya ven tu ubicación". El navegador pide permiso de ubicación y mantiene la pantalla encendida.
3. Laura y Jhonatan ven el carro moverse en el mapa (una posición cada 5 segundos) y la hora estimada de llegada.
4. Andrés marca a Laura "Abordó". Intenta finalizar: `PASSENGERS_UNMARKED`, con el nombre de Jhonatan.
5. A las 6:35 intenta marcar a Jhonatan "No se presentó": `NO_SHOW_TOO_EARLY` (hay que esperar 10 minutos desde la salida). A las 6:41 lo marca: Jhonatan recibe el aviso y sale del chat grupal.
6. Finaliza: "Viaje finalizado. Se emitieron los tickets". Laura recibe un ticket `CP-XXXX-XXXX` por 2.000 y el aviso para calificar. Jhonatan no recibe ticket.
7. Andrés marca "Aporte recibido" en el ticket de Laura (lo puede desmarcar); Laura ve "El conductor confirmó tu aporte".
8. El chat del viaje queda cerrado y la ubicación en vivo se borra.

**Verificación adicional:** con el carro en pico y placa ese día, iniciar responde `PICO_PLACA_RESTRICTED`.

**Prueba automatizada relacionada:** `frontend/e2e/journey.spec.ts` (iniciar, abordar, finalizar, ticket y calificación), `backend/tests/test_trip_lifecycle.py`.

---

## Caso 13. Ausencias repetidas suspenden las reservas

**Objetivo:** 3 ausencias en 30 días suspenden las reservas 7 días; la administración puede levantar la suspensión.

**Precondiciones:** Jhonatan ya tiene 2 ausencias en las últimas 3 semanas (la del caso 12 y otra en un viaje de Linda).

**Pasos y resultados esperados**

1. En otro viaje Jhonatan vuelve a no presentarse y el conductor lo marca: es su tercera ausencia en 30 días.
2. Jhonatan recibe "Tus reservas quedaron suspendidas por 7 días por ausencias repetidas". Las reservas que ya tenía se mantienen.
3. Intenta reservar otro viaje: `BOOKING_SUSPENDED`.
4. Sofía abre Usuarios > Jhonatan: ve la suspensión automática en el historial de sanciones y usa "Levantar suspensión de reservas" con un motivo.
5. Jhonatan recibe "Ya puedes volver a reservar viajes" y puede reservar de nuevo.

**Verificación adicional:** la auditoría registra `suspension.end` con Sofía como autora.

**Prueba automatizada relacionada:** `backend/tests/test_trip_lifecycle.py`, `backend/tests/test_admin_console.py`.

---

## Caso 14. Compartir el viaje y atender una emergencia

**Objetivo:** el enlace público no expone datos personales y vence; la emergencia llega en vivo a la administración y su atención queda auditada.

**Precondiciones:** viaje en curso con Laura a bordo. Laura tiene a "Mamá" como contacto de confianza.

**Pasos y resultados esperados**

1. Laura toca "Compartir viaje" y envía el enlace a Mamá. Ese enlace se muestra una sola vez.
2. Desde un navegador sin sesión, el enlace `/compartido/...` muestra la ruta, el vehículo con su placa, la hora estimada y la ubicación, sin nombres ni teléfonos. Se actualiza cada 15 segundos.
3. Laura toca "Emergencia": primero ve los botones "Llamar al 123" y "Llamar a Mamá". Toca "Avisar a la universidad" con la nota "El conductor tomó otra vía".
4. Sofía, en Emergencias, la ve aparecer sin recargar, marcada como abierta, con el nombre de Laura, el viaje y "Ver ubicación". La campana de todos los administradores también avisa.
5. Sofía la marca como atendida con la resolución "Llamamos a la pasajera; desvío por obras, todo en orden". Desaparece de las abiertas en la pantalla de los demás administradores (el superadmin lo comprueba con su sesión abierta en otro navegador).
6. Media hora después de la llegada estimada el enlace compartido deja de funcionar.

**Verificación adicional:** Daniel, que no está en el viaje, no puede crear enlaces ni emergencias en él (403 o 404). Laura no puede guardar un sexto contacto de confianza (`TRUSTED_CONTACTS_LIMIT`).

**Prueba automatizada relacionada:** `backend/tests/test_safety.py`, `backend/tests/test_live_router.py` (canal de emergencias), `backend/tests/test_ownership.py`.

---

## Caso 15. Chat del viaje de principio a fin

**Objetivo:** chat grupal en tiempo real, contadores, salida al cancelar, cierre al terminar y retención.

**Precondiciones:** viaje A con Laura y Jhonatan aceptados.

**Pasos y resultados esperados**

1. Al aceptar las reservas se creó el chat grupal "Viaje 6:30" con los tres. Andrés escribe "Salgo en 5 min".
2. Laura, con la app abierta en otra pantalla, ve subir el contador de Mensajes sin recargar. En el chat aparece "Andrés está escribiendo".
3. Con la red desconectada, la app muestra "Reconectando..."; al volver recupera los mensajes que llegaron mientras tanto.
4. Jhonatan cancela su reserva: sale del chat grupal y ya no recibe los mensajes nuevos.
5. Al finalizar el viaje el chat queda de solo lectura: enviar responde `CONVERSATION_CLOSED`.
6. A los 30 días de cerrado, el chat y sus mensajes se borran.

**Verificación adicional:** un mensaje de 1.001 caracteres no se envía. Daniel, ajeno al viaje, no puede leer el chat aunque conozca su id.

**Prueba automatizada relacionada:** `backend/tests/test_chat.py`, `backend/tests/test_ownership.py`.

---

## Caso 16. Calificaciones anónimas, reputación y moderación

**Objetivo:** solo califica quien viajó, por criterios, dentro de 7 días, sin revelar el autor; la moderación oculta comentarios sin cambiar las estrellas.

**Precondiciones:** viaje del caso 12 finalizado (Laura abordó, Jhonatan no se presentó).

**Pasos y resultados esperados**

1. Laura abre Calificar: califica a Andrés en puntualidad, conducción segura, amabilidad y limpieza, con el comentario "Muy puntual". Sin todos los criterios no puede enviar.
2. Intenta calificar otra vez el mismo viaje: `RATING_EXISTS`.
3. Jhonatan (no abordó) no puede calificar ese viaje: `RATING_TARGET_INVALID` o `RATING_NOT_OPEN`.
4. Andrés califica a Laura en puntualidad, amabilidad y cumplimiento de las reglas.
5. En el perfil de Andrés aparecen el promedio y el comentario, sin el nombre de Laura. En la búsqueda su calificación sale en la tarjeta del viaje.
6. Sofía oculta el comentario en Moderación: el perfil deja de mostrar el texto, pero el promedio no cambia. Lo puede volver a mostrar.
7. Al octavo día ya no se puede calificar (`RATING_WINDOW_CLOSED`).

**Verificación adicional:** el día antes del cierre, quien no calificó recibe un último recordatorio.

**Prueba automatizada relacionada:** `backend/tests/test_ratings.py`, `backend/tests/test_admin_console.py`, `frontend/e2e/journey.spec.ts`.

---

## Caso 17. Viaje solo para mujeres

**Objetivo:** solo una conductora lo publica, solo pasajeras lo ven y lo reservan, y el sexo verificado por la administración manda.

**Pasos y resultados esperados**

1. Andrés (hombre) intenta publicar con la regla "Solo mujeres": `WOMEN_ONLY_FEMALE_DRIVERS`.
2. Linda publica un viaje solo para mujeres el viernes 16 a las 7:00 en el Renault 9 (los viernes restringen 8 y 9; su placa termina en 3).
3. Jhonatan busca esa ruta y ese horario: el viaje no aparece. Si abre el enlace del viaje e intenta reservar: `WOMEN_ONLY_TRIP`.
4. Laura lo ve, marca la preferencia "Solo mujeres" en la búsqueda y lo reserva.
5. Daniel declaró "Mujer" por error al registrarse (caso 1) y Sofía lo corrigió a Hombre al aprobar: el viaje no le aparece y reservarlo responde `WOMEN_ONLY_TRIP`. El sexo que manda es el verificado por la administración, no el declarado.

**Verificación adicional:** activar "Solo mujeres" en un viaje de Linda que ya tiene a Jhonatan aceptado responde `WOMEN_ONLY_CONFLICT`.

**Prueba automatizada relacionada:** `backend/tests/test_trips.py`, `backend/tests/test_search.py`, `backend/tests/test_bookings.py`.

---

## Caso 18. El superadmin cambia una regla de pico y placa

**Objetivo:** cambiar una regla cancela al instante los viajes futuros afectados, con aviso, y deshacerla los restaura.

**Precondiciones:** Andrés (`RJS583`, termina en 3) tiene un viaje el jueves 22 de octubre con Laura aceptada. Hoy los jueves restringen 6 y 7.

**Pasos y resultados esperados**

1. El superadmin edita la regla de carros de los jueves en Configuración > Pico y placa y agrega el dígito 3.
2. El viaje del jueves 22 pasa a "Pico y placa" sin intervención de nadie. Laura recibe un aviso de cancelación (`auto_cancelled_pico_placa`) y Andrés el de "viaje cancelado por pico y placa". Si Linda tiene viajes futuros un jueves, también se cancelan: su `ABC123` también termina en 3.
3. El viaje no aparece en la búsqueda y no se puede reservar (`TRIP_NOT_BOOKABLE`).
4. El superadmin quita el dígito 3: el viaje vuelve a "Programado" y Andrés recibe el aviso de que se restauró. La reserva de Laura no vuelve sola: debe pedir cupo otra vez.
5. La auditoría muestra las dos ediciones de la regla con el antes y el después.

**Verificación adicional:** el mismo recálculo corre cada día a las 5:15 a. m., aunque nadie toque las reglas.

**Prueba automatizada relacionada:** `backend/tests/test_pico_placa.py`.

---

## Caso 19. Nuevo semestre y nueva versión de los términos

**Objetivo:** la revalidación semestral del documento de identidad y la aceptación obligatoria de términos nuevos.

**Pasos y resultados esperados**

1. El superadmin crea el semestre 2027-1 (1 de febrero a 30 de junio). Si se cruza con otro semestre: `SEMESTER_OVERLAP`.
2. Al empezar 2027-1, el documento de identidad de Laura (aprobado en 2026-2) vence y recibe el aviso de revalidación. Tiene hasta el plazo del semestre (30 días desde el inicio, por defecto) para subir el nuevo.
3. Jhonatan no lo sube a tiempo: al pasar el plazo su cuenta vuelve a "En revisión" y solo ve su estado hasta que se apruebe un documento nuevo. Administradores y superadmin no revalidan.
4. El superadmin publica los términos versión 1.1 en español. Publicar otra vez la versión 1.1 en español responde `LEGAL_VERSION_EXISTS`.
5. En su siguiente ingreso, cada persona con la app en español ve la pantalla de términos y no puede seguir sin aceptarlos. Quien la usa en inglés (por ejemplo Daniel, si cambia el idioma antes) sigue con la versión inglesa vigente hasta que se publique la suya.
6. Laura acepta y continúa; la aceptación queda guardada con la versión exacta.

**Verificación adicional:** borrar un semestre con documentos ligados responde `SEMESTER_IN_USE`.

**Prueba automatizada relacionada:** `backend/tests/test_semesters.py`, `backend/tests/test_legal.py`, `backend/tests/test_approvals.py`.

---

## Caso 20. Seguridad de la cuenta: bloqueo, recuperación, sanción y eliminación

**Objetivo:** protección contra intentos de contraseña, recuperación segura, sanciones de la administración y el derecho a eliminar la cuenta (Ley 1581).

**Precondiciones:** Jhonatan tiene sesión abierta en el celular y en el computador, y un viaje reservado para el viernes. Este caso elimina su cuenta: hazlo al final.

**Pasos y resultados esperados**

1. Desde un tercer navegador alguien prueba 5 contraseñas equivocadas para el correo de Jhonatan: al quinto intento la cuenta se bloquea 15 minutos ("Hiciste demasiados intentos. Por seguridad espera 15 minutos", `ACCOUNT_LOCKED`). Probar con un correo inexistente da el mismo mensaje y tarda lo mismo.
2. Jhonatan usa "Olvidaste tu contraseña": recibe "Restablece tu contraseña" en su buzón institucional, escribe el código y crea una contraseña nueva. Sus dos sesiones se cierran al instante y el siguiente ingreso le pide otro código, que llega en un correo "Código para iniciar sesión".
3. Sofía suspende a Jhonatan 3 días con el motivo "Reportes de mal comportamiento": su reserva del viernes se cancela con aviso al conductor y Jhonatan solo ve "Tu cuenta está suspendida". A los 3 días vuelve sola a activa.
4. Sofía intenta suspender a otro administrador: no puede (solo el superadmin gestiona administradores). Nadie puede suspenderse a sí mismo ni actuar sobre el superadmin.
5. Jhonatan, durante un viaje en curso, intenta eliminar su cuenta desde el perfil: `ACCOUNT_DELETE_TRIP_IN_PROGRESS`.
6. Después del viaje la elimina: marca "Entiendo que no se puede deshacer", escribe la contraseña y confirma. Ve "Tu cuenta fue eliminada" y vuelve al ingreso.
7. Con su correo y contraseña ya no puede entrar. En el panel su cuenta no aparece. En el viaje que hizo, su nombre figura como "Cuenta eliminada"; el ticket y la calificación del viaje se conservan.

**Verificación adicional:** el superadmin no ve la opción de eliminar su cuenta (`ACCOUNT_DELETE_NOT_ALLOWED`). Cambiar la cabecera `X-Forwarded-For` en cada intento no evita el bloqueo del paso 1. El correo de Jhonatan queda libre: puede registrarse otra vez desde cero, como Daniel en el caso 1.

**Prueba automatizada relacionada:** `backend/tests/test_auth.py`, `backend/tests/test_admin_console.py`, `backend/tests/test_account_deletion.py`, `backend/tests/test_rate_limits.py`, `frontend/e2e/account.spec.ts`.

---

## Comprobaciones transversales

En cualquiera de los casos anteriores conviene verificar además:

- **Idiomas:** cambiar a English, Português o Français traduce la pantalla al instante, sin recargar, incluidos los mensajes de error. Los correos de código llegan en el idioma de la persona.
- **Tema:** claro, oscuro y "según el sistema" se aplican al instante; "Reducir transparencia" quita el vidrio.
- **Celular:** en un teléfono la barra inferior muestra cinco destinos (el administrador tiene además "Más").
- **Errores de red:** con el servidor detenido, las listas muestran "No pudimos cargar esta información" con Reintentar, nunca una lista vacía.
- **Privacidad:** en ninguna pantalla aparecen el correo, el teléfono ni el documento de otra persona.
- **Auditoría:** toda acción de administración de los casos 1, 13, 14, 16, 18, 19 y 20 aparece en Configuración > Auditoría con su autor.
