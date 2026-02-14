from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


def _read_records(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))["rows"]


def _load_twin_states(state_root: Path):
    rows = []
    for path in sorted(state_root.glob("state_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


st.set_page_config(page_title="Cardiovascular Digital Twin MVP", layout="wide")
st.title("Cardiovascular Digital Twin (Research MVP)")
st.caption("Non-clinical heuristic dashboard. Synthetic data only.")

cohort = _read_records("data/processed/cohort_features.parquet")
patients = [row["patient_id"] for row in cohort]
pid = st.selectbox("Select patient", patients)

wearables = _read_records(f"data/synth/wearables/{pid}.parquet")
patient_states = [r for r in _load_twin_states(Path("data/twin_state")) if r["patient_id"] == pid]

col1, col2 = st.columns(2)
with col1:
    st.subheader("Risk over time")
    if patient_states:
        st.line_chart({"risk": [r["risk"] for r in patient_states]}, x=list(range(len(patient_states))))
    else:
        st.info("No twin state snapshots found. Run `make update`.")

with col2:
    st.subheader("Last 14-day wearable summary")
    last14 = wearables[-14:]
    if last14:
        avg_steps = sum(r["steps"] or 0 for r in last14) / len(last14)
        avg_hr = sum(r["hr"] or 0 for r in last14) / len(last14)
        avg_sbp = sum(r["sbp"] or 0 for r in last14) / len(last14)
        st.metric("Avg steps/day", f"{avg_steps:.0f}")
        st.metric("Avg HR", f"{avg_hr:.1f} bpm")
        st.metric("Avg SBP", f"{avg_sbp:.1f} mmHg")
    else:
        st.info("No wearable data")

st.subheader("EHR event timeline")
counts = {}
sample_events = []
for resource_file in Path("data/synth/fhir_ndjson").glob("*.ndjson"):
    for line in resource_file.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        subj = event.get("subject", {}).get("reference", "")
        if subj.endswith(pid):
            ts = event.get("period", {}).get("start") or event.get("effectiveDateTime") or event.get("authoredOn") or event.get("recordedDate") or event.get("performedDateTime")
            day = ts[:10]
            counts[day] = counts.get(day, 0) + 1
            if len(sample_events) < 6:
                sample_events.append(event)

if counts:
    ordered = sorted(counts.items())
    st.bar_chart({"events": [v for _, v in ordered]}, x=[k for k, _ in ordered])
else:
    st.write("No EHR events for selected patient.")

with st.expander("Sample events"):
    st.json(sample_events)

st.subheader("What-if heuristic controls")
delta_bp = st.slider("Reduce SBP (mmHg)", min_value=0, max_value=30, value=10)
delta_steps = st.slider("Increase daily steps", min_value=0, max_value=6000, value=1500, step=250)
base_risk = patient_states[-1]["risk"] if patient_states else 0.4
adjusted_risk = max(0.01, min(0.99, base_risk - (delta_bp * 0.003) - (delta_steps / 100000)))
st.write(f"Heuristic adjusted risk: **{adjusted_risk:.3f}** (baseline {base_risk:.3f})")
st.caption("Risk perturbation above is a simplified educational heuristic, not a clinical model.")
