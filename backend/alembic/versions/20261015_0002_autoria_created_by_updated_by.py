"""Autoria en todas las tablas: created_by y updated_by.

Cada tabla gana quien creo la fila y quien la cambio por ultima vez (FK a users, SET NULL
para poder anonimizar cuentas). places ya tenia created_by y system_settings updated_by.
En audit_log el autor (actor_id) pasa a llamarse created_by y se agrega updated_by, que el
trigger mantiene siempre nulo. Las filas existentes toman como autor a su dueno evidente.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOTH = [
    "users",
    "user_sessions",
    "auth_codes",
    "notifications",
    "trusted_contacts",
    "semesters",
    "documents",
    "vehicles",
    "pico_placa_rules",
    "trips",
    "trip_stops",
    "bookings",
    "ratings",
    "messages",
    "emergency_events",
]
NEW_COLUMNS = [(table, column) for table in BOTH for column in ("created_by", "updated_by")] + [
    ("places", "updated_by"),
    ("system_settings", "created_by"),
    ("audit_log", "updated_by"),
]

# Autor de las filas que ya existian: la persona duena de cada una.
OWNERS = {
    "user_sessions": "user_id",
    "trusted_contacts": "user_id",
    "documents": "user_id",
    "vehicles": "owner_id",
    "trips": "driver_id",
    "bookings": "passenger_id",
    "ratings": "author_id",
    "messages": "sender_id",
    "emergency_events": "user_id",
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
