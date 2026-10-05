"""Indice geografico de las rutas para la busqueda en metros.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05 04:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ST_DWithin(route::geography, punto, metros) usa este indice; solo viajes programados.
    op.execute(
        "CREATE INDEX ix_trips_route_geography ON trips USING gist ((route::geography)) "
        "WHERE status = 'scheduled' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_trips_route_geography")
