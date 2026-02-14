from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def write_summary(metrics: dict[str, float], output_path: str | Path = "reports/summary.md") -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Baseline Evaluation Summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in ["auroc", "auprc", "accuracy", "f1", "brier_score"]:
        lines.append(f"| {key} | {metrics[key]:.4f} |")

    lines.append("")
    lines.append("> Research MVP only. This project is non-clinical and must not be used for diagnosis or treatment decisions.")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
