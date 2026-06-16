"""SQLAlchemy 2.0 ORM models — the single source of truth for the schema.

Alembic autogenerates migrations from these (ADR-0006). Application code imports
these models for CRUD; the pgvector similarity search and ranking queries stay in
raw SQL where the ORM would only get in the way.

Field choices mirror the German rental domain (Kalt/Warm/Kaution) and the SPEC §7
data model. `warmmiete_eur` is a DB-computed column so it can never drift from its
parts. `is_scam`/`scam_type` are ground-truth labels for evaluation — never exposed
through the API.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listing"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    address: Mapped[str] = mapped_column(Text)
    kiez: Mapped[str] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)

    rooms: Mapped[float] = mapped_column(Numeric(3, 1))
    size_m2: Mapped[int] = mapped_column(Integer)

    kaltmiete_eur: Mapped[int] = mapped_column(Integer)
    nebenkosten_eur: Mapped[int] = mapped_column(Integer, server_default="0")
    # DB-computed: warm = cold + Nebenkosten. Cannot drift from its parts.
    warmmiete_eur: Mapped[int] = mapped_column(
        Integer, Computed("kaltmiete_eur + nebenkosten_eur", persisted=True)
    )
    deposit_eur: Mapped[int | None] = mapped_column(Integer)

    furnished: Mapped[bool] = mapped_column(Boolean, server_default="false")
    available_from: Mapped[date | None] = mapped_column(Date)
    floor: Mapped[int | None] = mapped_column(Integer)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    anmeldung_possible: Mapped[bool] = mapped_column(Boolean, server_default="true")

    contact_name: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    contact_text: Mapped[str] = mapped_column(Text, server_default="")

    photo_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(Text, server_default="synthetic")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Ground-truth labels for the scam-detection eval. NEVER serialized to the API.
    is_scam: Mapped[bool] = mapped_column(Boolean, server_default="false")
    scam_type: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    embedding: Mapped[ListingEmbedding | None] = relationship(
        back_populates="listing", uselist=False, cascade="all, delete-orphan"
    )
    risk: Mapped[RiskAssessment | None] = relationship(
        back_populates="listing", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_listing_kiez", "kiez"),
        Index("idx_listing_warm", "warmmiete_eur"),
        Index("idx_listing_rooms", "rooms"),
        Index("idx_listing_photo_set", "photo_set_id"),
    )


class Photo(Base):
    """A photo belongs to a *set*, not a listing — multiple listings can reference
    the same photo_set_id, which is how reused-photo scams are modeled. Cross-set
    near-duplicates are caught via phash (F7)."""

    __tablename__ = "photo"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    photo_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source_url: Mapped[str] = mapped_column(Text)  # hotlinked Pexels CDN URL (ADR-0003)
    room_type: Mapped[str] = mapped_column(Text)  # living_room|bedroom|kitchen|bathroom|exterior
    position: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    phash: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_photo_set", "photo_set_id"),
        Index("idx_photo_phash", "phash"),
    )


class ListingEmbedding(Base):
    """One semantic-search vector per listing. 768 dims = Gemini text-embedding-004."""

    __tablename__ = "listing_embedding"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    content: Mapped[str | None] = mapped_column(Text)  # the embedded text, for debugging
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    listing: Mapped[Listing] = relationship(back_populates="embedding")

    __table_args__ = (
        # HNSW cosine ANN index — strong recall, no training step.
        Index(
            "idx_listing_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class NeighborhoodCache(Base):
    """Cached OSM Overpass POI counts + a qualitative summary (F6)."""

    __tablename__ = "neighborhood_cache"

    location_key: Mapped[str] = mapped_column(Text, primary_key=True)
    poi_counts: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    summary: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CommuteCache(Base):
    """Cached BVG/VBB door-to-door transit times, keyed by origin+destination (F5)."""

    __tablename__ = "commute_cache"

    origin_key: Mapped[str] = mapped_column(Text, primary_key=True)
    dest_key: Mapped[str] = mapped_column(Text, primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer)
    changes: Mapped[int] = mapped_column(Integer, server_default="0")
    walk_minutes: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskAssessment(Base):
    """Current scam/risk result per listing (F7). `signals` stores each contributing
    signal with its evidence so the UI can explain *why* a listing was flagged."""

    __tablename__ = "risk_assessment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing.id", ondelete="CASCADE"), unique=True
    )
    score: Mapped[int] = mapped_column(Integer)
    band: Mapped[str] = mapped_column(Text)
    signals: Mapped[list] = mapped_column(JSONB, server_default="[]")
    engine_version: Mapped[str] = mapped_column(Text, server_default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    listing: Mapped[Listing] = relationship(back_populates="risk")

    __table_args__ = (
        CheckConstraint("score between 0 and 100", name="ck_risk_score_range"),
        CheckConstraint("band in ('low', 'caution', 'high')", name="ck_risk_band"),
        Index("idx_risk_band", "band"),
    )
