"""The ranking sanity eval is pure/offline, so it runs in CI as a regression guard."""

from evals.ranking_eval import run


def test_all_scenarios_pass():
    summary, rows = run()
    failures = [r["name"] for r in rows if not r["passed"]]
    assert not failures, f"ranking scenarios failed: {failures}"
    assert summary["pass_rate"] == 1.0
