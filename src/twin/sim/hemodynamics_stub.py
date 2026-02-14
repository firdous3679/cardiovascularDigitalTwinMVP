from __future__ import annotations

# Placeholder only for MVP research workflow. Not physiologically validated.


def simulate_hemodynamics_stub(age: float, hr: float, sbp: float, dbp: float) -> dict[str, float]:
    map_est = dbp + (sbp - dbp) / 3.0
    pulse_pressure = max(sbp - dbp, 1.0)
    compliance_proxy = max(0.1, (1.0 / pulse_pressure) * (70.0 / max(age, 18.0)))
    cardiac_strain_proxy = (hr / 60.0) * (map_est / 93.0)
    return {
        "map_estimate": round(map_est, 3),
        "compliance_proxy": round(compliance_proxy, 5),
        "cardiac_strain_proxy": round(cardiac_strain_proxy, 5),
    }
