"""Unit tests for the deterministic ranker (pure, no DB/LLM)."""

from search.ranking import (
    RankCriteria,
    RankingInput,
    rank,
    score_listing,
)


def _factor(result, name):
    return next((f for f in result.factors if f.name == name), None)


def test_relevance_always_active_and_from_distance():
    r = score_listing(RankingInput(warmmiete_eur=1000, distance=0.2), RankCriteria())
    rel = _factor(r, "relevance")
    assert rel is not None
    assert abs(rel.score - 0.8) < 1e-9


def test_budget_factor_rewards_headroom():
    crit = RankCriteria(max_warm_rent=1500)
    at_budget = _factor(score_listing(RankingInput(warmmiete_eur=1500), crit), "budget")
    under = _factor(score_listing(RankingInput(warmmiete_eur=1000), crit), "budget")
    assert abs(at_budget.score - 0.6) < 1e-9  # at budget still fits
    assert under.score > at_budget.score  # comfortably under scores higher


def test_budget_inactive_without_budget():
    r = score_listing(RankingInput(warmmiete_eur=1000), RankCriteria())
    assert _factor(r, "budget") is None


def test_commute_scoring():
    crit = RankCriteria()
    assert _factor(score_listing(RankingInput(warmmiete_eur=1, commute_minutes=0), crit), "commute").score == 1.0
    assert _factor(score_listing(RankingInput(warmmiete_eur=1, commute_minutes=60), crit), "commute").score == 0.0
    mid = _factor(score_listing(RankingInput(warmmiete_eur=1, commute_minutes=30), crit), "commute")
    assert abs(mid.score - 0.5) < 1e-9


def test_quiet_only_when_requested_and_known():
    item = RankingInput(warmmiete_eur=1, nightlife="low")
    assert _factor(score_listing(item, RankCriteria(quiet_priority=False)), "quiet") is None
    q = _factor(score_listing(item, RankCriteria(quiet_priority=True)), "quiet")
    assert q.score == 1.0
    loud = RankingInput(warmmiete_eur=1, nightlife="high")
    assert _factor(score_listing(loud, RankCriteria(quiet_priority=True)), "quiet").score == 0.1


def test_amenities_fraction():
    item = RankingInput(warmmiete_eur=1, available_amenities={"cafes", "parks"})
    crit = RankCriteria(desired_amenities=("cafes", "parks", "gym"))
    a = _factor(score_listing(item, crit), "amenities")
    assert abs(a.score - 2 / 3) < 1e-9


def test_total_is_weighted_average_of_active_factors():
    # Only relevance active → total equals relevance score.
    r = score_listing(RankingInput(warmmiete_eur=1000, distance=0.25), RankCriteria())
    assert abs(r.total - 0.75) < 1e-9


def test_rank_orders_best_first_and_is_deterministic():
    crit = RankCriteria(max_warm_rent=1500)
    items = [
        RankingInput(warmmiete_eur=1450, distance=0.5, listing_id="pricey"),
        RankingInput(warmmiete_eur=900, distance=0.1, listing_id="great"),
    ]
    out1 = rank(items, crit)
    out2 = rank(items, crit)
    assert [i.listing_id for i, _ in out1] == ["great", "pricey"]
    assert [i.listing_id for i, _ in out1] == [i.listing_id for i, _ in out2]  # reproducible
