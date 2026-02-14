from __future__ import annotations

import json
from pathlib import Path

from twin.features.aggregate_synth_features import aggregate_synth_features
from twin.synth.generate import generate_synthetic_data
from twin.update.update_loop import run_update_loop


def _read_rows(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))["rows"]


def test_synth_generation_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = Path(__file__).resolve().parents[1] / "heart_disease_uci.csv"
    csv_path = tmp_path / "heart_disease_uci.csv"
    csv_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    out_a = generate_synthetic_data(seed=123, days=10)
    wear_a = _read_rows(out_a["wearables"] / sorted(p.name for p in out_a["wearables"].glob("*.parquet"))[0])

    out_b = generate_synthetic_data(seed=123, days=10)
    wear_b = _read_rows(out_b["wearables"] / sorted(p.name for p in out_b["wearables"].glob("*.parquet"))[0])

    assert wear_a == wear_b


def test_synth_schemas_and_aggregation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = Path(__file__).resolve().parents[1] / "heart_disease_uci.csv"
    csv_path = tmp_path / "heart_disease_uci.csv"
    csv_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    from twin.cli import run_baseline

    run_baseline(str(csv_path))
    generate_synthetic_data(seed=42, days=7, data_path=str(csv_path))
    merged = aggregate_synth_features()

    imaging = _read_rows(Path("data/synth/imaging_features.parquet"))
    risk = _read_rows(Path("data/synth/risk_factors.parquet"))
    wearable_files = list(Path("data/synth/wearables").glob("*.parquet"))

    assert imaging and {"patient_id", "lvef", "lvedv", "lvesv", "wall_thickness", "cac_score_proxy"}.issubset(imaging[0])
    assert risk and {"patient_id", "apoe4_carrier", "family_history_cvd", "polygenic_risk_decile"}.issubset(risk[0])
    assert wearable_files
    assert {"patient_id", "timestamp", "hr", "sbp", "dbp", "steps", "sleep_duration_h", "sleep_efficiency"}.issubset(
        _read_rows(wearable_files[0])[0]
    )

    merged_rows = _read_rows(merged)
    assert merged_rows and "wearable_hr_mean" in merged_rows[0]


def test_update_loop_writes_valid_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = Path(__file__).resolve().parents[1] / "heart_disease_uci.csv"
    csv_path = tmp_path / "heart_disease_uci.csv"
    csv_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    from twin.cli import run_baseline

    run_baseline(str(csv_path))
    generate_synthetic_data(seed=2, days=20, data_path=str(csv_path))
    snapshots = run_update_loop(days=10)

    assert snapshots
    last = snapshots[-1]
    lines = [ln for ln in last.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines
    row = json.loads(lines[0])
    assert {"patient_id", "date", "risk", "bp_trend", "activity_trend", "hemodynamics_stub"}.issubset(row)
