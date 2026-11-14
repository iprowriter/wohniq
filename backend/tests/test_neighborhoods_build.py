"""Berlin Neighbourhoods — the bundle build (pure parts; full rebuild if raw files exist)."""

import json

import pytest

from data.neighborhoods import build_index as B
from data.neighborhoods.parse import MssRow


def test_status_by_region_weights_by_residents_and_skips_unindexed():
    rows = [
        MssRow("01100101", "A", 3000, 1),
        MssRow("01100102", "B", 1000, 3),
        MssRow("01100103", "C", 50, None),  # not indexed by the Senate
        MssRow("01100204", "D", 0, 2),  # nobody lives there
    ]
    out = B.status_by_region(rows)
    mean, shares, pop = out["011001"]
    assert mean == pytest.approx(1.5) and pop == 4000
    assert shares == {"high": 75.0, "middle": 0.0, "low": 25.0, "very_low": 0.0}
    assert "011002" not in out


def test_weighted_mean():
    assert B.weighted_mean([(10, 1), (20, 3), (99, 0)]) == pytest.approx(17.5)
    with pytest.raises(B.BuildError):
        B.weighted_mean([(1, 0)])


def test_shipped_bundle_is_deterministic_json():
    text = B.BUNDLE_PATH.read_text(encoding="utf-8")
    assert B.dump(json.loads(text)) == text  # sorted keys, stable formatting


def test_shipped_bundle_records_every_input():
    bundle = json.loads(B.BUNDLE_PATH.read_text(encoding="utf-8"))
    names = " ".join(bundle["inputs"])
    for needle in (
        "fallzahlen",
        "Unfallorte",
        "mss2023",
        "Blickpunkt",
        "gpkg",
        "bzr",
        "regions.json",
        "brw2026",
        "Statistischer Bericht",
    ):
        assert needle in names


def test_shipped_bundle_has_land_values_and_the_berlin_income_figure():
    bundle = json.loads(B.BUNDLE_PATH.read_text(encoding="utf-8"))
    income = bundle["city"]["income_per_taxpayer"]
    assert income["value"] == 45161 and income["year"] == "2022"
    assert income["source_id"] in bundle["sources"]
    for r in bundle["regions"]:
        lv = r["values"]["land_value"]
        assert 0 <= lv["raw"] <= 100 and lv["source_id"] == "bodenrichtwerte_2026"
        assert r["values"]["land_value_eur"]["raw"] > 0
    assert "income" not in bundle["references"]  # not published per neighborhood: unscored


@pytest.mark.slow
@pytest.mark.skipif(
    not any(B.RAW_DIR.glob(B.OSM_GLOB)), reason="raw files not present (see raw/README.md)"
)
def test_rebuild_from_raw_files_reproduces_the_shipped_bundle():
    rebuilt = B.dump(B.build_from_files())
    assert rebuilt == B.BUNDLE_PATH.read_text(encoding="utf-8")
