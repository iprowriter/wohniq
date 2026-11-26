"""berlin open data

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24

Adds the Berlin open-data tables for the rent check, Around this flat and Right now
(ADR-0016), loaded by `make berlin-load`, and listing.year_built for the Mietspiegel
building-age row. Installs PostGIS into Supabase's `extensions` schema first, so its
spatial_ref_sys table stays out of `public`. Additive only: nothing existing is changed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType


class Geography(UserDefinedType):
    """PostGIS geography(<type>, 4326); defined here so the migration never imports models."""

    cache_ok = True

    def __init__(self, geometry_type: str = "Point"):
        self.geometry_type = geometry_type

    def get_col_spec(self, **kw) -> str:
        return f"geography({self.geometry_type},4326)"


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions")
    op.create_table(
        "berlin_accident",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("category", sa.SmallInteger(), nullable=False),
        sa.Column("bike", sa.Boolean(), nullable=False),
        sa.Column("pedestrian", sa.Boolean(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_accident_geog",
        "berlin_accident",
        ["geog"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "berlin_address",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("street", sa.Text(), nullable=False),
        sa.Column("house_number", sa.Text(), nullable=False),
        sa.Column("postcode", sa.Text(), nullable=False),
        sa.Column("district", sa.Text(), nullable=False),
        sa.Column("location_class", sa.Text(), nullable=False),
        sa.Column("east", sa.Boolean(), nullable=False),
        sa.Column("plr_id", sa.Text(), nullable=False),
        sa.Column("search_key", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.CheckConstraint(
            "location_class in ('simple', 'medium', 'good')", name="ck_berlin_address_class"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_address_geog", "berlin_address", ["geog"], unique=False, postgresql_using="gist"
    )
    op.create_index(
        "idx_berlin_address_search_key",
        "berlin_address",
        ["search_key"],
        unique=False,
        postgresql_ops={"search_key": "text_pattern_ops"},
    )
    op.create_table(
        "berlin_air_station",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("station_type", sa.Text(), nullable=False),
        sa.Column("lqi", sa.SmallInteger(), nullable=True),
        sa.Column("measured_at", sa.Text(), nullable=True),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "berlin_dataset",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "content", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "berlin_district_region",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("district", sa.Text(), nullable=False),
        sa.Column("crime_rate", sa.Double(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "berlin_kita",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("places", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_kita_geog", "berlin_kita", ["geog"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "berlin_park",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("area_m2", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("MultiPolygon"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_park_geog", "berlin_park", ["geog"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "berlin_planning_area",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bzr_id", sa.Text(), nullable=False),
        sa.Column("bzr_name", sa.Text(), nullable=False),
        sa.Column("district", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column(
            "stats", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("geog", Geography("MultiPolygon"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_planning_area_geog",
        "berlin_planning_area",
        ["geog"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "berlin_playground",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_playground_geog",
        "berlin_playground",
        ["geog"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "berlin_rent_row",
        sa.Column("row", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("size_min", sa.SmallInteger(), nullable=False),
        sa.Column("size_max", sa.SmallInteger(), nullable=True),
        sa.Column("low", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("mean", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("high", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("row"),
    )
    op.create_table(
        "berlin_school",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("school_type", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_school_geog", "berlin_school", ["geog"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "berlin_stop",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("modes", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("geog", Geography("Point"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_berlin_stop_geog", "berlin_stop", ["geog"], unique=False, postgresql_using="gist"
    )
    op.add_column("listing", sa.Column("year_built", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    # PostGIS itself is left installed: other objects may use it.
    op.drop_column("listing", "year_built")
    op.drop_index("idx_berlin_stop_geog", table_name="berlin_stop", postgresql_using="gist")
    op.drop_table("berlin_stop")
    op.drop_index("idx_berlin_school_geog", table_name="berlin_school", postgresql_using="gist")
    op.drop_table("berlin_school")
    op.drop_table("berlin_rent_row")
    op.drop_index(
        "idx_berlin_playground_geog", table_name="berlin_playground", postgresql_using="gist"
    )
    op.drop_table("berlin_playground")
    op.drop_index(
        "idx_berlin_planning_area_geog", table_name="berlin_planning_area", postgresql_using="gist"
    )
    op.drop_table("berlin_planning_area")
    op.drop_index("idx_berlin_park_geog", table_name="berlin_park", postgresql_using="gist")
    op.drop_table("berlin_park")
    op.drop_index("idx_berlin_kita_geog", table_name="berlin_kita", postgresql_using="gist")
    op.drop_table("berlin_kita")
    op.drop_table("berlin_district_region")
    op.drop_table("berlin_dataset")
    op.drop_table("berlin_air_station")
    op.drop_index(
        "idx_berlin_address_search_key",
        table_name="berlin_address",
        postgresql_ops={"search_key": "text_pattern_ops"},
    )
    op.drop_index("idx_berlin_address_geog", table_name="berlin_address", postgresql_using="gist")
    op.drop_table("berlin_address")
    op.drop_index("idx_berlin_accident_geog", table_name="berlin_accident", postgresql_using="gist")
    op.drop_table("berlin_accident")
