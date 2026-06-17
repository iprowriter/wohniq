"""Ranking sanity scenarios (pure data).

Each scenario hands the ranker a small basket of candidate listings plus the
criteria, and names the listing that *should* come out on top. These are designed
so one candidate is the clear right answer — so they double as a regression guard:
if someone retunes the weights and breaks sensible ordering, the eval fails.

Unlike the parser/scam evals, this is fully deterministic and offline, so it also
runs in CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from search.ranking import RankCriteria, RankingInput


@dataclass(frozen=True)
class RankingScenario:
    name: str
    criteria: RankCriteria
    candidates: tuple[RankingInput, ...]
    expected_top_id: str
    top_k: int = 1  # expected listing must land within the top_k


SCENARIOS: list[RankingScenario] = [
    RankingScenario(
        name="value within budget beats pricey and irrelevant",
        criteria=RankCriteria(max_warm_rent=1500),
        candidates=(
            RankingInput(warmmiete_eur=950, distance=0.25, listing_id="value"),
            RankingInput(warmmiete_eur=1480, distance=0.20, listing_id="pricey"),
            RankingInput(warmmiete_eur=1000, distance=0.60, listing_id="irrelevant"),
        ),
        expected_top_id="value",
    ),
    RankingScenario(
        name="shortest commute wins when commute is the differentiator",
        criteria=RankCriteria(),
        candidates=(
            RankingInput(warmmiete_eur=1200, distance=0.30, commute_minutes=10, listing_id="near"),
            RankingInput(warmmiete_eur=1200, distance=0.30, commute_minutes=35, listing_id="mid"),
            RankingInput(warmmiete_eur=1200, distance=0.30, commute_minutes=55, listing_id="far"),
        ),
        expected_top_id="near",
    ),
    RankingScenario(
        name="quiet Kiez wins for a quiet-seeker",
        criteria=RankCriteria(quiet_priority=True),
        candidates=(
            RankingInput(warmmiete_eur=1200, distance=0.30, nightlife="low", listing_id="calm"),
            RankingInput(warmmiete_eur=1200, distance=0.30, nightlife="medium", listing_id="mixed"),
            RankingInput(warmmiete_eur=1200, distance=0.30, nightlife="high", listing_id="lively"),
        ),
        expected_top_id="calm",
    ),
    RankingScenario(
        name="more matched amenities wins",
        criteria=RankCriteria(desired_amenities=("cafes", "parks")),
        candidates=(
            RankingInput(
                warmmiete_eur=1200, distance=0.30,
                available_amenities={"cafes", "parks"}, listing_id="full",
            ),
            RankingInput(
                warmmiete_eur=1200, distance=0.30,
                available_amenities={"cafes"}, listing_id="half",
            ),
            RankingInput(
                warmmiete_eur=1200, distance=0.30,
                available_amenities=set(), listing_id="none",
            ),
        ),
        expected_top_id="full",
    ),
    RankingScenario(
        name="all-rounder wins on combined factors",
        criteria=RankCriteria(
            max_warm_rent=1600, quiet_priority=True, desired_amenities=("cafes",)
        ),
        candidates=(
            RankingInput(
                warmmiete_eur=1300, distance=0.20, nightlife="low",
                available_amenities={"cafes"}, commute_minutes=15, listing_id="ideal",
            ),
            RankingInput(
                warmmiete_eur=1550, distance=0.40, nightlife="high",
                available_amenities=set(), commute_minutes=40, listing_id="compromise",
            ),
        ),
        expected_top_id="ideal",
    ),
]
