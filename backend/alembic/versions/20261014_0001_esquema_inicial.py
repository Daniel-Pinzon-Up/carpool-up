"""Esquema inicial de Carpool UP: 18 tablas.

Usuarios y acceso: users, user_sessions, auth_codes, notifications, trusted_contacts.
Documentos: semesters, documents (carnet, constancia y licencia).
Viajes: vehicles, places, pico_placa_rules, trips, trip_stops.
Reservas y despues del viaje: bookings (con ticket y cancelacion tardia), ratings, messages,
emergency_events.
Administracion: system_settings, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS = (
    "auth_purpose",
    "booking_status",
    "doc_kind",
    "place_kind",
    "review_status",
    "sex",
    "stop_kind",
    "trip_status",
    "user_role",
    "user_status",
    "vehicle_type",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "pico_placa_rules",
        sa.Column(
            "vehicle_type", sa.Enum("car", "motorcycle", name="vehicle_type"), nullable=False
        ),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("restricted_digits", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cardinality(restricted_digits) > 0 AND restricted_digits <@ ARRAY[0,1,2,3,4,5,6,7,8,9]::smallint[]",  # noqa: E501
            name=op.f("ck_pico_placa_rules_digits_range"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name=op.f("ck_pico_placa_rules_validity_order"),
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name=op.f("ck_pico_placa_rules_weekday_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pico_placa_rules")),
    )
    op.create_index(
        "ix_pico_placa_lookup",
        "pico_placa_rules",
        ["vehicle_type", "weekday", "is_active"],
        unique=False,
    )
    op.create_table(
        "semesters",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("revalidation_deadline", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_on > starts_on", name=op.f("ck_semesters_dates_order")),
        sa.CheckConstraint(
            "revalidation_deadline BETWEEN starts_on AND ends_on",
            name=op.f("ck_semesters_deadline_in_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semesters")),
        sa.UniqueConstraint("name", name=op.f("uq_semesters_name")),
    )
    # Dos semestres no pueden solaparse, ni siquiera en una carrera entre peticiones.
    op.execute(
        "ALTER TABLE semesters ADD CONSTRAINT ex_semesters_no_overlap "
        "EXCLUDE USING gist (daterange(starts_on, ends_on, '[]') WITH &&)"
    )
    op.create_table(
        "users",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("sex", sa.Enum("female", "male", name="sex"), nullable=False),
        sa.Column("program", sa.Text(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("passenger", "driver", "admin", "superadmin", name="user_role"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending_email",
                "pending_approval",
                "active",
                "suspended",
                "blocked",
                name="user_status",
            ),
            nullable=False,
        ),
        sa.Column("avatar_path", sa.Text(), nullable=True),
        sa.Column("payment_note", sa.Text(), nullable=True),
        sa.Column("two_factor_required", sa.Boolean(), nullable=False),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        sa.Column("booking_ban_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_index("ix_audit_log_created_at_id", "audit_log", ["created_at", "id"], unique=False)
    op.create_index("ix_audit_log_entity", "audit_log", ["entity", "entity_id"], unique=False)
    # Registro inmutable: solo se inserta. El SET NULL de la FK hacia users se permite para
    # poder anonimizar cuentas sin perder la entrada.
    op.execute(
        """
        CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL
               AND (NEW.id, NEW.action, NEW.entity, NEW.entity_id, NEW.before, NEW.after,
                    NEW.ip, NEW.created_at)
                   IS NOT DISTINCT FROM
                   (OLD.id, OLD.action, OLD.entity, OLD.entity_id, OLD.before, OLD.after,
                    OLD.ip, OLD.created_at)
            THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()"
    )
    op.create_table(
        "auth_codes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("email_verification", "two_factor", "password_reset", name="auth_purpose"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_codes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_codes")),
    )
    op.create_index(
        "ix_auth_codes_lookup", "auth_codes", ["user_id", "purpose", "used_at"], unique=False
    )
    op.create_table(
        "documents",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("student_card", "institutional_proof", "driver_license", name="doc_kind"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "expired", name="review_status"),
            nullable=False,
        ),
        sa.Column("semester_id", sa.UUID(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_documents_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["semester_id"],
            ["semesters.id"],
            name=op.f("fk_documents_semester_id_semesters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_documents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(op.f("ix_documents_semester_id"), "documents", ["semester_id"], unique=False)
    op.create_index(
        "ix_documents_user_kind_created",
        "documents",
        ["user_id", "kind", "created_at"],
        unique=False,
    )
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at", "id"],
        unique=False,
    )
    op.create_geospatial_table(
        "places",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("campus", "sector", "landmark", "custom", name="place_kind"),
            nullable=False,
        ),
        sa.Column(
            "point",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_places_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_places")),
    )
    op.create_geospatial_index(
        "idx_places_point",
        "places",
        ["point"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(op.f("ix_places_created_by"), "places", ["created_by"], unique=False)
    op.create_index("ix_places_kind_active", "places", ["kind", "is_active"], unique=False)
    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_system_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_settings")),
    )
    op.create_table(
        "trusted_contacts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_trusted_contacts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trusted_contacts")),
    )
    op.create_index("ix_trusted_contacts_user", "trusted_contacts", ["user_id"], unique=False)
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("device_label", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
    )
    op.create_index(
        "ix_user_sessions_user_active", "user_sessions", ["user_id", "revoked_at"], unique=False
    )
    op.create_table(
        "vehicles",
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.Enum("car", "motorcycle", name="vehicle_type"), nullable=False),
        sa.Column("plate", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("capacity", sa.SmallInteger(), nullable=False),
        sa.Column("luggage_space", sa.Boolean(), nullable=False),
        sa.Column("photo_path", sa.Text(), nullable=True),
        sa.Column("photo_content_type", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type = 'car' AND capacity BETWEEN 2 AND 8) OR (type = 'motorcycle' AND capacity = 2)",
            name=op.f("ck_vehicles_capacity_by_type"),
        ),
        sa.CheckConstraint("plate = upper(plate)", name=op.f("ck_vehicles_plate_uppercase")),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_vehicles_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
    )
    op.create_index(op.f("ix_vehicles_owner_id"), "vehicles", ["owner_id"], unique=False)
    op.create_index(
        "uq_vehicles_plate_alive",
        "vehicles",
        ["plate"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_geospatial_table(
        "trips",
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seats_total", sa.SmallInteger(), nullable=False),
        sa.Column("price_per_seat", sa.Integer(), nullable=False),
        sa.Column(
            "route",
            Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("est_duration_s", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "in_progress",
                "completed",
                "cancelled_by_driver",
                "cancelled_pico_placa",
                "not_held",
                name="trip_status",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rating_reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("share_token_hash", sa.Text(), nullable=True),
        sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status <> 'cancelled_by_driver' OR cancel_reason IS NOT NULL",
            name=op.f("ck_trips_cancel_has_reason"),
        ),
        sa.CheckConstraint("price_per_seat >= 0", name=op.f("ck_trips_price_non_negative")),
        sa.CheckConstraint("seats_total BETWEEN 1 AND 7", name=op.f("ck_trips_seats_range")),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["users.id"], name=op.f("fk_trips_driver_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name=op.f("fk_trips_vehicle_id_vehicles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
        sa.UniqueConstraint("share_token_hash", name=op.f("uq_trips_share_token_hash")),
    )
    op.create_geospatial_index(
        "idx_trips_route",
        "trips",
        ["route"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index("ix_trips_driver_departs", "trips", ["driver_id", "departs_at"], unique=False)
    op.create_index(
        "ix_trips_route_geography",
        "trips",
        [sa.literal_column("(route::geography)")],
        unique=False,
        postgresql_using="gist",
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_trips_scheduled_departs",
        "trips",
        ["departs_at"],
        unique=False,
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.create_table(
        "bookings",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("pickup_place_id", sa.UUID(), nullable=False),
        sa.Column("dropoff_place_id", sa.UUID(), nullable=False),
        sa.Column("pickup_name", sa.Text(), nullable=True),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lon", sa.Float(), nullable=False),
        sa.Column("pickup_eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pickup_walk_m", sa.Integer(), nullable=False),
        sa.Column("dropoff_name", sa.Text(), nullable=True),
        sa.Column("dropoff_lat", sa.Float(), nullable=False),
        sa.Column("dropoff_lon", sa.Float(), nullable=False),
        sa.Column("dropoff_eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dropoff_walk_m", sa.Integer(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "accepted",
                "rejected",
                "cancel_requested",
                "cancelled_by_passenger",
                "cancelled_by_driver",
                "auto_cancelled_late",
                "auto_cancelled_pico_placa",
                "expired",
                "no_show",
                "completed",
                name="booking_status",
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("penalty_free", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("boarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("no_show_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("ticket_code", sa.Text(), nullable=True),
        sa.Column("ticket_amount", sa.Integer(), nullable=True),
        sa.Column("ticket_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_confirmed", sa.Boolean(), nullable=False),
        sa.Column("paid_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("seats BETWEEN 1 AND 7", name=op.f("ck_bookings_seats_range")),
        sa.CheckConstraint(
            "ticket_amount >= 0", name=op.f("ck_bookings_ticket_amount_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["dropoff_place_id"],
            ["places.id"],
            name=op.f("fk_bookings_dropoff_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"],
            ["users.id"],
            name=op.f("fk_bookings_passenger_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pickup_place_id"],
            ["places.id"],
            name=op.f("fk_bookings_pickup_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_bookings_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.UniqueConstraint("ticket_code", name=op.f("uq_bookings_ticket_code")),
    )
    op.create_index(
        "ix_bookings_passenger_pickup", "bookings", ["passenger_id", "pickup_eta"], unique=False
    )
    op.create_index("ix_bookings_trip_status", "bookings", ["trip_id", "status"], unique=False)
    op.create_index(
        "uq_bookings_active_passenger",
        "bookings",
        ["trip_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'accepted', 'cancel_requested')"),
    )
    op.create_table(
        "emergency_events",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("handled_by", sa.UUID(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(lat IS NULL) = (lon IS NULL)", name=op.f("ck_emergency_events_location_pair")
        ),
        sa.ForeignKeyConstraint(
            ["handled_by"],
            ["users.id"],
            name=op.f("fk_emergency_events_handled_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name=op.f("fk_emergency_events_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_emergency_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emergency_events")),
    )
    op.create_index(
        "ix_emergency_events_open",
        "emergency_events",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("handled_at IS NULL"),
    )
    op.create_index(
        op.f("ix_emergency_events_trip_id"), "emergency_events", ["trip_id"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 1000", name=op.f("ck_messages_body_length")
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_messages_sender_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_messages_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_trip_sent", "messages", ["trip_id", "sent_at", "id"], unique=False)
    op.create_table(
        "ratings",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("target_role", sa.Text(), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("average", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "target_role IN ('driver', 'passenger')", name=op.f("ck_ratings_target_role_values")
        ),
        sa.CheckConstraint("author_id <> target_id", name=op.f("ck_ratings_not_self")),
        sa.CheckConstraint("average BETWEEN 1 AND 5", name=op.f("ck_ratings_average_range")),
        sa.CheckConstraint("char_length(comment) <= 300", name=op.f("ck_ratings_comment_length")),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_ratings_author_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["users.id"], name=op.f("fk_ratings_target_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_ratings_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ratings")),
        sa.UniqueConstraint("trip_id", "author_id", "target_id", name="uq_ratings_pair"),
    )
    op.create_index(
        "ix_ratings_target_created", "ratings", ["target_id", "created_at"], unique=False
    )
    op.create_table(
        "trip_stops",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("place_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "kind", sa.Enum("origin", "stop", "destination", name="stop_kind"), nullable=False
        ),
        sa.Column("eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["places.id"],
            name=op.f("fk_trip_stops_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_stops_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_stops")),
        sa.UniqueConstraint("trip_id", "position", name="uq_trip_stops_position"),
    )
    op.create_index(op.f("ix_trip_stops_place_id"), "trip_stops", ["place_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trip_stops_place_id"), table_name="trip_stops")
    op.drop_table("trip_stops")
    op.drop_index("ix_ratings_target_created", table_name="ratings")
    op.drop_table("ratings")
    op.drop_index("ix_messages_trip_sent", table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_emergency_events_trip_id"), table_name="emergency_events")
    op.drop_index(
        "ix_emergency_events_open",
        table_name="emergency_events",
        postgresql_where=sa.text("handled_at IS NULL"),
    )
    op.drop_table("emergency_events")
    op.drop_index(
        "uq_bookings_active_passenger",
        table_name="bookings",
        postgresql_where=sa.text("status IN ('requested', 'accepted', 'cancel_requested')"),
    )
    op.drop_index("ix_bookings_trip_status", table_name="bookings")
    op.drop_index("ix_bookings_passenger_pickup", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(
        "ix_trips_scheduled_departs",
        table_name="trips",
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_trips_route_geography",
        table_name="trips",
        postgresql_using="gist",
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.drop_index("ix_trips_driver_departs", table_name="trips")
    op.drop_geospatial_index(
        "idx_trips_route", table_name="trips", postgresql_using="gist", column_name="route"
    )
    op.drop_geospatial_table("trips")
    op.drop_index(
        "uq_vehicles_plate_alive",
        table_name="vehicles",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_vehicles_owner_id"), table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_trusted_contacts_user", table_name="trusted_contacts")
    op.drop_table("trusted_contacts")
    op.drop_table("system_settings")
    op.drop_index("ix_places_kind_active", table_name="places")
    op.drop_index(op.f("ix_places_created_by"), table_name="places")
    op.drop_geospatial_index(
        "idx_places_point", table_name="places", postgresql_using="gist", column_name="point"
    )
    op.drop_geospatial_table("places")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_documents_user_kind_created", table_name="documents")
    op.drop_index(op.f("ix_documents_semester_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_auth_codes_lookup", table_name="auth_codes")
    op.drop_table("auth_codes")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at_id", table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("semesters")
    op.drop_index("ix_pico_placa_lookup", table_name="pico_placa_rules")
    op.drop_table("pico_placa_rules")
    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
