from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any


def _stratified_split(y: list[int], test_size: float = 0.2, seed: int = 42) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    positives = [i for i, val in enumerate(y) if val == 1]
    negatives = [i for i, val in enumerate(y) if val == 0]
    rng.shuffle(positives)
    rng.shuffle(negatives)

    pos_test = max(1, int(len(positives) * test_size))
    neg_test = max(1, int(len(negatives) * test_size))

    test_idx = set(positives[:pos_test] + negatives[:neg_test])
    train_idx = [i for i in range(len(y)) if i not in test_idx]
    return train_idx, sorted(test_idx)


def _build_encoder(X: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    numeric_cols: list[str] = []
    categorical_levels: dict[str, list[str]] = {}
    cols = list(X[0].keys())
    for col in cols:
        if isinstance(X[0][col], (int, float)):
            numeric_cols.append(col)
        else:
            categorical_levels[col] = sorted({str(row[col]) for row in X})
    return numeric_cols, categorical_levels


def _encode_rows(X: list[dict[str, Any]], numeric_cols: list[str], categorical_levels: dict[str, list[str]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in X:
        vec: list[float] = [1.0]
        for col in numeric_cols:
            vec.append(float(row[col]))
        for col, levels in categorical_levels.items():
            value = str(row[col])
            vec.extend([1.0 if value == level else 0.0 for level in levels])
        matrix.append(vec)
    return matrix


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def _fit_logistic(X: list[list[float]], y: list[int], epochs: int = 300, lr: float = 0.001) -> list[float]:
    weights = [0.0 for _ in range(len(X[0]))]
    for _ in range(epochs):
        grad = [0.0 for _ in weights]
        for row, target in zip(X, y):
            pred = _sigmoid(sum(w * x for w, x in zip(weights, row)))
            err = pred - target
            for j, xj in enumerate(row):
                grad[j] += err * xj
        n = float(len(X))
        for j in range(len(weights)):
            weights[j] -= lr * grad[j] / n
    return weights


def _predict_proba(X: list[list[float]], w: list[float]) -> list[float]:
    return [_sigmoid(sum(wj * xj for wj, xj in zip(w, row))) for row in X]


def _accuracy(y: list[int], p: list[float]) -> float:
    preds = [1 if s >= 0.5 else 0 for s in p]
    return sum(int(a == b) for a, b in zip(y, preds)) / len(y)


def _f1(y: list[int], p: list[float]) -> float:
    preds = [1 if s >= 0.5 else 0 for s in p]
    tp = sum(1 for yt, yp in zip(y, preds) if yt == yp == 1)
    fp = sum(1 for yt, yp in zip(y, preds) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y, preds) if yt == 1 and yp == 0)
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def _brier(y: list[int], p: list[float]) -> float:
    return sum((yt - pt) ** 2 for yt, pt in zip(y, p)) / len(y)


def _auroc(y: list[int], p: list[float]) -> float:
    pairs = sorted(zip(p, y), key=lambda x: x[0], reverse=True)
    pos = sum(y)
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return 0.0

    tp = 0
    fp = 0
    prev_tpr = 0.0
    prev_fpr = 0.0
    area = 0.0
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr = tp / pos
        fpr = fp / neg
        area += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
        prev_tpr, prev_fpr = tpr, fpr
    return area


def _auprc(y: list[int], p: list[float]) -> float:
    pairs = sorted(zip(p, y), key=lambda x: x[0], reverse=True)
    pos = sum(y)
    if pos == 0:
        return 0.0

    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / pos
        precision = tp / (tp + fp)
        area += (recall - prev_recall) * precision
        prev_recall = recall
    return area


def train_and_evaluate(X: list[dict[str, Any]], y: list[int], output_metrics: str | Path = "reports/metrics.json") -> dict[str, float]:
    if len(X) < 10:
        raise ValueError("Dataset too small for train/test evaluation.")

    train_idx, test_idx = _stratified_split(y)
    X_train = [X[i] for i in train_idx]
    y_train = [y[i] for i in train_idx]
    X_test = [X[i] for i in test_idx]
    y_test = [y[i] for i in test_idx]

    numeric_cols, categorical_levels = _build_encoder(X_train)
    Z_train = _encode_rows(X_train, numeric_cols, categorical_levels)
    Z_test = _encode_rows(X_test, numeric_cols, categorical_levels)

    weights = _fit_logistic(Z_train, y_train)
    proba = _predict_proba(Z_test, weights)

    metrics = {
        "auroc": _auroc(y_test, proba),
        "auprc": _auprc(y_test, proba),
        "accuracy": _accuracy(y_test, proba),
        "f1": _f1(y_test, proba),
        "brier_score": _brier(y_test, proba),
    }

    metrics_path = Path(output_metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics
