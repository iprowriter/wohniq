"""Unit tests for the neighborhood parser (pure, no network)."""

from enrich.neighborhood_parse import (
    build_overpass_query,
    parse_overpass,
    summarize,
)

SAMPLE = {
    "elements": [
        {"type": "node", "lat": 52.540, "lon": 13.420, "tags": {"amenity": "cafe", "name": "Bonanza"}},
        {"type": "node", "lat": 52.541, "lon": 13.421, "tags": {"amenity": "cafe", "name": "The Barn"}},
        {"type": "way", "center": {"lat": 52.539, "lon": 13.419}, "tags": {"leisure": "park", "name": "Helmholtzplatz"}},
        {"type": "node", "lat": 52.538, "lon": 13.418, "tags": {"shop": "supermarket", "name": "REWE"}},
        {"type": "node", "lat": 52.537, "lon": 13.417, "tags": {"amenity": "bar", "name": "Zum Eck"}},
        {"type": "node", "lat": 52.536, "lon": 13.416, "tags": {"office": "lawyer", "name": "Ignore me"}},
    ]
}


def test_query_includes_radius_and_filters():
    q = build_overpass_query(52.54, 13.42, radius=500)
    assert "around:500,52.54,13.42" in q
    assert '"amenity"="cafe"' in q
    assert "out center tags;" in q


def test_parse_counts_and_pois():
    result = parse_overpass(SAMPLE)
    assert result.counts == {"cafes": 2, "parks": 1, "supermarket": 1, "nightlife": 1}
    assert len(result.pois) == 5  # the lawyer office is ignored
    # POIs carry coordinates + name for the future map.
    cafe = next(p for p in result.pois if p["name"] == "Bonanza")
    assert cafe == {"category": "cafes", "name": "Bonanza", "lat": 52.540, "lng": 13.420}
    # park came from a way → coords pulled from `center`.
    park = next(p for p in result.pois if p["category"] == "parks")
    assert park["lat"] == 52.539


def test_available_amenities_are_canonical_only():
    result = parse_overpass(SAMPLE)
    assert result.available_amenities == {"cafes", "parks", "supermarket", "nightlife"}


def test_summary_quiet_vs_lively():
    assert "Quiet" in summarize({"nightlife": 0, "parks": 1})
    assert "lively" in summarize({"nightlife": 8}).lower()
    assert summarize({}) == "Residential"
    assert "cafe-rich" in summarize({"cafes": 6})
