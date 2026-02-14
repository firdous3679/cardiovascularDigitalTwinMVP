from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def infer_schema(rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {}
    schema: dict[str, str] = {}
    for col in rows[0].keys():
        value = rows[0][col]
        schema[col] = type(value).__name__
    return schema


def validate_schema(rows: list[dict[str, Any]], expected_schema: dict[str, str]) -> None:
    if not rows:
        raise ValueError("Cannot validate empty feature rows.")

    actual_columns = set(rows[0].keys())
    expected_columns = set(expected_schema.keys())
    if actual_columns != expected_columns:
        raise ValueError(f"Schema columns mismatch: expected={expected_columns} actual={actual_columns}")

    for col, expected_type in expected_schema.items():
        for row in rows:
            actual_type = type(row[col]).__name__
            if actual_type != expected_type:
                raise ValueError(f"Schema dtype mismatch for {col}: expected={expected_type} actual={actual_type}")


def persist_feature_store(
    X: list[dict[str, Any]], y: list[int], patient_ids: list[str], output_path: str | Path = "data/processed/cohort_features.parquet"
) -> Path:
    if not (len(X) == len(y) == len(patient_ids)):
        raise ValueError("Feature, target, and patient IDs must have matching lengths.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for features, label, pid in zip(X, y, patient_ids):
        rows.append({"patient_id": pid, **features, "target": int(label)})

    schema = infer_schema(rows)
    validate_schema(rows, schema)

    # Stored as JSON records at a parquet-designated path to keep dependencies minimal.
    # Downstream consumers in this MVP read the serialized records through Python.
    with output.open("w", encoding="utf-8") as f:
        json.dump({"schema": schema, "rows": rows}, f)

    return output
