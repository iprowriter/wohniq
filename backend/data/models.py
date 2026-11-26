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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


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
    # Year the building was first ready for occupancy (Bezugsfertigkeit): picks the
    # Mietspiegel building-age row for the rent check (ADR-0016).
    year_built: Mapped[int | None] = mapped_column(SmallInteger)
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
    """One semantic-search vector per listing. 768 dims = Gemini gemini-embedding-001
    truncated (Matryoshka) from its native 3072."""

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
    # Each POI: {category, name, lat, lng} — retained so a future map view needs no re-fetch.
    pois: Mapped[list] = mapped_column(JSONB, server_default="[]")
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


# --- Berlin open data (rent check, Around this flat, Right now; ADR-0016) ----------------
# Loaded by `make berlin-load` from the `make berlin-data` build. Read with raw SQL in
# berlin/postgres.py; these models exist so Alembic owns the schema.


class Geography(UserDefinedType):
    """PostGIS `geography(<type>, 4326)` (PostGIS lives in the `extensions` schema)."""

    cache_ok = True

    def __init__(self, geometry_type: str = "Point"):
        self.geometry_type = geometry_type

    def get_col_spec(self, **kw) -> str:
        return f"geography({self.geometry_type},4326)"


def _gist(table: str) -> Index:
    return Index(f"idx_{table}_geog", "geog", postgresql_using="gist")


class BerlinAddress(Base):
    """The 400,505 residential addresses of the Mietspiegel Wohnlagenverzeichnis 2026."""

    __tablename__ = "berlin_address"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    street: Mapped[str] = mapped_column(Text)
    house_number: Mapped[str] = mapped_column(Text)
    postcode: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(Text)
    location_class: Mapped[str] = mapped_column(Text)
    east: Mapped[bool] = mapped_column(Boolean)
    plr_id: Mapped[str] = mapped_column(Text)
    search_key: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (
        Index(
            "idx_berlin_address_search_key",
            "search_key",
            postgresql_ops={"search_key": "text_pattern_ops"},
        ),
        _gist("berlin_address"),
        CheckConstraint(
            "location_class in ('simple', 'medium', 'good')", name="ck_berlin_address_class"
        ),
    )


class BerlinPlanningArea(Base):
    """LOR 2021 planning areas (542), with each measure's typical value in `stats`."""

    __tablename__ = "berlin_planning_area"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    bzr_id: Mapped[str] = mapped_column(Text)
    bzr_name: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    stats: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    geog = mapped_column(Geography("MultiPolygon"))

    __table_args__ = (_gist("berlin_planning_area"),)


class BerlinDistrictRegion(Base):
    """LOR 2021 district regions (143), with neighbourhood offences per 100,000 residents."""

    __tablename__ = "berlin_district_region"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(Text)
    crime_rate: Mapped[float | None] = mapped_column(Double)


class BerlinStop(Base):
    __tablename__ = "berlin_stop"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    modes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (_gist("berlin_stop"),)


class BerlinSchool(Base):
    __tablename__ = "berlin_school"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # primary|secondary|vocational|special|adult
    school_type: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (_gist("berlin_school"),)


class BerlinKita(Base):
    __tablename__ = "berlin_kita"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    places: Mapped[int | None] = mapped_column(Integer)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (_gist("berlin_kita"),)


class BerlinPark(Base):
    """Public green spaces of 1 ha or more (outlines simplified to 3 m)."""

    __tablename__ = "berlin_park"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    area_m2: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("MultiPolygon"))

    __table_args__ = (_gist("berlin_park"),)


class BerlinPlayground(Base):
    __tablename__ = "berlin_playground"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (_gist("berlin_playground"),)


class BerlinAccident(Base):
    """Road accidents with personal injury, 2025 (Unfallatlas)."""

    __tablename__ = "berlin_accident"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    category: Mapped[int] = mapped_column(SmallInteger)  # 1 killed, 2 serious, 3 light
    bike: Mapped[bool] = mapped_column(Boolean)
    pedestrian: Mapped[bool] = mapped_column(Boolean)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))

    __table_args__ = (_gist("berlin_accident"),)


class BerlinAirStation(Base):
    __tablename__ = "berlin_air_station"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    station_type: Mapped[str] = mapped_column(Text)
    lqi: Mapped[int | None] = mapped_column(SmallInteger)
    measured_at: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)
    geog = mapped_column(Geography("Point"))


class BerlinRentRow(Base):
    """Berliner Mietspiegeltabelle 2026: €/m² net cold by location, building age, size."""

    __tablename__ = "berlin_rent_row"

    row: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    location: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    size_min: Mapped[int] = mapped_column(SmallInteger)
    size_max: Mapped[int | None] = mapped_column(SmallInteger)
    low: Mapped[float] = mapped_column(Numeric(5, 2))
    mean: Mapped[float] = mapped_column(Numeric(5, 2))
    high: Mapped[float] = mapped_column(Numeric(5, 2))


class BerlinDataset(Base):
    """Small JSON documents of the loaded build, keyed by name: the build manifest,
    Mietspiegel periods and checklist, air snapshot time, Berlin-wide crime rate."""

    __tablename__ = "berlin_dataset"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
