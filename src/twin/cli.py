from __future__ import annotations

import argparse

from twin.data.uci_loader import load_uci_dataset
from twin.eval.report import write_summary
from twin.features.feature_store import persist_feature_store
from twin.models.baseline import train_and_evaluate


def run_baseline(data_path: str | None = None) -> None:
    X, y, patient_ids = load_uci_dataset(data_path)
    persist_feature_store(X, y, patient_ids)
    metrics = train_and_evaluate(X, y)
    write_summary(metrics)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cardiovascular Digital Twin MVP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run-baseline", help="Run baseline pipeline")
    run_parser.add_argument("--data", default=None, help="Optional CSV path")

    args = parser.parse_args()
    if args.command == "run-baseline":
        run_baseline(args.data)


if __name__ == "__main__":
    main()
