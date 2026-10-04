"""Configuracion y catalogos: usuarios, parametros, semestres, lugares, pico y placa,
documentos legales y auditoria.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los tipos enum se crean una sola vez y las columnas los reutilizan (create_type=False).
ENUMS = {
    "sex": ("female", "male"),
    "user_role": ("passenger", "driver", "admin", "superadmin"),
    "user_status": ("pending_email", "pending_approval", "active", "suspended", "blocked"),
    "language": ("es", "en", "pt", "fr"),
    "theme_preference": ("system", "light", "dark"),
    "place_kind": ("campus", "sector", "landmark", "custom"),
    "vehicle_type": ("car", "motorcycle"),
    "legal_kind": ("terms", "data_policy"),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
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
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("sex", enum("sex"), nullable=False),
        sa.Column("program", sa.Text(), nullable=True),
        sa.Column("role", enum("user_role"), nullable=False),
        sa.Column("status", enum("user_status"), nullable=False),
        sa.Column("avatar_path", sa.Text(), nullable=True),
        sa.Column("payment_note", sa.Text(), nullable=True),
        sa.Column("two_factor_required", sa.Boolean(), nullable=False),
        sa.Column("preferred_language", enum("language"), nullable=False),
        sa.Column("theme_preference", enum("theme_preference"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_system_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_settings")),
    )

    op.create_table(
        "semesters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("revalidation_deadline", sa.Date(), nullable=False),
        *timestamps(),
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

    op.create_geospatial_table(
        "places",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", enum("place_kind"), nullable=False),
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
        *timestamps(),
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
        "pico_placa_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vehicle_type", enum("vehicle_type"), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("restricted_digits", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "cardinality(restricted_digits) > 0 "
            "AND restricted_digits <@ ARRAY[0,1,2,3,4,5,6,7,8,9]::smallint[]",
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
        "ix_pico_placa_lookup", "pico_placa_rules", ["vehicle_type", "weekday", "is_active"]
    )

    op.create_table(
        "legal_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", enum("legal_kind"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("language", enum("language"), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_documents")),
        sa.UniqueConstraint("kind", "language", "version", name="uq_legal_documents_version"),
    )
    op.create_index(
        "uq_legal_documents_current",
        "legal_documents",
        ["kind", "language"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_created_at_id", "audit_log", ["created_at", "id"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity", "entity_id"])
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


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_index("uq_legal_documents_current", table_name="legal_documents")
    op.drop_table("legal_documents")
    op.drop_index("ix_pico_placa_lookup", table_name="pico_placa_rules")
    op.drop_table("pico_placa_rules")
    op.drop_index("ix_places_kind_active", table_name="places")
    op.drop_index(op.f("ix_places_created_by"), table_name="places")
    op.drop_geospatial_index(
        "idx_places_point", table_name="places", postgresql_using="gist", column_name="point"
    )
    op.drop_geospatial_table("places")
    op.drop_table("semesters")
    op.drop_table("system_settings")
    op.drop_table("users")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
