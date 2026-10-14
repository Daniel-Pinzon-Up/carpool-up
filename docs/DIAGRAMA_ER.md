# Diagrama entidad-relación

Modelo de datos de Carpool UP: **18 tablas** en PostgreSQL 16 con PostGIS, definidas con SQLAlchemy y creadas por una única migración de Alembic (`backend/alembic/versions/20261014_0001_esquema_inicial.py`).

## Cómo leerlo

| Símbolo | Significado |
|---------|-------------|
| `PK` | Llave primaria |
| `FK` | Llave foránea |
| `UK` | Valor único |
| `\|\|--o{` | Uno a muchos (cero o más) |
| `\|\|--o\|` | Uno a cero o uno |
| `\|o--o{` | Opcional: la llave foránea puede ser nula |

- Las llaves primarias son UUID, salvo `system_settings` (clave de texto) y `audit_log` (entero autoincremental).
- `geometry` son columnas de PostGIS: la ruta del viaje (`trips.route`) y la ubicación de cada lugar (`places.point`).
- `jsonb` guarda datos que antes eran tablas aparte: las reglas del viaje (`trips.rules`) y los criterios de cada calificación (`ratings.scores`).
- Los tipos `enum` son enums de PostgreSQL (estado del viaje, de la reserva, rol, etc.).

## Diagrama general

`users` es el centro: casi todo pertenece a una persona o lo decide una persona. `trips` es el segundo eje: paradas, reservas, calificaciones, chat y emergencias cuelgan del viaje.

```mermaid
erDiagram
  users {
    uuid id PK
    citext email UK "correo institucional"
    text password_hash
    text full_name
    sex sex
    text program
    user_role role "pasajero, conductor, admin, superadmin"
    user_status status
    text avatar_path
    text payment_note
    boolean two_factor_required
    timestamptz terms_accepted_at "acepto terminos al registrarse"
    timestamptz suspended_until "fin de la suspension de la cuenta"
    text suspension_reason
    timestamptz booking_ban_until "sin reservar por ausencias"
    integer failed_login_attempts
    timestamptz locked_until
    timestamptz last_login_at
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  user_sessions {
    uuid id PK
    uuid user_id FK
    text refresh_token_hash
    text device_label
    text ip
    text user_agent
    timestamptz expires_at
    timestamptz revoked_at
    timestamptz last_seen_at
    timestamptz created_at
    timestamptz updated_at
  }
  auth_codes {
    uuid id PK
    uuid user_id FK
    auth_purpose purpose
    text code_hash
    timestamptz expires_at
    integer attempts
    timestamptz used_at
    timestamptz created_at
    timestamptz updated_at
  }
  notifications {
    uuid id PK
    uuid user_id FK
    text kind
    jsonb payload
    timestamptz read_at
    timestamptz created_at
  }
  trusted_contacts {
    uuid id PK
    uuid user_id FK
    text name
    text phone
    text relationship
    timestamptz created_at
    timestamptz updated_at
  }
  semesters {
    uuid id PK
    text name UK
    date starts_on
    date ends_on
    date revalidation_deadline
    timestamptz created_at
    timestamptz updated_at
  }
  documents {
    uuid id PK
    uuid user_id FK
    doc_kind kind "carne, constancia o licencia"
    text file_path
    text content_type
    review_status status
    uuid semester_id FK
    date expires_on "vencimiento de la licencia"
    uuid reviewed_by FK
    timestamptz reviewed_at
    text rejection_reason
    timestamptz created_at
    timestamptz updated_at
  }
  vehicles {
    uuid id PK
    uuid owner_id FK
    vehicle_type type
    text plate
    text brand
    text model
    text color
    smallint year
    smallint capacity
    boolean luggage_space
    text photo_path
    text photo_content_type
    boolean is_active
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  pico_placa_rules {
    uuid id PK
    vehicle_type vehicle_type
    smallint weekday
    smallint[] restricted_digits
    date valid_from
    date valid_to
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }
  places {
    uuid id PK
    text name
    place_kind kind
    geometry point "ubicacion PostGIS"
    boolean is_active
    uuid created_by FK
    timestamptz created_at
    timestamptz updated_at
  }
  trips {
    uuid id PK
    uuid driver_id FK
    uuid vehicle_id FK
    timestamptz departs_at
    smallint seats_total
    integer price_per_seat
    geometry route "ruta PostGIS"
    integer distance_m
    integer est_duration_s
    trip_status status
    timestamptz started_at
    timestamptz finished_at
    text cancel_reason
    timestamptz cancelled_at
    timestamptz reminded_at
    timestamptz rating_reminded_at
    jsonb rules "reglas del viaje (JSON)"
    text share_token_hash UK "enlace para compartir"
    timestamptz share_expires_at
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  trip_stops {
    uuid id PK
    uuid trip_id FK
    uuid place_id FK
    smallint position
    stop_kind kind
    timestamptz eta
    timestamptz created_at
    timestamptz updated_at
  }
  bookings {
    uuid id PK
    uuid trip_id FK
    uuid passenger_id FK
    smallint seats
    uuid pickup_place_id FK
    uuid dropoff_place_id FK
    text pickup_name
    float pickup_lat
    float pickup_lon
    timestamptz pickup_eta
    integer pickup_walk_m
    text dropoff_name
    float dropoff_lat
    float dropoff_lon
    timestamptz dropoff_eta
    integer dropoff_walk_m
    jsonb preferences
    booking_status status
    timestamptz expires_at
    boolean penalty_free
    timestamptz decided_at
    timestamptz boarded_at
    timestamptz no_show_at
    timestamptz cancelled_at
    text cancel_reason "cancelacion tardia"
    text ticket_code UK "ticket de aporte"
    integer ticket_amount
    timestamptz ticket_issued_at
    boolean paid_confirmed
    timestamptz paid_confirmed_at
    timestamptz created_at
    timestamptz updated_at
  }
  ratings {
    uuid id PK
    uuid trip_id FK
    uuid author_id FK
    uuid target_id FK
    text target_role
    jsonb scores "criterio -> estrellas (JSON)"
    float average "promedio 1 a 5"
    text comment
    boolean hidden
    timestamptz created_at
  }
  messages {
    uuid id PK
    uuid trip_id FK "el chat es del viaje"
    uuid sender_id FK
    text body
    timestamptz sent_at
    boolean hidden
  }
  emergency_events {
    uuid id PK
    uuid trip_id FK
    uuid user_id FK
    float lat
    float lon
    text note
    timestamptz created_at
    uuid handled_by FK
    timestamptz handled_at
    text resolution
  }
  system_settings {
    text key PK
    jsonb value
    uuid updated_by FK
    timestamptz created_at
    timestamptz updated_at
  }
  audit_log {
    uuid id PK
    uuid actor_id FK
    text action
    text entity
    text entity_id
    jsonb before
    jsonb after
    text ip
    timestamptz created_at
  }
  users |o--o{ audit_log : "realiza"
  users ||--o{ auth_codes : "recibe"
  places ||--o{ bookings : "punto de bajada"
  users ||--o{ bookings : "reserva"
  places ||--o{ bookings : "punto de recogida"
  trips ||--o{ bookings : "recibe"
  users |o--o{ documents : "revisa (admin)"
  semesters |o--o{ documents : "da vigencia"
  users ||--o{ documents : "sube"
  users |o--o{ emergency_events : "atiende (admin)"
  trips ||--o{ emergency_events : "ocurre en"
  users ||--o{ emergency_events : "activa"
  users ||--o{ messages : "escribe"
  trips ||--o{ messages : "tiene chat"
  users ||--o{ notifications : "recibe"
  users |o--o{ places : "crea (admin)"
  users ||--o{ ratings : "califica"
  users ||--o{ ratings : "es calificado"
  trips ||--o{ ratings : "se califica en"
  users |o--o{ system_settings : "ajusta (superadmin)"
  places ||--o{ trip_stops : "es parada de"
  trips ||--o{ trip_stops : "tiene"
  users ||--o{ trips : "conduce"
  vehicles ||--o{ trips : "se usa en"
  users ||--o{ trusted_contacts : "registra"
  users ||--o{ user_sessions : "abre"
  users ||--o{ vehicles : "es dueño de"
```

## 1. Usuarios y acceso

La cuenta, sus sesiones, los códigos de verificación enviados al correo, los avisos y los contactos de confianza. Las sanciones (suspensión de la cuenta y de reservas) son columnas de `users`.

```mermaid
erDiagram
  users {
    uuid id PK
    citext email UK "correo institucional"
    text password_hash
    text full_name
    sex sex
    text program
    user_role role "pasajero, conductor, admin, superadmin"
    user_status status
    text avatar_path
    text payment_note
    boolean two_factor_required
    timestamptz terms_accepted_at "acepto terminos al registrarse"
    timestamptz suspended_until "fin de la suspension de la cuenta"
    text suspension_reason
    timestamptz booking_ban_until "sin reservar por ausencias"
    integer failed_login_attempts
    timestamptz locked_until
    timestamptz last_login_at
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  user_sessions {
    uuid id PK
    uuid user_id FK
    text refresh_token_hash
    text device_label
    text ip
    text user_agent
    timestamptz expires_at
    timestamptz revoked_at
    timestamptz last_seen_at
    timestamptz created_at
    timestamptz updated_at
  }
  auth_codes {
    uuid id PK
    uuid user_id FK
    auth_purpose purpose
    text code_hash
    timestamptz expires_at
    integer attempts
    timestamptz used_at
    timestamptz created_at
    timestamptz updated_at
  }
  notifications {
    uuid id PK
    uuid user_id FK
    text kind
    jsonb payload
    timestamptz read_at
    timestamptz created_at
  }
  trusted_contacts {
    uuid id PK
    uuid user_id FK
    text name
    text phone
    text relationship
    timestamptz created_at
    timestamptz updated_at
  }
  users ||--o{ auth_codes : "recibe"
  users ||--o{ notifications : "recibe"
  users ||--o{ trusted_contacts : "registra"
  users ||--o{ user_sessions : "abre"
```

## 2. Documentos y vehículos

Una sola tabla `documents` guarda el carné o constancia del semestre y la licencia de conducción (`kind`), con su revisión. Los vehículos del conductor y las reglas de pico y placa.

```mermaid
erDiagram
  semesters {
    uuid id PK
    text name UK
    date starts_on
    date ends_on
    date revalidation_deadline
    timestamptz created_at
    timestamptz updated_at
  }
  documents {
    uuid id PK
    uuid user_id FK
    doc_kind kind "carne, constancia o licencia"
    text file_path
    text content_type
    review_status status
    uuid semester_id FK
    date expires_on "vencimiento de la licencia"
    uuid reviewed_by FK
    timestamptz reviewed_at
    text rejection_reason
    timestamptz created_at
    timestamptz updated_at
  }
  vehicles {
    uuid id PK
    uuid owner_id FK
    vehicle_type type
    text plate
    text brand
    text model
    text color
    smallint year
    smallint capacity
    boolean luggage_space
    text photo_path
    text photo_content_type
    boolean is_active
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  pico_placa_rules {
    uuid id PK
    vehicle_type vehicle_type
    smallint weekday
    smallint[] restricted_digits
    date valid_from
    date valid_to
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }
  users {
    uuid id PK
  }
  users |o--o{ documents : "revisa (admin)"
  semesters |o--o{ documents : "da vigencia"
  users ||--o{ documents : "sube"
  users ||--o{ vehicles : "es dueño de"
```

## 3. Viajes y reservas

El viaje con su ruta PostGIS, sus reglas (JSON) y su enlace para compartir; sus paradas en orden; y las reservas, que también guardan la cancelación tardía y el ticket de aporte.

```mermaid
erDiagram
  places {
    uuid id PK
    text name
    place_kind kind
    geometry point "ubicacion PostGIS"
    boolean is_active
    uuid created_by FK
    timestamptz created_at
    timestamptz updated_at
  }
  trips {
    uuid id PK
    uuid driver_id FK
    uuid vehicle_id FK
    timestamptz departs_at
    smallint seats_total
    integer price_per_seat
    geometry route "ruta PostGIS"
    integer distance_m
    integer est_duration_s
    trip_status status
    timestamptz started_at
    timestamptz finished_at
    text cancel_reason
    timestamptz cancelled_at
    timestamptz reminded_at
    timestamptz rating_reminded_at
    jsonb rules "reglas del viaje (JSON)"
    text share_token_hash UK "enlace para compartir"
    timestamptz share_expires_at
    timestamptz deleted_at
    timestamptz created_at
    timestamptz updated_at
  }
  trip_stops {
    uuid id PK
    uuid trip_id FK
    uuid place_id FK
    smallint position
    stop_kind kind
    timestamptz eta
    timestamptz created_at
    timestamptz updated_at
  }
  bookings {
    uuid id PK
    uuid trip_id FK
    uuid passenger_id FK
    smallint seats
    uuid pickup_place_id FK
    uuid dropoff_place_id FK
    text pickup_name
    float pickup_lat
    float pickup_lon
    timestamptz pickup_eta
    integer pickup_walk_m
    text dropoff_name
    float dropoff_lat
    float dropoff_lon
    timestamptz dropoff_eta
    integer dropoff_walk_m
    jsonb preferences
    booking_status status
    timestamptz expires_at
    boolean penalty_free
    timestamptz decided_at
    timestamptz boarded_at
    timestamptz no_show_at
    timestamptz cancelled_at
    text cancel_reason "cancelacion tardia"
    text ticket_code UK "ticket de aporte"
    integer ticket_amount
    timestamptz ticket_issued_at
    boolean paid_confirmed
    timestamptz paid_confirmed_at
    timestamptz created_at
    timestamptz updated_at
  }
  users {
    uuid id PK
  }
  vehicles {
    uuid id PK
  }
  places ||--o{ bookings : "punto de bajada"
  users ||--o{ bookings : "reserva"
  places ||--o{ bookings : "punto de recogida"
  trips ||--o{ bookings : "recibe"
  users |o--o{ places : "crea (admin)"
  places ||--o{ trip_stops : "es parada de"
  trips ||--o{ trip_stops : "tiene"
  users ||--o{ trips : "conduce"
  vehicles ||--o{ trips : "se usa en"
  users ||--o{ vehicles : "es dueño de"
```

## 4. Calificaciones, chat, seguridad y administración

Calificaciones con sus criterios en JSON, el chat de cada viaje, las alertas de emergencia, los parámetros del negocio y la auditoría inmutable.

```mermaid
erDiagram
  ratings {
    uuid id PK
    uuid trip_id FK
    uuid author_id FK
    uuid target_id FK
    text target_role
    jsonb scores "criterio -> estrellas (JSON)"
    float average "promedio 1 a 5"
    text comment
    boolean hidden
    timestamptz created_at
  }
  messages {
    uuid id PK
    uuid trip_id FK "el chat es del viaje"
    uuid sender_id FK
    text body
    timestamptz sent_at
    boolean hidden
  }
  emergency_events {
    uuid id PK
    uuid trip_id FK
    uuid user_id FK
    float lat
    float lon
    text note
    timestamptz created_at
    uuid handled_by FK
    timestamptz handled_at
    text resolution
  }
  system_settings {
    text key PK
    jsonb value
    uuid updated_by FK
    timestamptz created_at
    timestamptz updated_at
  }
  audit_log {
    uuid id PK
    uuid actor_id FK
    text action
    text entity
    text entity_id
    jsonb before
    jsonb after
    text ip
    timestamptz created_at
  }
  users {
    uuid id PK
  }
  trips {
    uuid id PK
  }
  users |o--o{ audit_log : "realiza"
  users |o--o{ emergency_events : "atiende (admin)"
  trips ||--o{ emergency_events : "ocurre en"
  users ||--o{ emergency_events : "activa"
  users ||--o{ messages : "escribe"
  trips ||--o{ messages : "tiene chat"
  users ||--o{ ratings : "califica"
  users ||--o{ ratings : "es calificado"
  trips ||--o{ ratings : "se califica en"
  users |o--o{ system_settings : "ajusta (superadmin)"
  users ||--o{ trips : "conduce"
```

## Relaciones

| Desde | Hacia | Llave foránea | Significado |
|-------|-------|---------------|-------------|
| `users` | `audit_log` | `audit_log.actor_id` | realiza |
| `users` | `auth_codes` | `auth_codes.user_id` | recibe |
| `places` | `bookings` | `bookings.dropoff_place_id` | punto de bajada |
| `users` | `bookings` | `bookings.passenger_id` | reserva |
| `places` | `bookings` | `bookings.pickup_place_id` | punto de recogida |
| `trips` | `bookings` | `bookings.trip_id` | recibe |
| `users` | `documents` | `documents.reviewed_by` | revisa (admin) |
| `semesters` | `documents` | `documents.semester_id` | da vigencia |
| `users` | `documents` | `documents.user_id` | sube |
| `users` | `emergency_events` | `emergency_events.handled_by` | atiende (admin) |
| `trips` | `emergency_events` | `emergency_events.trip_id` | ocurre en |
| `users` | `emergency_events` | `emergency_events.user_id` | activa |
| `users` | `messages` | `messages.sender_id` | escribe |
| `trips` | `messages` | `messages.trip_id` | tiene chat |
| `users` | `notifications` | `notifications.user_id` | recibe |
| `users` | `places` | `places.created_by` | crea (admin) |
| `users` | `ratings` | `ratings.author_id` | califica |
| `users` | `ratings` | `ratings.target_id` | es calificado |
| `trips` | `ratings` | `ratings.trip_id` | se califica en |
| `users` | `system_settings` | `system_settings.updated_by` | ajusta (superadmin) |
| `places` | `trip_stops` | `trip_stops.place_id` | es parada de |
| `trips` | `trip_stops` | `trip_stops.trip_id` | tiene |
| `users` | `trips` | `trips.driver_id` | conduce |
| `vehicles` | `trips` | `trips.vehicle_id` | se usa en |
| `users` | `trusted_contacts` | `trusted_contacts.user_id` | registra |
| `users` | `user_sessions` | `user_sessions.user_id` | abre |
| `users` | `vehicles` | `vehicles.owner_id` | es dueño de |

## Qué cambió frente al modelo anterior (35 tablas)

| Antes | Ahora |
|-------|-------|
| `identity_documents` y `driver_licenses` | `documents` con `kind` |
| `cancellation_requests` | columnas `cancel_reason` y estado `cancel_requested` en `bookings` |
| `tickets` | columnas `ticket_*` y `paid_confirmed*` en `bookings` |
| `trip_rules` | `trips.rules` (JSON) |
| `rating_scores` | `ratings.scores` (JSON) y `ratings.average` |
| `conversations` y `conversation_members` | `messages.trip_id`: un chat por viaje |
| `share_links` | `trips.share_token_hash` y `trips.share_expires_at` |
| `suspensions` | `users.suspended_until`, `users.suspension_reason`, `users.booking_ban_until` |
| `user_stats` | se calcula con consultas agrupadas al pedirla |
| `legal_documents` y `terms_acceptances` | archivos `frontend/public/legal/*.md` y `users.terms_accepted_at` |
| `trip_series`, `series_stops`, `series_subscriptions`, `waitlist_entries`, `traffic_factors` | eliminadas junto con su función (viajes recurrentes, lista de espera y factor de tráfico) |

## Anexo: todas las columnas

### `users`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `email` | citext | no | UK |
| `password_hash` | text | no |  |
| `full_name` | text | no |  |
| `sex` | sex | no |  |
| `program` | text | sí |  |
| `role` | user_role | no |  |
| `status` | user_status | no |  |
| `avatar_path` | text | sí |  |
| `payment_note` | text | sí |  |
| `two_factor_required` | boolean | no |  |
| `terms_accepted_at` | timestamptz | sí |  |
| `suspended_until` | timestamptz | sí |  |
| `suspension_reason` | text | sí |  |
| `booking_ban_until` | timestamptz | sí |  |
| `failed_login_attempts` | integer | no |  |
| `locked_until` | timestamptz | sí |  |
| `last_login_at` | timestamptz | sí |  |
| `deleted_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `user_sessions`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `user_id` | uuid | no | FK → `users` |
| `refresh_token_hash` | text | no |  |
| `device_label` | text | no |  |
| `ip` | text | sí |  |
| `user_agent` | text | sí |  |
| `expires_at` | timestamptz | no |  |
| `revoked_at` | timestamptz | sí |  |
| `last_seen_at` | timestamptz | no |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `auth_codes`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `user_id` | uuid | no | FK → `users` |
| `purpose` | auth_purpose | no |  |
| `code_hash` | text | no |  |
| `expires_at` | timestamptz | no |  |
| `attempts` | integer | no |  |
| `used_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `notifications`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `user_id` | uuid | no | FK → `users` |
| `kind` | text | no |  |
| `payload` | jsonb | no |  |
| `read_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |

### `trusted_contacts`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `user_id` | uuid | no | FK → `users` |
| `name` | text | no |  |
| `phone` | text | no |  |
| `relationship` | text | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `semesters`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `name` | text | no | UK |
| `starts_on` | date | no |  |
| `ends_on` | date | no |  |
| `revalidation_deadline` | date | no |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `documents`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `user_id` | uuid | no | FK → `users` |
| `kind` | doc_kind | no |  |
| `file_path` | text | no |  |
| `content_type` | text | no |  |
| `status` | review_status | no |  |
| `semester_id` | uuid | sí | FK → `semesters` |
| `expires_on` | date | sí |  |
| `reviewed_by` | uuid | sí | FK → `users` |
| `reviewed_at` | timestamptz | sí |  |
| `rejection_reason` | text | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `vehicles`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `owner_id` | uuid | no | FK → `users` |
| `type` | vehicle_type | no |  |
| `plate` | text | no |  |
| `brand` | text | no |  |
| `model` | text | no |  |
| `color` | text | no |  |
| `year` | smallint | no |  |
| `capacity` | smallint | no |  |
| `luggage_space` | boolean | no |  |
| `photo_path` | text | sí |  |
| `photo_content_type` | text | sí |  |
| `is_active` | boolean | no |  |
| `deleted_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `pico_placa_rules`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `vehicle_type` | vehicle_type | no |  |
| `weekday` | smallint | no |  |
| `restricted_digits` | smallint[] | no |  |
| `valid_from` | date | no |  |
| `valid_to` | date | sí |  |
| `is_active` | boolean | no |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `places`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `name` | text | no |  |
| `kind` | place_kind | no |  |
| `point` | geometry | no |  |
| `is_active` | boolean | no |  |
| `created_by` | uuid | sí | FK → `users` |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `trips`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `driver_id` | uuid | no | FK → `users` |
| `vehicle_id` | uuid | no | FK → `vehicles` |
| `departs_at` | timestamptz | no |  |
| `seats_total` | smallint | no |  |
| `price_per_seat` | integer | no |  |
| `route` | geometry | no |  |
| `distance_m` | integer | no |  |
| `est_duration_s` | integer | no |  |
| `status` | trip_status | no |  |
| `started_at` | timestamptz | sí |  |
| `finished_at` | timestamptz | sí |  |
| `cancel_reason` | text | sí |  |
| `cancelled_at` | timestamptz | sí |  |
| `reminded_at` | timestamptz | sí |  |
| `rating_reminded_at` | timestamptz | sí |  |
| `rules` | jsonb | no |  |
| `share_token_hash` | text | sí | UK |
| `share_expires_at` | timestamptz | sí |  |
| `deleted_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `trip_stops`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `trip_id` | uuid | no | FK → `trips` |
| `place_id` | uuid | no | FK → `places` |
| `position` | smallint | no |  |
| `kind` | stop_kind | no |  |
| `eta` | timestamptz | no |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `bookings`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `trip_id` | uuid | no | FK → `trips` |
| `passenger_id` | uuid | no | FK → `users` |
| `seats` | smallint | no |  |
| `pickup_place_id` | uuid | no | FK → `places` |
| `dropoff_place_id` | uuid | no | FK → `places` |
| `pickup_name` | text | sí |  |
| `pickup_lat` | float | no |  |
| `pickup_lon` | float | no |  |
| `pickup_eta` | timestamptz | no |  |
| `pickup_walk_m` | integer | no |  |
| `dropoff_name` | text | sí |  |
| `dropoff_lat` | float | no |  |
| `dropoff_lon` | float | no |  |
| `dropoff_eta` | timestamptz | no |  |
| `dropoff_walk_m` | integer | no |  |
| `preferences` | jsonb | no |  |
| `status` | booking_status | no |  |
| `expires_at` | timestamptz | no |  |
| `penalty_free` | boolean | no |  |
| `decided_at` | timestamptz | sí |  |
| `boarded_at` | timestamptz | sí |  |
| `no_show_at` | timestamptz | sí |  |
| `cancelled_at` | timestamptz | sí |  |
| `cancel_reason` | text | sí |  |
| `ticket_code` | text | sí | UK |
| `ticket_amount` | integer | sí |  |
| `ticket_issued_at` | timestamptz | sí |  |
| `paid_confirmed` | boolean | no |  |
| `paid_confirmed_at` | timestamptz | sí |  |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `ratings`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `trip_id` | uuid | no | FK → `trips` |
| `author_id` | uuid | no | FK → `users` |
| `target_id` | uuid | no | FK → `users` |
| `target_role` | text | no |  |
| `scores` | jsonb | no |  |
| `average` | float | no |  |
| `comment` | text | sí |  |
| `hidden` | boolean | no |  |
| `created_at` | timestamptz | no |  |

### `messages`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `trip_id` | uuid | no | FK → `trips` |
| `sender_id` | uuid | no | FK → `users` |
| `body` | text | no |  |
| `sent_at` | timestamptz | no |  |
| `hidden` | boolean | no |  |

### `emergency_events`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `trip_id` | uuid | no | FK → `trips` |
| `user_id` | uuid | no | FK → `users` |
| `lat` | float | sí |  |
| `lon` | float | sí |  |
| `note` | text | sí |  |
| `created_at` | timestamptz | no |  |
| `handled_by` | uuid | sí | FK → `users` |
| `handled_at` | timestamptz | sí |  |
| `resolution` | text | sí |  |

### `system_settings`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `key` | text | no | PK |
| `value` | jsonb | no |  |
| `updated_by` | uuid | sí | FK → `users` |
| `created_at` | timestamptz | no |  |
| `updated_at` | timestamptz | no |  |

### `audit_log`

| Columna | Tipo | Nula | Llave |
|---------|------|------|-------|
| `id` | uuid | no | PK |
| `actor_id` | uuid | sí | FK → `users` |
| `action` | text | no |  |
| `entity` | text | no |  |
| `entity_id` | text | sí |  |
| `before` | jsonb | sí |  |
| `after` | jsonb | sí |  |
| `ip` | text | sí |  |
| `created_at` | timestamptz | no |  |
