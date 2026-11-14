"""The Berlin Neighbourhoods eval is pure/offline, so it runs in CI as a regression guard."""

from evals.neighborhoods_eval import run


def test_all_neighborhood_checks_pass():
    summary, rows = run()
    failures = [
        f"{r['name']}: {r['detail']}" for r in rows if r["kind"] != "known gap" and not r["passed"]
    ]
    assert not failures, f"neighbourhoods eval failed: {failures}"
    assert summary["ground_truth"] >= 12 and summary["properties"] >= 50


def test_known_gaps_are_reported_with_a_reason_and_none_is_silently_closed():
    summary, rows = run()
    gaps = [r for r in rows if r["kind"] == "known gap"]
    assert all(r["detail"] for r in gaps)
    # A gap that now passes should be promoted to a normal case (as Grunewald was).
    assert not [r["name"] for r in gaps if r["passed"]]
    assert summary["known_gaps"] == [r["name"] for r in gaps]


def test_grunewald_affluence_gap_is_closed_by_land_values():
    _, rows = run()
    row = next(r for r in rows if r["name"].startswith("Affluence: villa districts"))
    assert row["kind"] == "ground truth" and row["passed"]
