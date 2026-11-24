"""The browser rent check is tested against these vectors; they must match berlin/rent.py."""

from data.berlin.export_rent_vectors import OUT, build, dump


def test_rent_vectors_fixture_is_up_to_date():
    assert OUT.is_file(), "run: uv run python -m data.berlin.export_rent_vectors"
    assert OUT.read_text(encoding="utf-8") == dump(build()), (
        "frontend/tests/fixtures/rent-vectors.json is stale: "
        "uv run python -m data.berlin.export_rent_vectors"
    )


def test_vectors_cover_every_verdict():
    verdicts = {v["expected"]["verdict"] for v in build()["vectors"]}
    assert verdicts == {
        "within_limit",
        "above_limit",
        "below_index",
        "new_build",
        "not_covered",
        "unknown",
    }
