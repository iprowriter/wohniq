"""`BerlinData` over Supabase/PostGIS (live mode). Raw SQL, per ADR-0006's rule of thumb.

Every distance is `ST_Distance(..., false)` / `ST_DWithin(..., false)`: great-circle metres
on PostGIS's sphere, the same measure as berlin/geo.py, so this and `LocalBerlinData` give
the same answers (tests/test_berlin_parity.py). Ties are broken by id, like the local side.
"""

from __future__ import annotations

from functools import cached_property

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from berlin.repository import POINT_LAYERS, Address, AirStation, Area, Park, Stop
from berlin.text import search_key

_PT = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"

_LAYER_SQL = {
    "schools": "SELECT id, name, kind, school_type, lat, lng, {d} AS distance_m FROM berlin_school",
    "kitas": "SELECT id, name, places, lat, lng, {d} AS distance_m FROM berlin_kita",
    "playgrounds": "SELECT id, name, lat, lng, {d} AS distance_m FROM berlin_playground",
    "accidents": (
        "SELECT id, category, bike, pedestrian, lat, lng, {d} AS distance_m FROM berlin_accident"
    ),
}
_ADDRESS_COLS = (
    "id, street, house_number, postcode, district, location_class, east, plr_id, lat, lng"
)


def _address(row) -> Address:
    return Address(
        row.id,
        row.street,
        row.house_number,
        row.postcode,
        row.district,
        row.location_class,
        row.east,
        row.plr_id,
        row.lat,
        row.lng,
    )


class PostgresBerlinData:
    remote = True  # berlin/measures.py runs a point's queries concurrently

    def __init__(self, engine: Engine):
        self.engine = engine
        self._documents: dict[str, object] = {}

    def _run(self, fn):
        # One retry: a pooled connection Supabase closed while idle fails once, then works.
        try:
            with self.engine.connect() as c:
                return fn(c)
        except (OperationalError, DBAPIError) as exc:
            if not getattr(exc, "connection_invalidated", False) and not isinstance(
                exc, OperationalError
            ):
                raise
            with self.engine.connect() as c:
                return fn(c)

    def _all(self, sql: str, **params):
        return self._run(lambda c: c.execute(text(sql), params).all())

    def _document(self, name: str):
        # The documents only change with `make berlin-load`; restart the API after a load.
        if name not in self._documents:
            rows = self._all("SELECT content FROM berlin_dataset WHERE name = :n", n=name)
            self._documents[name] = rows[0].content if rows else None
        return self._documents[name]

    # --- addresses ----------------------------------------------------------------------

    def search_addresses(self, query: str, limit: int = 10) -> list[Address]:
        prefix = search_key(query)
        if len(prefix) < 2:
            return []
        rows = self._all(
            f"SELECT {_ADDRESS_COLS} FROM berlin_address WHERE search_key LIKE :p "
            "ORDER BY id LIMIT :limit",
            p=prefix + "%",  # keys are [a-z0-9 ] only, so no LIKE escaping is needed
            limit=limit,
        )
        return [_address(r) for r in rows]

    def address(self, address_id: int) -> Address | None:
        rows = self._all(f"SELECT {_ADDRESS_COLS} FROM berlin_address WHERE id = :i", i=address_id)
        return _address(rows[0]) if rows else None

    def nearest_address(
        self, lat: float, lng: float, district: str | None = None
    ) -> Address | None:
        radius = 100.0
        district_sql = "AND district = :district" if district is not None else ""
        while radius <= 20_000:
            rows = self._all(
                f"SELECT {_ADDRESS_COLS}, ST_Distance(geog, {_PT}, false) AS d "
                f"FROM berlin_address WHERE ST_DWithin(geog, {_PT}, :r, false) {district_sql} "
                "ORDER BY d, id LIMIT 1",
                lat=lat,
                lng=lng,
                r=radius,
                district=district,
            )
            if rows:
                return _address(rows[0])
            radius *= 2
        return None

    def location_class_share(self, lat: float, lng: float, radius_m: float) -> dict[str, float]:
        rows = self._all(
            "SELECT location_class, count(*) AS n FROM berlin_address "
            f"WHERE ST_DWithin(geog, {_PT}, :r, false) GROUP BY location_class",
            lat=lat,
            lng=lng,
            r=radius_m,
        )
        total = sum(r.n for r in rows)
        return {r.location_class: r.n / total for r in rows} if total else {}

    # --- areas --------------------------------------------------------------------------

    def area_at(self, lat: float, lng: float) -> Area | None:
        rows = self._all(
            "SELECT id, name, bzr_id, bzr_name, district FROM berlin_planning_area "
            f"WHERE ST_Covers(geog, {_PT}) ORDER BY id LIMIT 1",
            lat=lat,
            lng=lng,
        )
        if not rows:
            return None
        r = rows[0]
        return Area(r.id, r.name, r.bzr_id, r.bzr_name, r.district)

    def crime(self, bzr_id: str) -> float | None:
        return self.crime_rates().get(bzr_id)

    def crime_rates(self) -> dict[str, float]:
        return self._crime_rates

    @cached_property
    def _crime_rates(self) -> dict[str, float]:
        rows = self._all("SELECT id, crime_rate FROM berlin_district_region")
        return {r.id: float(r.crime_rate) for r in rows if r.crime_rate is not None}

    def berlin_crime_rate(self) -> float:
        return float(self._document("crime")["berlin_rate"])

    def area_stats(self) -> dict[str, dict[str, float]]:
        return self._area_stats

    @cached_property
    def _area_stats(self) -> dict[str, dict[str, float]]:
        return {r.id: r.stats for r in self._all("SELECT id, stats FROM berlin_planning_area")}

    # --- around a point -----------------------------------------------------------------

    def nearest_stops(
        self, lat: float, lng: float, limit: int = 6, modes: frozenset[str] | None = None
    ) -> list[Stop]:
        where = "WHERE modes && :modes" if modes else ""
        sql = text(
            f"SELECT id, name, modes, lat, lng, ST_Distance(geog, {_PT}, false) AS d "
            f'FROM berlin_stop {where} ORDER BY d, id COLLATE "C" LIMIT :limit'
        )
        params: dict = {"lat": lat, "lng": lng, "limit": limit}
        if modes:
            sql = sql.bindparams(bindparam("modes"))
            params["modes"] = sorted(modes)
        rows = self._run(lambda c: c.execute(sql, params).all())
        return [Stop(r.id, r.name, tuple(r.modes), r.lat, r.lng, float(r.d)) for r in rows]

    def within(self, layer: str, lat: float, lng: float, radius_m: float) -> list[dict]:
        if layer not in POINT_LAYERS:
            raise ValueError(f"unknown layer {layer!r}")
        d = f"ST_Distance(geog, {_PT}, false)"
        sql = _LAYER_SQL[layer].format(d=d)
        rows = self._all(
            f"{sql} WHERE ST_DWithin(geog, {_PT}, :r, false) ORDER BY distance_m, id",
            lat=lat,
            lng=lng,
            r=radius_m,
        )
        out = []
        for r in rows:
            row = dict(r._mapping)
            row.pop("id")
            row["distance_m"] = float(row["distance_m"])
            out.append(row)
        return out

    def nearest_park(self, lat: float, lng: float) -> Park | None:
        for radius in (2_000.0, None):
            near = f"WHERE ST_DWithin(geog, {_PT}, :r, false)" if radius else ""
            rows = self._all(
                f"SELECT name, area_m2, lat, lng, ST_Distance(geog, {_PT}, false) AS d "
                f"FROM berlin_park {near} ORDER BY d, id LIMIT 1",
                lat=lat,
                lng=lng,
                r=radius,
            )
            if rows:
                r = rows[0]
                return Park(r.name, r.area_m2, float(r.d), r.lat, r.lng)
        return None

    def nearest_air_station(self, lat: float, lng: float) -> AirStation | None:
        rows = self._all(
            "SELECT code, name, station_type, lqi, measured_at, lat, lng, "
            f"ST_Distance(geog, {_PT}, false) AS d FROM berlin_air_station "
            'ORDER BY d, code COLLATE "C" LIMIT 1',
            lat=lat,
            lng=lng,
        )
        if not rows:
            return None
        r = rows[0]
        return AirStation(
            r.code, r.name, r.station_type, r.lqi, r.measured_at, float(r.d), r.lat, r.lng
        )

    # --- map layers (results map: Transit, Green) -----------------------------------------

    _BOX = "ST_MakeEnvelope(:west, :south, :east, :north, 4326)"

    def stops_in_bbox(
        self, south: float, west: float, north: float, east: float, limit: int = 400
    ) -> list[Stop]:
        rows = self._all(
            "SELECT id, name, modes, lat, lng FROM berlin_stop "
            "WHERE lat BETWEEN :south AND :north AND lng BETWEEN :west AND :east "
            'ORDER BY id COLLATE "C" LIMIT :limit',
            south=south,
            west=west,
            north=north,
            east=east,
            limit=limit,
        )
        return [Stop(r.id, r.name, tuple(r.modes), r.lat, r.lng, 0.0) for r in rows]

    def parks_in_bbox(
        self, south: float, west: float, north: float, east: float, limit: int = 300
    ) -> list[dict]:
        import json

        rows = self._all(
            "SELECT id, name, area_m2, ST_AsGeoJSON(geog::geometry, 5) AS g FROM berlin_park "
            f"WHERE ST_Intersects(geog, {self._BOX}::geography) "
            "ORDER BY area_m2 DESC, id LIMIT :limit",
            south=south,
            west=west,
            north=north,
            east=east,
            limit=limit,
        )
        out = []
        for r in sorted(rows, key=lambda r: r.id):
            g = json.loads(r.g)
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            out.append({"name": r.name, "area_m2": r.area_m2, "polygons": polys})
        return out

    # --- rent index ---------------------------------------------------------------------

    def rent_rows(self) -> list[dict]:
        return self._rent_rows

    @cached_property
    def _rent_rows(self) -> list[dict]:
        rows = self._all(
            "SELECT row, location, period, size_min, size_max, low, mean, high "
            "FROM berlin_rent_row ORDER BY row"
        )
        return [
            {**r._mapping, "low": float(r.low), "mean": float(r.mean), "high": float(r.high)}
            for r in rows
        ]

    def rent_periods(self) -> dict[str, dict]:
        return self._document("rent_periods") or {}

    def checklist(self) -> list[dict]:
        return self._document("checklist") or []

    def manifest(self) -> dict:
        return self._document("manifest") or {}
