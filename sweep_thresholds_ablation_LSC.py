from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd

CPS_STATE_TYPE = "cps_service_state"
SCENARIO_IMPACT = {
    "acct_takeover": 1.0,
    "stealth": 0.6,
    "staging_exfil": 0.75,
    "exfil": 0.8,
    "email_only": 0.5,
}


def filter_to_test(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("phase") == "test"]


def compute_cps_metrics(events: list[dict], service: str = "traffic"):
    cps_states = [
        e
        for e in events
        if e.get("event_type") == CPS_STATE_TYPE and isinstance(e.get("meta"), dict) and e["meta"].get("service") == service
    ]
    cps_states.sort(key=lambda x: int(x.get("step", 0)))
    degraded_flags = [bool(e.get("meta", {}).get("degraded", False)) for e in cps_states]
    sdp = 1.0 if any(degraded_flags) else 0.0

    durations = []
    run_len = 0
    for d in degraded_flags:
        if d:
            run_len += 1
        elif run_len > 0:
            durations.append(run_len)
            run_len = 0
    if run_len > 0:
        durations.append(run_len)

    avg_dur = float(sum(durations) / len(durations)) if durations else 0.0
    severity_by_actor: dict[int, float] = {}
    for e in cps_states:
        meta = e.get("meta", {})
        cause = meta.get("cause_actor_id")
        sev = float(meta.get("severity", 0.0))
        if cause is None:
            continue
        try:
            cause = int(cause)
        except (TypeError, ValueError):
            continue
        if cause < 0:
            continue
        severity_by_actor[cause] = max(severity_by_actor.get(cause, 0.0), sev)

    return sdp, avg_dur, severity_by_actor


def eval_from_events(events: list[dict]) -> dict:
    events = filter_to_test(events)
    actors = sorted({int(e["actor_id"]) for e in events if "actor_id" in e and int(e["actor_id"]) >= 0})
    scenario_by_actor = {}
    for e in events:
        if e.get("actor_id") is not None and int(e["actor_id"]) >= 0 and e.get("scenario"):
            scenario_by_actor[int(e["actor_id"])] = e.get("scenario")

    malicious = {int(e["actor_id"]) for e in events if e.get("label") == "malicious" and int(e.get("actor_id", -1)) >= 0}
    confirmed = {int(e["actor_id"]) for e in events if e.get("event_type") == "alert_confirmed" and int(e.get("actor_id", -1)) >= 0}

    tp = len(malicious & confirmed)
    fp = len(confirmed - malicious)
    fn = len(malicious - confirmed)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    actor_f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    first_mal_step = {}
    first_conf_step = {}
    for e in events:
        aid = int(e.get("actor_id", -1))
        if aid < 0:
            continue
        if e.get("label") == "malicious":
            first_mal_step.setdefault(aid, int(e.get("step", 0)))
        if e.get("event_type") == "alert_confirmed":
            first_conf_step.setdefault(aid, int(e.get("step", 0)))

    ttd_values = [first_conf_step[a] - first_mal_step[a] for a in malicious if a in first_conf_step and a in first_mal_step]
    mean_ttd = sum(ttd_values) / len(ttd_values) if ttd_values else None

    last_test_step = max([int(e.get("step", 0)) for e in events], default=0)
    cps_sdp, avg_dur, severity_by_actor = compute_cps_metrics(events, service="traffic")

    iw_num = 0.0
    iw_den = 0.0
    for a in malicious:
        if a not in first_mal_step:
            continue
        ttd_i = first_conf_step[a] - first_mal_step[a] if a in first_conf_step else last_test_step - first_mal_step[a]
        w_i = severity_by_actor.get(a)
        if w_i is None:
            w_i = SCENARIO_IMPACT.get(scenario_by_actor.get(a, ""), 0.5)
        iw_num += w_i * ttd_i
        iw_den += w_i
    iw_ttd = iw_num / iw_den if iw_den > 0 else None

    return {
        "num_actors": len(actors),
        "num_mal_actors": len(malicious),
        "actor_precision": prec,
        "actor_recall": rec,
        "actor_f1": actor_f1,
        "mean_ttd": mean_ttd,
        "iw_ttd": iw_ttd,
        "sdp": cps_sdp,
        "avg_degraded_mode_duration": avg_dur,
    }


def load_model(path: str):
    spec = importlib.util.spec_from_file_location("mini_model", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["mini_model"] = module
    spec.loader.exec_module(module)
    return module


def run_sweep(args):
    module = load_model(args.model)
    rows = []
    for threshold in range(args.threshold_min, args.threshold_max + 1):
        for seed in range(args.seeds):
            events = module.run_simulation(
                seed=seed,
                warmup_steps=args.warmup_steps,
                test_steps=args.test_steps,
                threshold=threshold,
            )
            metrics = eval_from_events(events)
            rows.append({"threshold": threshold, "seed": seed, **metrics})

    df = pd.DataFrame(rows)
    summary = (
        df.groupby("threshold", as_index=False)
        .agg(
            actor_precision=("actor_precision", "mean"),
            actor_recall=("actor_recall", "mean"),
            actor_f1=("actor_f1", "mean"),
            mean_ttd=("mean_ttd", "mean"),
            iw_ttd=("iw_ttd", "mean"),
            sdp=("sdp", "mean"),
            avg_degraded_mode_duration=("avg_degraded_mode_duration", "mean"),
        )
    )
    summary.to_csv(args.out, index=False)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--warmup_steps", type=int, default=60)
    parser.add_argument("--test_steps", type=int, default=240)
    parser.add_argument("--threshold_min", type=int, default=3)
    parser.add_argument("--threshold_max", type=int, default=7)
    args = parser.parse_args()

    run_sweep(args)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
