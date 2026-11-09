"""The Lifestyle Match eval is pure/offline, so it runs in CI as a regression guard."""

from evals.lifestyle_eval import run


def test_all_lifestyle_checks_pass():
    summary, rows = run()
    failures = [f"{r['name']}: {r.get('detail', '')}" for r in rows if not r["passed"]]
    assert not failures, f"lifestyle eval failed: {failures}"
    assert summary["scenarios"] >= 7


def test_definition_of_done_scenario_is_first_and_passes():
    _, rows = run()
    assert "Definition of Done" in rows[0]["name"] and rows[0]["passed"]
