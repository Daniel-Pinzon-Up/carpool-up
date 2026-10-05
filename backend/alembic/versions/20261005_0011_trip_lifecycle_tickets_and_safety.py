"""Ciclo del viaje y seguridad: tickets, contactos de confianza, enlaces y emergencias.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-05 21:36:32.839826
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
        "share_links",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_share_links_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_share_links_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_share_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_share_links_token_hash")),
    )
    op.create_index(op.f("ix_share_links_trip_id"), "share_links", ["trip_id"], unique=False)
    op.create_table(
        "tickets",
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("paid_confirmed", sa.Boolean(), nullable=False),
        sa.Column("paid_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_tickets_amount_non_negative")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_tickets_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
        sa.UniqueConstraint("booking_id", name=op.f("uq_tickets_booking_id")),
        sa.UniqueConstraint("code", name=op.f("uq_tickets_code")),
    )
    op.add_column("trips", sa.Column("osrm_duration_s", sa.Integer(), nullable=True))
    op.add_column("trips", sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trips", "reminded_at")
    op.drop_column("trips", "osrm_duration_s")
    op.drop_table("tickets")
    op.drop_index(op.f("ix_share_links_trip_id"), table_name="share_links")
    op.drop_table("share_links")
    op.drop_index(op.f("ix_emergency_events_trip_id"), table_name="emergency_events")
    op.drop_index(
        "ix_emergency_events_open",
        table_name="emergency_events",
        postgresql_where=sa.text("handled_at IS NULL"),
    )
    op.drop_table("emergency_events")
    op.drop_index("ix_trusted_contacts_user", table_name="trusted_contacts")
    op.drop_table("trusted_contacts")
