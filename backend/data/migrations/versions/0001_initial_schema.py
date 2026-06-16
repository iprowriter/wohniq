"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-15

Creates the full WohnIQ schema (SPEC §7) plus the pgvector and pgcrypto
extensions. Hand-authored to match data/models.py; subsequent migrations should
be produced with `alembic revision --autogenerate`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.execute("create extension if not exists pgcrypto")

    op.create_table(
        "listing",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("kiez", sa.Text(), nullable=False),
        sa.Column("district", sa.Text(), nullable=True),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("rooms", sa.Numeric(3, 1), nullable=False),
        sa.Column("size_m2", sa.Integer(), nullable=False),
        sa.Column("kaltmiete_eur", sa.Integer(), nullable=False),
        sa.Column("nebenkosten_eur", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "warmmiete_eur",
            sa.Integer(),
            sa.Computed("kaltmiete_eur + nebenkosten_eur", persisted=True),
            nullable=False,
        ),
        sa.Column("deposit_eur", sa.Integer(), nullable=True),
        sa.Column("furnished", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column(
            "anmeldung_possible", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("contact_text", sa.Text(), server_default="", nullable=False),
        sa.Column("photo_set_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.Text(), server_default="synthetic", nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_scam", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("scam_type", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_listing_kiez", "listing", ["kiez"])
    op.create_index("idx_listing_warm", "listing", ["warmmiete_eur"])
    op.create_index("idx_listing_rooms", "listing", ["rooms"])
    op.create_index("idx_listing_photo_set", "listing", ["photo_set_id"])

    op.create_table(
        "photo",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("photo_set_id", sa.UUID(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("room_type", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("phash", sa.Text(), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_photo_set", "photo", ["photo_set_id"])
    op.create_index("idx_photo_phash", "photo", ["phash"])

    op.create_table(
        "listing_embedding",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("listing_id"),
    )
    op.create_index(
        "idx_listing_embedding_hnsw",
        "listing_embedding",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "neighborhood_cache",
        sa.Column("location_key", sa.Text(), nullable=False),
        sa.Column("poi_counts", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("location_key"),
    )

    op.create_table(
        "commute_cache",
        sa.Column("origin_key", sa.Text(), nullable=False),
        sa.Column("dest_key", sa.Text(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("changes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("walk_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("origin_key", "dest_key"),
    )

    op.create_table(
        "risk_assessment",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("signals", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("engine_version", sa.Text(), server_default="v1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score between 0 and 100", name="ck_risk_score_range"),
        sa.CheckConstraint("band in ('low', 'caution', 'high')", name="ck_risk_band"),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id"),
    )
    op.create_index("idx_risk_band", "risk_assessment", ["band"])


def downgrade() -> None:
    op.drop_table("risk_assessment")
    op.drop_table("commute_cache")
    op.drop_table("neighborhood_cache")
    op.drop_index("idx_listing_embedding_hnsw", table_name="listing_embedding")
    op.drop_table("listing_embedding")
    op.drop_table("photo")
    op.drop_table("listing")
