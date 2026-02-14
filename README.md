# Cardiovascular Digital Twin MVP

> **Research MVP disclaimer:** This repository is for research/prototyping only. It is **non-clinical** and must not be used for diagnosis, treatment, or medical decision-making.

This project provides a clean, testable backbone pipeline over the committed UCI CSV dataset:

1. Load and clean data
2. Build processed cohort features
3. Train/evaluate a baseline classifier
4. Write report artifacts

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

## Run tests

```bash
make test
```

## Output artifacts

After `make run`, the pipeline writes:

- `data/processed/cohort_features.parquet`
- `reports/metrics.json`
- `reports/summary.md`

## Project layout

- `src/twin/data/uci_loader.py` — loading, column normalization, missing values, target mapping, stable patient IDs
- `src/twin/features/feature_store.py` — persisted processed cohort + schema check
- `src/twin/models/baseline.py` — split, baseline model, metrics
- `src/twin/eval/report.py` — markdown summary
- `src/twin/state/state.py` — twin state dataclass + JSON helpers
- `tests/` — unit and smoke tests
