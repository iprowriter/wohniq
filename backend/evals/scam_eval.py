"""Scam-detection eval (T3.5) — the showpiece artifact.

Runs the full detector over every listing in the DB, compares its High-risk verdict
to the hidden ground-truth labels, and reports a confusion matrix, precision/recall/
F1/accuracy, per-scam-type recall, and (if the seed manifest is present) how many
hard-negative listings were correctly cleared. Writes JSON + a Markdown table for the
README.

Hits the DB and (unless --no-llm) Gemini once per listing. Predicted scam = band is
"high".

Usage:
    uv run python -m evals.scam_eval            # full run (rules + photos + LLM text)
    uv run python -m evals.scam_eval --no-llm   # faster: rules + photos only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from core.db import get_sessionmaker
from core.logging import configure_logging, get_logger
from data.models import Listing, Photo
from evals.metrics import confusion, derive_metrics, recall_by_group
from scam.detector import assess_listing
from scam.signals import kiez_price_stats

configure_logging()
logger = get_logger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "generated" / "seed_manifest.json"


def _load_hard_negative_ids() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    manifest = json.loads(MANIFEST_PATH.read_text())
    return {row["id"] for row in manifest if row.get("is_hard_negative")}


def run(*, skip_text: bool = False) -> dict:
    factory = get_sessionmaker()
    with factory() as session:
        listings = list(session.scalars(select(Listing)))
        photos = list(session.scalars(select(Photo)))

    if not listings:
        raise SystemExit("No listings. Seed the DB first (make seed && make seed-images).")

    # Photos grouped by set; each listing's phashes come from its photo_set_id.
    phashes_by_set: dict[str, list[str]] = {}
    for p in photos:
        phashes_by_set.setdefault(str(p.photo_set_id), []).append(p.phash)

    def listing_phashes(listing: Listing) -> list[str]:
        return phashes_by_set.get(str(listing.photo_set_id), [])

    # Corpus for cross-listing photo comparison: (listing_id, phash) for every listing.
    corpus = [(str(x.id), ph) for x in listings for ph in listing_phashes(x)]

    # Robust price stats per Kiez (median resists the cheap scams — that's the point).
    ppm2_by_kiez: dict[str, list[float]] = {}
    for x in listings:
        ppm2_by_kiez.setdefault(x.kiez, []).append(x.kaltmiete_eur / x.size_m2)
    stats_by_kiez = {k: kiez_price_stats(v) for k, v in ppm2_by_kiez.items()}

    y_true: list[bool] = []
    y_pred: list[bool] = []
    scam_types: list[str | None] = []
    rows: list[dict] = []

    for x in listings:
        median, mad = stats_by_kiez[x.kiez]
        result = assess_listing(
            listing_id=str(x.id),
            kiez=x.kiez,
            eur_per_m2=x.kaltmiete_eur / x.size_m2,
            anmeldung_possible=x.anmeldung_possible,
            median_eur_per_m2=median,
            mad_eur_per_m2=mad,
            phashes=listing_phashes(x),
            photo_corpus=corpus,
            contact_text=x.contact_text,
            skip_text=skip_text,
        )
        predicted = result.band == "high"
        y_true.append(bool(x.is_scam))
        y_pred.append(predicted)
        scam_types.append(x.scam_type)
        rows.append(
            {
                "id": str(x.id),
                "is_scam": bool(x.is_scam),
                "scam_type": x.scam_type,
                "score": result.score,
                "band": result.band,
                "predicted_scam": predicted,
            }
        )

    cm = confusion(y_true, y_pred)
    metrics = derive_metrics(cm)
    per_type = recall_by_group(y_true, y_pred, scam_types)

    # Hard-negative clearance: legit-but-tricky listings the detector should NOT flag.
    hard_ids = _load_hard_negative_ids()
    hard_total = sum(1 for r in rows if r["id"] in hard_ids)
    hard_cleared = sum(1 for r in rows if r["id"] in hard_ids and not r["predicted_scam"])

    return {
        "confusion": cm,
        "metrics": metrics,
        "per_scam_type_recall": per_type,
        "hard_negatives": {"total": hard_total, "cleared": hard_cleared},
        "rows": rows,
    }


def _markdown(report: dict) -> str:
    cm, m = report["confusion"], report["metrics"]
    lines = [
        "# Scam detector — evaluation",
        "",
        "Predicted scam = High-risk band. Labels are the hidden synthetic ground truth.",
        "",
        "## Confusion matrix",
        "",
        "| | predicted scam | predicted legit |",
        "|---|---|---|",
        f"| **actual scam** | {cm['tp']} (TP) | {cm['fn']} (FN) |",
        f"| **actual legit** | {cm['fp']} (FP) | {cm['tn']} (TN) |",
        "",
        "## Metrics",
        "",
        f"- Precision: {m['precision']:.0%}",
        f"- Recall: {m['recall']:.0%}",
        f"- F1: {m['f1']:.2f}",
        f"- Accuracy: {m['accuracy']:.0%}",
        "",
        "## Recall by scam type",
        "",
        "| scam type | caught / total | recall |",
        "|---|---|---|",
    ]
    for stype, s in report["per_scam_type_recall"].items():
        lines.append(f"| {stype} | {s['caught']}/{s['total']} | {s['recall']:.0%} |")
    hn = report["hard_negatives"]
    lines += ["", f"Hard negatives correctly cleared: {hn['cleared']}/{hn['total']}", ""]
    return "\n".join(lines)


def _print_report(report: dict) -> None:
    cm, m = report["confusion"], report["metrics"]
    print("Confusion matrix (positive = scam):")
    print(f"  TP={cm['tp']}  FN={cm['fn']}")
    print(f"  FP={cm['fp']}  TN={cm['tn']}")
    print(
        f"\nPrecision {m['precision']:.0%} · Recall {m['recall']:.0%} · "
        f"F1 {m['f1']:.2f} · Accuracy {m['accuracy']:.0%}"
    )
    print("\nRecall by scam type:")
    for stype, s in report["per_scam_type_recall"].items():
        print(f"  {stype:18} {s['caught']}/{s['total']}  ({s['recall']:.0%})")
    hn = report["hard_negatives"]
    print(f"\nHard negatives cleared: {hn['cleared']}/{hn['total']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the scam-detection eval.")
    parser.add_argument("--no-llm", action="store_true", help="Skip the LLM text pass")
    args = parser.parse_args()

    report = run(skip_text=args.no_llm)
    _print_report(report)

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "scam_eval.json").write_text(json.dumps(report, indent=2))
    (RESULTS_DIR / "scam_eval.md").write_text(_markdown(report))
    logger.info("Wrote %s and scam_eval.md", RESULTS_DIR / "scam_eval.json")


if __name__ == "__main__":
    main()
