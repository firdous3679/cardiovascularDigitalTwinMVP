from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


def _read_records(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload["rows"]


def aggregate_synth_features(
    cohort_path: str | Path = "data/processed/cohort_features.parquet",
    synth_root: str | Path = "data/synth",
    output_path: str | Path = "data/processed/features_with_synth.parquet",
) -> Path:
    cohort_rows = _read_records(cohort_path)
    root = Path(synth_root)
    imaging = {row["patient_id"]: row for row in _read_records(root / "imaging_features.parquet")}
    risk_factors = {row["patient_id"]: row for row in _read_records(root / "risk_factors.parquet")}

    wearable_summary: dict[str, dict[str, float]] = {}
    for w_file in (root / "wearables").glob("*.parquet"):
        rows = _read_records(w_file)
        if not rows:
            continue
        pid = rows[0]["patient_id"]
        wearable_summary[pid] = {
            "wearable_days": float(len(rows)),
            "wearable_hr_mean": round(mean(r["hr"] for r in rows if r["hr"] is not None), 3),
            "wearable_steps_mean": round(mean(r["steps"] for r in rows if r["steps"] is not None), 3),
            "wearable_sleep_mean": round(mean(r["sleep_duration_h"] for r in rows if r["sleep_duration_h"] is not None), 3),
            "wearable_missing_rate": round(
                mean(1.0 if r["hr"] is None or r["steps"] is None else 0.0 for r in rows), 4
            ),
        }

    merged: list[dict[str, Any]] = []
    for row in cohort_rows:
        pid = row["patient_id"]
        out = dict(row)
        out.update({k: v for k, v in imaging.get(pid, {}).items() if k != "patient_id"})
        out.update({k: v for k, v in wearable_summary.get(pid, {}).items()})
        out.update({k: v for k, v in risk_factors.get(pid, {}).items() if k != "patient_id"})
        merged.append(out)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    schema = {k: type(v).__name__ for k, v in merged[0].items()} if merged else {}
    output.write_text(json.dumps({"schema": schema, "rows": merged}), encoding="utf-8")
    return output
