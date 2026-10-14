"""Autoria en todas las tablas: created_by y updated_by.

Cada tabla gana quien creo la fila y quien la cambio por ultima vez (FK a users, SET NULL
para poder anonimizar cuentas). places, share_links y suspensions ya tenian created_by y
system_settings updated_by.
En audit_log el autor (actor_id) pasa a llamarse created_by y se agrega updated_by, que el
trigger mantiene siempre nulo. Las filas existentes toman como autor a su dueno evidente.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOTH = [
    "auth_codes",
    "bookings",
    "cancellation_requests",
    "conversation_members",
    "conversations",
    "driver_licenses",
    "emergency_events",
    "identity_documents",
    "legal_documents",
    "messages",
    "notifications",
    "pico_placa_rules",
    "rating_scores",
    "ratings",
    "semesters",
    "series_stops",
    "series_subscriptions",
    "terms_acceptances",
    "tickets",
    "traffic_factors",
    "trip_rules",
    "trip_series",
    "trip_stops",
    "trips",
    "trusted_contacts",
    "user_sessions",
    "user_stats",
    "users",
    "vehicles",
    "waitlist_entries",
]
NEW_COLUMNS = [(table, column) for table in BOTH for column in ("created_by", "updated_by")] + [
    ("places", "updated_by"),
    ("share_links", "updated_by"),
    ("suspensions", "updated_by"),
    ("system_settings", "created_by"),
    ("audit_log", "updated_by"),
]

# Autor de las filas que ya existian: la persona duena de cada una.
OWNERS = {
    "user_sessions": "user_id",
    "identity_documents": "user_id",
    "driver_licenses": "user_id",
    "terms_acceptances": "user_id",
    "trusted_contacts": "user_id",
    "emergency_events": "user_id",
    "vehicles": "owner_id",
    "trips": "driver_id",
    "trip_series": "driver_id",
    "bookings": "passenger_id",
    "series_subscriptions": "passenger_id",
    "waitlist_entries": "passenger_id",
    "cancellation_requests": "requested_by",
    "ratings": "author_id",
    "messages": "sender_id",
}

TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.created_by IS NULL AND OLD.created_by IS NOT NULL
       AND (NEW.id, NEW.action, NEW.entity, NEW.entity_id, NEW.before, NEW.after,
            NEW.ip, NEW.created_at, NEW.updated_by)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.action, OLD.entity, OLD.entity_id, OLD.before, OLD.after,
            OLD.ip, OLD.created_at, OLD.updated_by)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql
"""

OLD_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
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


def upgrade() -> None:
    op.alter_column("audit_log", "actor_id", new_column_name="created_by")
    op.execute("ALTER INDEX ix_audit_log_actor_id RENAME TO ix_audit_log_created_by")
    op.execute(
        "ALTER TABLE audit_log RENAME CONSTRAINT fk_audit_log_actor_id_users "
        "TO fk_audit_log_created_by_users"
    )
    op.execute(TRIGGER_FUNCTION)

    for table, column in NEW_COLUMNS:
        op.add_column(table, sa.Column(column, sa.UUID(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_{column}_users"),
            table,
            "users",
            [column],
            ["id"],
            ondelete="SET NULL",
        )

    for table, owner in OWNERS.items():
        # Nombres fijos de este archivo, no datos de usuarios.
        op.execute(f"UPDATE {table} SET created_by = {owner} WHERE created_by IS NULL")  # noqa: S608


def downgrade() -> None:
    for table, column in reversed(NEW_COLUMNS):
        op.drop_constraint(op.f(f"fk_{table}_{column}_users"), table, type_="foreignkey")
        op.drop_column(table, column)

    op.execute(
        "ALTER TABLE audit_log RENAME CONSTRAINT fk_audit_log_created_by_users "
        "TO fk_audit_log_actor_id_users"
    )
    op.execute("ALTER INDEX ix_audit_log_created_by RENAME TO ix_audit_log_actor_id")
    op.alter_column("audit_log", "created_by", new_column_name="actor_id")
    op.execute(OLD_TRIGGER_FUNCTION)
