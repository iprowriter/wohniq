"""neighborhood pois column

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17

Adds neighborhood_cache.pois (jsonb) so each cached location keeps the individual
amenities (category, name, lat, lng), enabling a future map view without re-querying
Overpass.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "neighborhood_cache",
        sa.Column("pois", postgresql.JSONB(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("neighborhood_cache", "pois")
