"""Commute eval (ADR-0009): offline estimates vs. live BVG/VBB journeys.

For a deterministic sample of listings × common work locations, asks the live
transport.rest API for the first journey departing next weekday at 08:00 (the peak the
network model represents), then scores both offline methods against it:

  * distance — straight-line estimate (enrich/commute_estimate.py, ADR-0008)
  * network  — route-based estimate over the VBB peak network (needs `make demo-stops`)

Reports MAE, bias, share within 5/10 minutes, how often the faster listing also *looks*
faster (order agreement, per destination), and changes accuracy for the network model.
Writes JSON + Markdown to evals/results/.

Live answers are cached in evals/results/commute_live.json, so a re-run only queries
missing pairs, and `--offline` re-scores from the cache without any network (useful
after tuning the model).

    uv run python -m evals.commute_eval                 # needs internet
    uv run python -m evals.commute_eval --offline       # re-score cached live journeys
    uv run python -m evals.commute_eval --listings 30   # bigger sample
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from core.logging import configure_logging, get_logger
from data.synthetic import generate_listings
from enrich import commute as live
from enrich.commute_estimate import estimate_commute
from enrich.commute_parse import parse_journey
from enrich.transit_network import get_network
from evals.commute_metrics import changes_accuracy, error_stats, order_agreement, verdict

configure_logging()
logger = get_logger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
LIVE_CACHE = RESULTS_DIR / "commute_live.json"

DESTINATIONS = [
    "Alexanderplatz",
    "Hauptbahnhof",
    "Potsdamer Platz",
    "Friedrichstraße",
    "Zoologischer Garten",
    "Warschauer Straße",
    "Südkreuz",
    "Adlershof",
]
API_PAUSE_S = 0.7  # transport.rest allows ~100 requests/minute


def next_weekday_peak(now: datetime | None = None) -> str:
    """Next Tue/Wed/Thu at 08:00 Berlin time, ISO 8601 (matches the network's peak)."""
    berlin = ZoneInfo("Europe/Berlin")
    now = now or datetime.now(berlin)
    day = now.date() + timedelta(days=1)
    while day.weekday() not in (1, 2, 3):
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, 8, 0, tzinfo=berlin).isoformat()


def sample_listings(n: int):
    """Every k-th seeded listing (by id), so the sample spreads across Kieze."""
    listings = sorted(generate_listings(100, seed=42), key=lambda x: str(x.id))
    step = max(1, len(listings) // n)
    return listings[::step][:n]


def _load_cache() -> dict:
    return json.loads(LIVE_CACHE.read_text()) if LIVE_CACHE.exists() else {}


def _save_cache(cache: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")


def collect_live(listings, destinations, *, offline: bool, departure: str) -> dict:
    """Live journeys per 'listing_id|destination' (cached). Destinations carry coordinates."""
    cache = _load_cache()
    cache.setdefault("destinations", {})
    cache.setdefault("journeys", {})
    if offline:
        return cache
    for name in destinations:
        if name in cache["destinations"]:
            continue
        stop = live.resolve_location(name)
        coords = live._stop_coords(stop)
        if not stop or "id" not in stop or coords is None:
            logger.warning("could not resolve %r; skipping", name)
            continue
        cache["destinations"][name] = {"id": stop["id"], "name": stop.get("name"), "coords": coords}
        _save_cache(cache)
        time.sleep(API_PAUSE_S)
    for listing in listings:
        for name, dest in cache["destinations"].items():
            if name not in destinations:
                continue
            key = f"{listing.id}|{name}"
            if key in cache["journeys"]:
                continue
            try:
                journey = live.fetch_first_journey(
                    listing.lat, listing.lng, dest["id"], departure=departure
                )
                result = parse_journey(journey) if journey else None
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("journey failed for %s: %s", key, exc)
                result = None
            cache["journeys"][key] = (
                {"minutes": result.minutes, "changes": result.changes} if result else None
            )
            _save_cache(cache)
            time.sleep(API_PAUSE_S)
    return cache


def score(listings, destinations, cache: dict, network=None) -> dict:
    rows = []
    for listing in listings:
        for name in destinations:
            dest = cache["destinations"].get(name)
            actual = cache["journeys"].get(f"{listing.id}|{name}")
            if not dest or not actual:
                continue
            dlat, dlng = dest["coords"]
            row = {
                "listing": listing.title,
                "kiez": listing.kiez,
                "destination": name,
                "live": actual["minutes"],
                "live_changes": actual["changes"],
                "distance": estimate_commute(listing.lat, listing.lng, dlat, dlng).minutes,
            }
            if network is not None:
                r = network.route(listing.lat, listing.lng, dlat, dlng)
                row["network"] = max(1, round(r.minutes))
                row["network_changes"] = r.changes
            rows.append(row)

    methods = ["distance"] + (["network"] if network is not None else [])
    live_minutes = [r["live"] for r in rows]
    summary = {m: error_stats([r[m] for r in rows], live_minutes) for m in methods}
    for m in methods:
        per_dest = [
            order_agreement(
                [r[m] for r in rows if r["destination"] == d],
                [r["live"] for r in rows if r["destination"] == d],
            )
            for d in destinations
        ]
        per_dest = [x for x in per_dest if x is not None]
        summary[m]["order_agreement"] = (
            round(sum(per_dest) / len(per_dest), 3) if per_dest else None
        )
    report = {"pairs": len(rows), "methods": summary, "verdict": verdict(summary), "rows": rows}
    if network is not None:
        report["network_changes"] = changes_accuracy(
            [r["network_changes"] for r in rows], [r["live_changes"] for r in rows]
        )
    return report


def _markdown(report: dict, departure: str) -> str:
    lines = [
        "# Commute eval: offline estimates vs. live BVG/VBB journeys",
        "",
        f"{report['pairs']} listing → destination pairs; live journeys departing {departure}.",
        "",
        "| Method | MAE (min) | Median abs. error | Bias | Within 5 min | Within 10 min"
        " | Order agreement |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, s in report["methods"].items():
        if not s.get("n"):
            continue
        lines.append(
            f"| {m} | {s['mae']} | {s['median_abs_error']} | {s['bias']:+} "
            f"| {s['within_5_min']:.0%} | {s['within_10_min']:.0%} "
            f"| {s['order_agreement'] if s['order_agreement'] is not None else '-'} |"
        )
    if "network_changes" in report and report["network_changes"].get("n"):
        c = report["network_changes"]
        lines += ["", f"Network changes: {c['exact']:.0%} exact, {c['within_1']:.0%} within one."]
    lines += ["", f"**Verdict:** {report['verdict']}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline commute estimates vs. live journeys.")
    parser.add_argument("--listings", type=int, default=15, help="Number of listings to sample")
    parser.add_argument("--offline", action="store_true", help="Score cached live data only")
    args = parser.parse_args()

    listings = sample_listings(args.listings)
    departure = next_weekday_peak()
    cache = collect_live(listings, DESTINATIONS, offline=args.offline, departure=departure)
    network = get_network()
    if network is None:
        print("No VBB network found (run `make demo-stops`): scoring straight-line only.")
    report = score(listings, DESTINATIONS, cache, network)
    if not report["pairs"]:
        raise SystemExit("No live journeys to score. Run without --offline while online.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "commute_eval.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    md = _markdown(report, departure)
    (RESULTS_DIR / "commute_eval.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
