"""Chat: conversaciones grupales y directas, miembros y mensajes.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-05 21:08:53.976251
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column(
            "kind", sa.Enum("trip_group", "direct", name="conversation_kind"), nullable=False
        ),
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("series_id", sa.UUID(), nullable=True),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            "(kind = 'trip_group' AND trip_id IS NOT NULL AND passenger_id IS NULL) OR "
            "(kind = 'direct' AND passenger_id IS NOT NULL "
            "AND (trip_id IS NOT NULL OR series_id IS NOT NULL))",
            name=op.f("ck_conversations_kind_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["users.id"],
            name=op.f("fk_conversations_driver_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"],
            ["users.id"],
            name=op.f("fk_conversations_passenger_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["trip_series.id"],
            name=op.f("fk_conversations_series_id_trip_series"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name=op.f("fk_conversations_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "uq_conversations_direct_series",
        "conversations",
        ["series_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'direct' AND series_id IS NOT NULL"),
    )
    op.create_index(
        "uq_conversations_direct_trip",
        "conversations",
        ["trip_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'direct' AND series_id IS NULL"),
    )
    op.create_index(
        "uq_conversations_trip_group",
        "conversations",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'trip_group'"),
    )
    op.create_table(
        "conversation_members",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_members_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversation_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("conversation_id", "user_id", name=op.f("pk_conversation_members")),
    )
    op.create_index(
        "ix_conversation_members_user", "conversation_members", ["user_id"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
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
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_messages_sender_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_conversation_sent",
        "messages",
        ["conversation_id", "sent_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_sent", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversation_members_user", table_name="conversation_members")
    op.drop_table("conversation_members")
    op.drop_index(
        "uq_conversations_trip_group",
        table_name="conversations",
        postgresql_where=sa.text("kind = 'trip_group'"),
    )
    op.drop_index(
        "uq_conversations_direct_trip",
        table_name="conversations",
        postgresql_where=sa.text("kind = 'direct' AND series_id IS NULL"),
    )
    op.drop_index(
        "uq_conversations_direct_series",
        table_name="conversations",
        postgresql_where=sa.text("kind = 'direct' AND series_id IS NOT NULL"),
    )
    op.drop_table("conversations")
    sa.Enum(name="conversation_kind").drop(op.get_bind(), checkfirst=True)
