from __future__ import annotations

import argparse

from twin.data.uci_loader import load_uci_dataset
from twin.eval.report import write_summary
from twin.features.aggregate_synth_features import aggregate_synth_features
from twin.features.feature_store import persist_feature_store
from twin.models.baseline import train_and_evaluate
from twin.synth.generate import generate_synthetic_data
from twin.update.update_loop import run_update_loop


def run_baseline(data_path: str | None = None) -> None:
    X, y, patient_ids = load_uci_dataset(data_path)
    persist_feature_store(X, y, patient_ids)
    metrics = train_and_evaluate(X, y)
    write_summary(metrics)


def run_synth(seed: int = 42, days: int = 180, data_path: str | None = None) -> None:
    generate_synthetic_data(seed=seed, data_path=data_path, days=days)
    aggregate_synth_features()


def run_updates(days: int = 30) -> None:
    run_update_loop(days=days)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cardiovascular Digital Twin MVP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run-baseline", help="Run baseline pipeline")
    run_parser.add_argument("--data", default=None, help="Optional CSV path")

    synth_parser = sub.add_parser("generate-synth", help="Generate synthetic multimodal data")
    synth_parser.add_argument("--seed", type=int, default=42)
    synth_parser.add_argument("--days", type=int, default=180)
    synth_parser.add_argument("--data", default=None, help="Optional CSV path")

    update_parser = sub.add_parser("update-loop", help="Run digital twin daily update loop")
    update_parser.add_argument("--days", type=int, default=30)

    args = parser.parse_args()
    if args.command == "run-baseline":
        run_baseline(args.data)
    elif args.command == "generate-synth":
        run_synth(seed=args.seed, days=args.days, data_path=args.data)
    elif args.command == "update-loop":
        run_updates(days=args.days)


if __name__ == "__main__":
    main()
