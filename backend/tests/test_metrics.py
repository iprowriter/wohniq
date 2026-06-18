"""Unit tests for the eval metrics (pure, no DB/API)."""

from evals.metrics import confusion, derive_metrics, recall_by_group


def test_confusion_counts():
    y_true = [True, True, False, False, True]
    y_pred = [True, False, True, False, True]
    cm = confusion(y_true, y_pred)
    assert cm == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}


def test_derive_metrics():
    cm = {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    m = derive_metrics(cm)
    assert abs(m["precision"] - 2 / 3) < 1e-9
    assert abs(m["recall"] - 2 / 3) < 1e-9
    assert abs(m["f1"] - 2 / 3) < 1e-9
    assert abs(m["accuracy"] - 0.6) < 1e-9


def test_metrics_handle_empty():
    m = derive_metrics({"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    assert m == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0}


def test_recall_by_group():
    y_true = [True, True, True, False]
    y_pred = [True, False, True, True]  # last is a legit false-positive (ignored here)
    groups = ["price_bait", "price_bait", "photo_reuse", None]
    out = recall_by_group(y_true, y_pred, groups)
    assert out["price_bait"] == {"caught": 1, "total": 2, "recall": 0.5}
    assert out["photo_reuse"] == {"caught": 1, "total": 1, "recall": 1.0}
    assert "unknown" not in out  # the legit row (y_true False) isn't counted
