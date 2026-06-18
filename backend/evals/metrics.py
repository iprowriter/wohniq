"""Classification metrics for the scam eval (pure, stdlib only).

Confusion matrix, precision/recall/F1/accuracy, and per-group recall — everything
needed to report how well the detector recovers the hidden ground-truth labels.
Unit-testable offline; the scam eval feeds it the detector's predictions.
"""

from __future__ import annotations

from collections.abc import Sequence


def confusion(y_true: Sequence[bool], y_pred: Sequence[bool]) -> dict[str, int]:
    """2×2 counts. Positive = scam."""
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if not t and not p)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def derive_metrics(cm: dict[str, int]) -> dict[str, float]:
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }


def recall_by_group(
    y_true: Sequence[bool],
    y_pred: Sequence[bool],
    groups: Sequence[str | None],
) -> dict[str, dict[str, float]]:
    """Recall per group, counting only true positives' group (e.g. per scam_type)."""
    out: dict[str, list[int]] = {}  # group -> [caught, total]
    for true, pred, group in zip(y_true, y_pred, groups, strict=True):
        if not true:
            continue
        key = group or "unknown"
        bucket = out.setdefault(key, [0, 0])
        bucket[1] += 1
        if pred:
            bucket[0] += 1
    return {
        key: {"caught": caught, "total": total, "recall": caught / total if total else 0.0}
        for key, (caught, total) in sorted(out.items())
    }
