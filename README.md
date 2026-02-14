# Cardiovascular Digital Twin MVP

> **Research MVP disclaimer:** This repository is for research/prototyping only. It is **non-clinical** and must not be used for diagnosis, treatment, or medical decision-making.

This project provides a clean baseline pipeline over the committed UCI CSV dataset plus a synthetic multimodal digital twin workflow:

1. Load and clean UCI cohort data
2. Build processed cohort features
3. Train/evaluate a baseline classifier
4. Generate synthetic multimodal data conditioned on cohort patient features
5. Aggregate synthetic + cohort features
6. Run daily twin update snapshots with simple drift checks
7. Visualize patient trajectories in Streamlit dashboard

## Prerequisites

- Python 3.11+
- `make`

## Data source behavior

The loader resolves data in this order:

1. `data/raw/uci_heart/heart_disease_uci.csv`
2. fallback to `./heart_disease_uci.csv` (repo root)

Raw data is not edited by the pipeline.

## Setup

```bash
make setup
```

## Run baseline pipeline

```bash
make run
```

Or directly with an optional custom path:

```bash
python -m twin.cli run-baseline --data path/to/heart_disease_uci.csv
```

## Generate synthetic multimodal data

```bash
make synth
```

Direct CLI options:

```bash
python -m twin.cli generate-synth --seed 42 --days 180
```

Notes:
- Deterministic with seed (`same seed => same synthetic outputs`).
- Synthetic records are conditioned on each patient's UCI feature profile.
- Includes realistic missingness and noise.
- Writes synthetic FHIR-ish NDJSON, imaging-derived features, wearables, and risk-factor tables.

## Run digital twin update loop

```bash
make update
```

Optionally set number of days:

```bash
DAYS=45 make update
```

This ingests daily synthetic data, updates per-patient state (`risk`, `bp_trend`, `activity_trend`), writes state snapshots to `data/twin_state/state_YYYY-MM-DD.jsonl`, and applies simple drift checks plus weekly lightweight recalibration.

## Run dashboard

```bash
make dashboard
```

Dashboard includes:
- patient selector
- risk-over-time plot
- 14-day wearable summary
- compact EHR timeline (counts + sample events)
- what-if sliders (BP/activity) with clearly labeled heuristic risk perturbation

## Run tests

```bash
make test
```

## Output artifacts

After running `make run`, `make synth`, and `make update`, the pipeline writes:

- `data/processed/cohort_features.parquet`
- `data/processed/features_with_synth.parquet`
- `data/synth/fhir_ndjson/*.ndjson`
- `data/synth/imaging_features.parquet`
- `data/synth/wearables/*.parquet`
- `data/synth/risk_factors.parquet`
- `data/twin_state/state_YYYY-MM-DD.jsonl`
- `reports/metrics.json`
- `reports/summary.md`

## Replacing synthetic EHR with real FHIR later (high-level)

1. Keep patient-level key (`patient_id`) as the stable join bridge.
2. Swap synthetic NDJSON reader with a real FHIR ingestion layer that extracts Encounter/Condition/MedicationRequest/Observation/Procedure.
3. Map real code systems (LOINC/SNOMED/RxNorm) into the same downstream feature contracts used in `aggregate_synth_features.py`.
4. Preserve the update-loop state schema so dashboard and evaluation continue to work.
5. Add governance: de-identification, consent scope, and audit logging before any clinical deployment.

## Project layout

- `src/twin/data/uci_loader.py` — loading, column normalization, missing values, target mapping, stable patient IDs
- `src/twin/features/feature_store.py` — persisted processed cohort + schema checks
- `src/twin/synth/generate.py` — deterministic synthetic multimodal generation
- `src/twin/features/aggregate_synth_features.py` — synthetic modality aggregation and join with cohort
- `src/twin/update/update_loop.py` — daily twin updates + drift checks/recalibration
- `src/twin/sim/hemodynamics_stub.py` — mechanistic placeholder simulator stub
- `app/streamlit_app.py` — Streamlit dashboard
- `tests/` — unit and smoke tests
