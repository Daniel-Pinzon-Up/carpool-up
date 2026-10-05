"""Viajes, series, paradas y reglas.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05 02:32:07.907100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los tipos enum se crean una sola vez; stop_kind lo usan dos tablas.
ENUMS = {
    "series_status": ("active", "cancelled", "finished"),
    "trip_status": (
        "scheduled",
        "in_progress",
        "completed",
        "cancelled_by_driver",
        "cancelled_pico_placa",
        "not_held",
    ),
    "stop_kind": ("origin", "stop", "destination"),
    "rule_kind": ("women_only", "pets", "luggage", "smoking", "music", "custom"),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "trip_series",
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("semester_id", sa.UUID(), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("departure_time", sa.Time(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("price_per_seat", sa.Integer(), nullable=False),
        sa.Column("status", enum("series_status"), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            "cardinality(weekdays) BETWEEN 1 AND 7 "
            "AND weekdays <@ ARRAY[0,1,2,3,4,5,6]::smallint[]",
            name=op.f("ck_trip_series_weekdays_valid"),
        ),
        sa.CheckConstraint("price_per_seat >= 0", name=op.f("ck_trip_series_price_non_negative")),
        sa.CheckConstraint("seats BETWEEN 1 AND 7", name=op.f("ck_trip_series_seats_range")),
        sa.CheckConstraint("window_end >= window_start", name=op.f("ck_trip_series_window_order")),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["users.id"],
            name=op.f("fk_trip_series_driver_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["semester_id"],
            ["semesters.id"],
            name=op.f("fk_trip_series_semester_id_semesters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name=op.f("fk_trip_series_vehicle_id_vehicles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_series")),
    )
    op.create_index(op.f("ix_trip_series_driver_id"), "trip_series", ["driver_id"], unique=False)
    op.create_table(
        "series_stops",
        sa.Column("series_id", sa.UUID(), nullable=False),
        sa.Column("place_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", enum("stop_kind"), nullable=False),
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
            name=op.f("fk_series_stops_place_id_places"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["trip_series.id"],
            name=op.f("fk_series_stops_series_id_trip_series"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series_stops")),
        sa.UniqueConstraint("series_id", "position", name="uq_series_stops_position"),
    )
    op.create_geospatial_table(
        "trips",
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("series_id", sa.UUID(), nullable=True),
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
        sa.Column("status", enum("trip_status"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            ["series_id"],
            ["trip_series.id"],
            name=op.f("fk_trips_series_id_trip_series"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name=op.f("fk_trips_vehicle_id_vehicles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
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
        "ix_trips_scheduled_departs",
        "trips",
        ["departs_at"],
        unique=False,
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.create_index(op.f("ix_trips_series_id"), "trips", ["series_id"], unique=False)
    op.create_table(
        "trip_rules",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("kind", enum("rule_kind"), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
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
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_rules_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_rules")),
        sa.UniqueConstraint("trip_id", "kind", name="uq_trip_rules_kind"),
    )
    op.create_table(
        "trip_stops",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("place_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", enum("stop_kind"), nullable=False),
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
    op.drop_table("trip_rules")
    op.drop_index(op.f("ix_trips_series_id"), table_name="trips")
    op.drop_index(
        "ix_trips_scheduled_departs",
        table_name="trips",
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.drop_index("ix_trips_driver_departs", table_name="trips")
    op.drop_geospatial_index(
        "idx_trips_route", table_name="trips", postgresql_using="gist", column_name="route"
    )
    op.drop_geospatial_table("trips")
    op.drop_table("series_stops")
    op.drop_index(op.f("ix_trip_series_driver_id"), table_name="trip_series")
    op.drop_table("trip_series")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
