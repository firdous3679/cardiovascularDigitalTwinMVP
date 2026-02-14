from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any

ROOT_CSV_FALLBACK = Path("heart_disease_uci.csv")
RAW_CSV_PRIMARY = Path("data/raw/uci_heart/heart_disease_uci.csv")


def normalize_column_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def resolve_data_path(path: str | None = None) -> Path:
    if path:
        return Path(path)
    if RAW_CSV_PRIMARY.exists():
        return RAW_CSV_PRIMARY
    return ROOT_CSV_FALLBACK


def _to_number(value: str) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if text == "" or text.lower() in {"na", "nan", "none", "null", "?"}:
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return 1.0 if lowered == "true" else 0.0
    try:
        return float(text)
    except ValueError:
        return None


def _mode(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda pair: pair[1])[0] if counts else "unknown"


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stable_patient_id(row: dict[str, Any], target_column: str | None) -> str:
    serial = "|".join(
        f"{k}={row[k]}" for k in sorted(row.keys()) if k != target_column
    )
    digest = hashlib.sha256(serial.encode("utf-8")).hexdigest()[:16]
    return f"pid_{digest}"


def load_uci_dataset(path: str | None = None) -> tuple[list[dict[str, Any]], list[int], list[str]]:
    """Load and clean UCI heart data.

    Missing-value strategy:
    - Numeric columns: median imputation.
    - Categorical columns: mode imputation, fallback value "unknown".
    """

    data_path = resolve_data_path(path)
    with data_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")
        rows = [
            {normalize_column_name(k): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            for row in reader
        ]

    if not rows:
        raise ValueError("Dataset is empty.")

    target_column = "target" if "target" in rows[0] else ("num" if "num" in rows[0] else None)
    if target_column is None:
        raise ValueError("Expected target column 'target' or 'num'.")

    feature_columns = [col for col in rows[0].keys() if col != target_column]
    numeric_flags: dict[str, bool] = {}
    for col in feature_columns:
        numeric_flags[col] = all(
            (_to_number(row.get(col, "")) is not None) or str(row.get(col, "")).strip() in {"", "?", "NA", "na"}
            for row in rows
        )

    numeric_values: dict[str, list[float]] = {col: [] for col in feature_columns if numeric_flags[col]}
    categorical_values: dict[str, list[str]] = {col: [] for col in feature_columns if not numeric_flags[col]}

    for row in rows:
        for col in feature_columns:
            raw = str(row.get(col, ""))
            num = _to_number(raw)
            if numeric_flags[col]:
                if num is not None:
                    numeric_values[col].append(num)
            else:
                cleaned = raw.strip()
                if cleaned and cleaned not in {"?", "NA", "na"}:
                    categorical_values[col].append(cleaned)

    numeric_fill = {col: _median(vals) for col, vals in numeric_values.items()}
    categorical_fill = {col: _mode(vals) for col, vals in categorical_values.items()}

    X: list[dict[str, Any]] = []
    y: list[int] = []
    patient_ids: list[str] = []

    for row in rows:
        raw_target = _to_number(str(row.get(target_column, "")))
        if raw_target is None:
            raise ValueError("Target contains missing/non-numeric values.")

        mapped_target = int(raw_target)
        if mapped_target not in {0, 1}:
            mapped_target = 0 if mapped_target == 0 else 1
        y.append(mapped_target)

        features: dict[str, Any] = {}
        for col in feature_columns:
            raw = str(row.get(col, ""))
            num = _to_number(raw)
            if numeric_flags[col]:
                features[col] = num if num is not None else numeric_fill[col]
            else:
                cleaned = raw.strip()
                features[col] = cleaned if cleaned and cleaned not in {"?", "NA", "na"} else categorical_fill[col]

        pid = _stable_patient_id({**features, target_column: mapped_target}, target_column)
        patient_ids.append(pid)
        X.append(features)

    return X, y, patient_ids
