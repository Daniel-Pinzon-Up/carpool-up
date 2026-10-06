"""Calificaciones por criterio y resumen de estadisticas por usuario.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06 14:59:05.507629
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_stats",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("rating_avg", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("trips_as_driver", sa.Integer(), nullable=False),
        sa.Column("trips_as_passenger", sa.Integer(), nullable=False),
        sa.Column("driver_cancellations", sa.Integer(), nullable=False),
        sa.Column("passenger_no_shows", sa.Integer(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_stats_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_stats")),
    )
    op.create_table(
        "ratings",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("target_role", sa.Text(), nullable=False),
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
        "rating_scores",
        sa.Column("rating_id", sa.UUID(), nullable=False),
        sa.Column("criterion", sa.Text(), nullable=False),
        sa.Column("stars", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name=op.f("ck_rating_scores_stars_range")),
        sa.ForeignKeyConstraint(
            ["rating_id"],
            ["ratings.id"],
            name=op.f("fk_rating_scores_rating_id_ratings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("rating_id", "criterion", name=op.f("pk_rating_scores")),
    )
    op.add_column(
        "trips", sa.Column("rating_reminded_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Resumen inicial de quienes ya tienen viajes o reservas (aun no hay calificaciones).
    op.execute(
        """
        INSERT INTO user_stats (
            user_id, rating_count, trips_as_driver, trips_as_passenger,
            driver_cancellations, passenger_no_shows, criteria, updated_at
        )
        SELECT
            u.id,
            0,
            (SELECT count(*) FROM trips t
             WHERE t.driver_id = u.id AND t.status = 'completed'),
            (SELECT count(*) FROM bookings b
             WHERE b.passenger_id = u.id AND b.status = 'completed'),
            (SELECT count(*) FROM trips t
             WHERE t.driver_id = u.id AND t.status = 'cancelled_by_driver'
               AND t.deleted_at IS NULL),
            (SELECT count(*) FROM bookings b
             WHERE b.passenger_id = u.id AND b.status = 'no_show'),
            '{}'::jsonb,
            now()
        FROM users u
        WHERE EXISTS (SELECT 1 FROM trips t WHERE t.driver_id = u.id)
           OR EXISTS (SELECT 1 FROM bookings b WHERE b.passenger_id = u.id)
        """
    )


def downgrade() -> None:
    op.drop_column("trips", "rating_reminded_at")
    op.drop_table("rating_scores")
    op.drop_index("ix_ratings_target_created", table_name="ratings")
    op.drop_table("ratings")
    op.drop_table("user_stats")
