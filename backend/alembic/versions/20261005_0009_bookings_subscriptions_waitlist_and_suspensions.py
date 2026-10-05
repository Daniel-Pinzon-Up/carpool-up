"""Reservas, suscripciones a series, lista de espera, cancelaciones tardias y sanciones.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05 19:55:02.753332
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suspensions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind", sa.Enum("booking_ban", "account", name="suspension_kind"), nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name=op.f("ck_suspensions_period_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_suspensions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_suspensions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suspensions")),
    )
    op.create_index("ix_suspensions_user_kind", "suspensions", ["user_id", "kind"], unique=False)
    op.create_table(
        "series_subscriptions",
        sa.Column("series_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("pickup_place_id", sa.UUID(), nullable=False),
        sa.Column("dropoff_place_id", sa.UUID(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "active",
                "rejected",
                "cancelled",
                "finished",
                "expired",
                name="subscription_status",
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
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
            "seats BETWEEN 1 AND 7", name=op.f("ck_series_subscriptions_seats_range")
        ),
        sa.CheckConstraint(
            "to_date >= from_date", name=op.f("ck_series_subscriptions_range_order")
        ),
        sa.ForeignKeyConstraint(
            ["dropoff_place_id"],
            ["places.id"],
            name=op.f("fk_series_subscriptions_dropoff_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"],
            ["users.id"],
            name=op.f("fk_series_subscriptions_passenger_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pickup_place_id"],
            ["places.id"],
            name=op.f("fk_series_subscriptions_pickup_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["trip_series.id"],
            name=op.f("fk_series_subscriptions_series_id_trip_series"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series_subscriptions")),
    )
    op.create_index(
        "ix_series_subscriptions_passenger",
        "series_subscriptions",
        ["passenger_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_series_subscriptions_open",
        "series_subscriptions",
        ["series_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'active')"),
    )
    op.create_table(
        "bookings",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=True),
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
            ["subscription_id"],
            ["series_subscriptions.id"],
            name=op.f("fk_bookings_subscription_id_series_subscriptions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_bookings_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(
        "ix_bookings_passenger_pickup", "bookings", ["passenger_id", "pickup_eta"], unique=False
    )
    op.create_index(
        op.f("ix_bookings_subscription_id"), "bookings", ["subscription_id"], unique=False
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
        "cancellation_requests",
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "rejected", name="cancel_request_status"),
            nullable=False,
        ),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_cancellation_requests_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_cancellation_requests_requested_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name=op.f("fk_cancellation_requests_resolved_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cancellation_requests")),
    )
    op.create_index(
        "uq_cancellation_requests_pending",
        "cancellation_requests",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "waitlist_entries",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("pickup_place_id", sa.UUID(), nullable=False),
        sa.Column("dropoff_place_id", sa.UUID(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("waiting", "offered", "converted", "expired", "left", name="waitlist_status"),
            nullable=False,
        ),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booking_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("seats BETWEEN 1 AND 7", name=op.f("ck_waitlist_entries_seats_range")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_waitlist_entries_booking_id_bookings"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dropoff_place_id"],
            ["places.id"],
            name=op.f("fk_waitlist_entries_dropoff_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"],
            ["users.id"],
            name=op.f("fk_waitlist_entries_passenger_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pickup_place_id"],
            ["places.id"],
            name=op.f("fk_waitlist_entries_pickup_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name=op.f("fk_waitlist_entries_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waitlist_entries")),
    )
    op.create_index(
        op.f("ix_waitlist_entries_passenger_id"), "waitlist_entries", ["passenger_id"], unique=False
    )
    op.create_index(
        "ix_waitlist_entries_trip_position",
        "waitlist_entries",
        ["trip_id", "position"],
        unique=False,
    )
    op.create_index(
        "uq_waitlist_entries_open",
        "waitlist_entries",
        ["trip_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('waiting', 'offered')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_waitlist_entries_open",
        table_name="waitlist_entries",
        postgresql_where=sa.text("status IN ('waiting', 'offered')"),
    )
    op.drop_index("ix_waitlist_entries_trip_position", table_name="waitlist_entries")
    op.drop_index(op.f("ix_waitlist_entries_passenger_id"), table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
    op.drop_index(
        "uq_cancellation_requests_pending",
        table_name="cancellation_requests",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_table("cancellation_requests")
    op.drop_index(
        "uq_bookings_active_passenger",
        table_name="bookings",
        postgresql_where=sa.text("status IN ('requested', 'accepted', 'cancel_requested')"),
    )
    op.drop_index("ix_bookings_trip_status", table_name="bookings")
    op.drop_index(op.f("ix_bookings_subscription_id"), table_name="bookings")
    op.drop_index("ix_bookings_passenger_pickup", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(
        "uq_series_subscriptions_open",
        table_name="series_subscriptions",
        postgresql_where=sa.text("status IN ('requested', 'active')"),
    )
    op.drop_index("ix_series_subscriptions_passenger", table_name="series_subscriptions")
    op.drop_table("series_subscriptions")
    op.drop_index("ix_suspensions_user_kind", table_name="suspensions")
    op.drop_table("suspensions")
    for name in (
        "waitlist_status",
        "cancel_request_status",
        "booking_status",
        "subscription_status",
        "suspension_kind",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
