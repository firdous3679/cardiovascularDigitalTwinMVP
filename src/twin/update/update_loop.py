from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from twin.sim.hemodynamics_stub import simulate_hemodynamics_stub


def _read_records(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["rows"]


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_update_loop(
    synth_root: str | Path = "data/synth",
    output_root: str | Path = "data/twin_state",
    days: int = 30,
    recalibrate_weekly: bool = True,
) -> list[Path]:
    root = Path(synth_root)
    state_root = Path(output_root)
    state_root.mkdir(parents=True, exist_ok=True)

    wearable_by_patient: dict[str, list[dict[str, Any]]] = {}
    for w_file in (root / "wearables").glob("*.parquet"):
        rows = sorted(_read_records(w_file), key=lambda r: r["timestamp"])
        if rows:
            wearable_by_patient[rows[0]["patient_id"]] = rows

    imaging = {r["patient_id"]: r for r in _read_records(root / "imaging_features.parquet")}

    events_by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for resource in ["encounter", "condition", "medicationrequest", "observation", "procedure"]:
        for event in _load_ndjson(root / "fhir_ndjson" / f"{resource}.ndjson"):
            key = event.get("period", {}).get("start") or event.get("effectiveDateTime") or event.get("authoredOn") or event.get("recordedDate") or event.get("performedDateTime")
            if key:
                events_by_day[key[:10]][event["resourceType"]] += 1

    all_dates = sorted({r["timestamp"][:10] for rows in wearable_by_patient.values() for r in rows})
    if not all_dates:
        return []
    dates = all_dates[-days:]

    snapshots: list[Path] = []
    calibration_offset = 0.0

    for i, day in enumerate(dates):
        out_file = state_root / f"state_{day}.jsonl"
        lines: list[str] = []

        day_risks = []
        for pid, rows in wearable_by_patient.items():
            history = [r for r in rows if r["timestamp"][:10] <= day]
            last14 = history[-14:]
            today = next((r for r in history if r["timestamp"][:10] == day), None)
            if not last14 or today is None:
                continue

            hr_vals = [r["hr"] for r in last14 if r["hr"] is not None]
            sbp_vals = [r["sbp"] for r in last14 if r["sbp"] is not None]
            dbp_vals = [r["dbp"] for r in last14 if r["dbp"] is not None]
            step_vals = [r["steps"] for r in last14 if r["steps"] is not None]

            if not hr_vals or not sbp_vals or not dbp_vals:
                continue

            hr_mean = mean(hr_vals)
            sbp_mean = mean(sbp_vals)
            dbp_mean = mean(dbp_vals)
            steps_mean = mean(step_vals) if step_vals else 0.0
            bp_trend = sbp_vals[-1] - sbp_vals[0] if len(sbp_vals) > 1 else 0.0
            activity_trend = step_vals[-1] - step_vals[0] if len(step_vals) > 1 else 0.0

            hemo = simulate_hemodynamics_stub(float(imaging.get(pid, {}).get("lvef", 55.0)), hr_mean, sbp_mean, dbp_mean)
            risk = 0.25 + (sbp_mean - 120) * 0.004 + (hr_mean - 70) * 0.003 - (steps_mean - 7000) / 100000
            risk += max(0.0, bp_trend) * 0.001 + calibration_offset
            risk = max(0.01, min(0.99, risk))

            event_counts = events_by_day.get(day, {})
            snapshot = {
                "patient_id": pid,
                "date": day,
                "risk": round(risk, 5),
                "bp_trend": round(bp_trend, 4),
                "activity_trend": round(activity_trend, 4),
                "events_today": dict(event_counts),
                "rolling_mean_shift": round((hr_mean - 70.0) / 70.0, 5),
                "calibration_drift": round(abs(risk - 0.5), 5),
                "recalibrated": False,
                "hemodynamics_stub": hemo,
            }
            lines.append(json.dumps(snapshot, sort_keys=True))
            day_risks.append(risk)

        if recalibrate_weekly and i > 0 and i % 7 == 0 and day_risks:
            avg_risk = mean(day_risks)
            if abs(avg_risk - 0.5) > 0.07:
                calibration_offset += (0.5 - avg_risk) * 0.3
                lines = [
                    json.dumps({**json.loads(line), "recalibrated": True}, sort_keys=True)
                    for line in lines
                ]

        out_file.write_text("\n".join(lines), encoding="utf-8")
        snapshots.append(out_file)

    return snapshots
