from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from twin.data.uci_loader import load_uci_dataset


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _risk_from_features(features: dict[str, Any], label: int) -> float:
    age = float(features.get("age", 55.0))
    chol = float(features.get("chol", 220.0))
    trestbps = float(features.get("trestbps", 130.0))
    thalch = float(features.get("thalch", 150.0))
    oldpeak = float(features.get("oldpeak", 1.0))
    risk = 0.2 + (age - 50.0) * 0.01 + (chol - 200.0) * 0.001 + (trestbps - 120.0) * 0.004 - (thalch - 140.0) * 0.002
    risk += oldpeak * 0.05 + label * 0.12
    return _clamp(risk, 0.01, 0.98)


def _base_metrics(features: dict[str, Any], label: int, rng: random.Random) -> dict[str, float]:
    age = float(features.get("age", 55.0))
    bp = float(features.get("trestbps", 130.0))
    chol = float(features.get("chol", 220.0))
    hr = float(features.get("thalch", 150.0)) * 0.55 + rng.uniform(-8, 8)
    activity = 9000 - (age - 45) * 80 - label * 1000 + rng.uniform(-800, 800)
    sleep_h = 7.2 - label * 0.4 + rng.uniform(-0.6, 0.4)
    return {
        "risk": _risk_from_features(features, label),
        "sbp": _clamp(bp + rng.uniform(-8, 10), 95, 210),
        "dbp": _clamp(0.62 * bp + rng.uniform(-6, 6), 55, 130),
        "hr": _clamp(hr, 45, 135),
        "steps": _clamp(activity, 1000, 18000),
        "sleep_h": _clamp(sleep_h, 4.5, 9.5),
        "chol": chol,
        "age": age,
    }


def _write_json_records(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": {k: type(v).__name__ for k, v in rows[0].items()} if rows else {}, "rows": rows}
    path.write_text(json.dumps(payload), encoding="utf-8")


def generate_synthetic_data(seed: int = 42, data_path: str | None = None, days: int = 180, output_root: str | Path = "data/synth") -> dict[str, Path]:
    X, y, patient_ids = load_uci_dataset(data_path)
    root = Path(output_root)
    fhir_root = root / "fhir_ndjson"
    wearable_root = root / "wearables"
    fhir_root.mkdir(parents=True, exist_ok=True)
    wearable_root.mkdir(parents=True, exist_ok=True)

    resource_rows: dict[str, list[dict[str, Any]]] = {r: [] for r in ["Encounter", "Condition", "MedicationRequest", "Observation", "Procedure"]}
    imaging_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)

    for idx, (pid, feat, label) in enumerate(zip(patient_ids, X, y)):
        rng = random.Random(seed * 10_000 + idx)
        base = _base_metrics(feat, label, rng)

        imaging_rows.append(
            {
                "patient_id": pid,
                "lvef": round(_clamp(65 - base["risk"] * 28 + rng.uniform(-5, 4), 20, 75), 1),
                "lvedv": round(_clamp(110 + base["risk"] * 55 + rng.uniform(-12, 12), 65, 260), 1),
                "lvesv": round(_clamp(45 + base["risk"] * 40 + rng.uniform(-9, 10), 20, 180), 1),
                "wall_thickness": round(_clamp(9 + base["risk"] * 5 + rng.uniform(-1.2, 1.2), 6, 18), 2),
                "cac_score_proxy": int(_clamp(base["risk"] * 280 + rng.uniform(0, 140), 0, 700)),
            }
        )

        risk_rows.append(
            {
                "patient_id": pid,
                "apoe4_carrier": int(rng.random() < (0.1 + 0.2 * base["risk"])),
                "family_history_cvd": int(rng.random() < (0.2 + 0.5 * base["risk"])),
                "polygenic_risk_decile": int(_clamp(round(base["risk"] * 10 + rng.uniform(-1, 1)), 1, 10)),
            }
        )

        wearable_rows: list[dict[str, Any]] = []
        for day_offset in range(days):
            day = now - timedelta(days=(days - 1 - day_offset))
            circadian = 1.0 + 0.12 * (1 if day.weekday() < 5 else -1)
            missing_day = rng.random() < 0.08
            hr = _clamp(base["hr"] * circadian + rng.uniform(-7, 7), 40, 160)
            sbp = _clamp(base["sbp"] + rng.uniform(-10, 10), 85, 220)
            dbp = _clamp(base["dbp"] + rng.uniform(-8, 8), 45, 140)
            steps = _clamp(base["steps"] * (0.75 + 0.35 * rng.random()) * (0.9 if day.weekday() > 4 else 1.0), 0, 25000)
            sleep_h = _clamp(base["sleep_h"] + rng.uniform(-1.2, 1.0), 3.5, 10.5)
            sleep_eff = _clamp(0.88 - base["risk"] * 0.13 + rng.uniform(-0.08, 0.05), 0.55, 0.98)

            wearable_rows.append(
                {
                    "patient_id": pid,
                    "timestamp": day.isoformat(),
                    "hr": None if missing_day and rng.random() < 0.5 else round(hr, 1),
                    "sbp": None if missing_day and rng.random() < 0.6 else round(sbp, 1),
                    "dbp": None if missing_day and rng.random() < 0.6 else round(dbp, 1),
                    "steps": None if missing_day else int(steps),
                    "sleep_duration_h": None if missing_day and rng.random() < 0.5 else round(sleep_h, 2),
                    "sleep_efficiency": None if missing_day and rng.random() < 0.5 else round(sleep_eff, 3),
                }
            )

            if rng.random() < (0.03 + base["risk"] * 0.08):
                resource_rows["Encounter"].append(
                    {
                        "resourceType": "Encounter",
                        "id": f"enc-{pid}-{day.date()}",
                        "subject": {"reference": f"Patient/{pid}"},
                        "period": {"start": day.isoformat()},
                        "class": {"code": "outpatient" if rng.random() < 0.8 else "emergency"},
                    }
                )

            if day_offset % 30 == 0 or rng.random() < 0.04:
                resource_rows["Observation"].append(
                    {
                        "resourceType": "Observation",
                        "id": f"obs-{pid}-{day.date()}",
                        "subject": {"reference": f"Patient/{pid}"},
                        "effectiveDateTime": day.isoformat(),
                        "code": {"coding": [{"system": "placeholder-lab", "code": "bp_panel"}]},
                        "component": [
                            {"code": {"text": "SBP"}, "valueQuantity": {"value": round(sbp, 1)}},
                            {"code": {"text": "DBP"}, "valueQuantity": {"value": round(dbp, 1)}},
                            {"code": {"text": "HR"}, "valueQuantity": {"value": round(hr, 1)}},
                        ],
                    }
                )

            if day_offset % 45 == 0 and rng.random() < 0.75:
                resource_rows["MedicationRequest"].append(
                    {
                        "resourceType": "MedicationRequest",
                        "id": f"med-{pid}-{day.date()}",
                        "subject": {"reference": f"Patient/{pid}"},
                        "authoredOn": day.isoformat(),
                        "medicationCodeableConcept": {"coding": [{"system": "placeholder-rx", "code": "statin_or_bp_agent"}]},
                        "status": "active",
                    }
                )

            if day_offset % 60 == 0 and rng.random() < (0.35 + base["risk"] * 0.4):
                resource_rows["Condition"].append(
                    {
                        "resourceType": "Condition",
                        "id": f"cond-{pid}-{day.date()}",
                        "subject": {"reference": f"Patient/{pid}"},
                        "recordedDate": day.isoformat(),
                        "code": {"coding": [{"system": "placeholder-cond", "code": "cvd_risk_state"}]},
                        "clinicalStatus": {"text": "active"},
                    }
                )

            if day_offset % 90 == 0 and rng.random() < (0.2 + base["risk"] * 0.3):
                resource_rows["Procedure"].append(
                    {
                        "resourceType": "Procedure",
                        "id": f"proc-{pid}-{day.date()}",
                        "subject": {"reference": f"Patient/{pid}"},
                        "performedDateTime": day.isoformat(),
                        "code": {"coding": [{"system": "placeholder-proc", "code": "stress_test_or_echo"}]},
                        "status": "completed",
                    }
                )

        _write_json_records(wearable_root / f"{pid}.parquet", wearable_rows)

    for resource, rows in resource_rows.items():
        out = fhir_root / f"{resource.lower()}.ndjson"
        out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    _write_json_records(root / "imaging_features.parquet", imaging_rows)
    _write_json_records(root / "risk_factors.parquet", risk_rows)

    return {
        "fhir_root": fhir_root,
        "imaging": root / "imaging_features.parquet",
        "wearables": wearable_root,
        "risk_factors": root / "risk_factors.parquet",
    }
