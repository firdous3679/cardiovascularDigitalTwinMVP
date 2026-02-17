from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Event:
    step: int
    event_type: str
    actor_id: int
    resource: str
    action: str
    label: str = "benign"
    scenario: str | None = None
    phase: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class TrafficTwin:
    def __init__(self, service: str = "traffic", degrade_threshold: float = 0.25):
        self.service = service
        self.degrade_threshold = degrade_threshold
        self.severity = 0.0
        self.degraded = False
        self.cause_actor_id: int | None = None

    def step(self, model: "InsiderModel") -> None:
        self.severity = max(0.0, self.severity - 0.015)
        for event in model.action_events:
            if event.event_type != "cps_command":
                continue
            cmd = event.meta.get("cmd")
            if cmd == "PUSH_TIMING_PLAN":
                self.severity = max(self.severity, float(event.meta.get("severity_inc", 0.9)))
                if event.actor_id >= 0:
                    self.cause_actor_id = event.actor_id
            elif cmd == "TWEAK_OFFSET":
                self.severity = min(1.0, self.severity + float(event.meta.get("severity_inc", 0.03)))
                if event.actor_id >= 0:
                    self.cause_actor_id = event.actor_id
            elif cmd == "ROLLBACK_PLAN":
                self.severity = max(0.0, self.severity - 0.3)
                if self.severity < self.degrade_threshold:
                    self.cause_actor_id = None
        self.degraded = self.severity >= self.degrade_threshold
        model.emit_action(
            Event(
                step=model.step_idx,
                event_type="cps_service_state",
                actor_id=-1,
                resource="traffic_corridor_A",
                action="service_state",
                label="benign",
                meta={
                    "service": self.service,
                    "degraded": self.degraded,
                    "severity": round(self.severity, 4),
                    "cause_actor_id": self.cause_actor_id,
                },
            )
        )


class MaliciousInsider:
    def __init__(self, unique_id: int, scenario: str, rng: random.Random):
        self.unique_id = unique_id
        self.scenario = scenario
        self.rng = rng

    def act(self, model: "InsiderModel") -> None:
        if self.scenario == "acct_takeover":
            if self.rng.random() < 0.20:
                model.emit_action(
                    Event(model.step_idx, "auth", self.unique_id, "admin_console", "after_hours_login", "malicious", self.scenario)
                )
            if self.rng.random() < 0.12:
                model.emit_action(
                    Event(
                        model.step_idx,
                        "cps_command",
                        self.unique_id,
                        "traffic_corridor_A",
                        "PUSH_TIMING_PLAN",
                        "malicious",
                        self.scenario,
                        meta={"service": "traffic", "cmd": "PUSH_TIMING_PLAN", "severity_inc": 0.85, "unsafe": True},
                    )
                )
        elif self.scenario == "stealth":
            if self.rng.random() < 0.07:
                model.emit_action(
                    Event(model.step_idx, "db_query", self.unique_id, "citizen_db", "suspicious_query", "malicious", self.scenario)
                )
            if self.rng.random() < 0.10:
                model.emit_action(
                    Event(
                        model.step_idx,
                        "cps_command",
                        self.unique_id,
                        "traffic_corridor_A",
                        "TWEAK_OFFSET",
                        "malicious",
                        self.scenario,
                        meta={"service": "traffic", "cmd": "TWEAK_OFFSET", "severity_inc": 0.03},
                    )
                )
        elif self.scenario == "staging_exfil":
            if self.rng.random() < 0.09:
                model.emit_action(Event(model.step_idx, "file_access", self.unique_id, "share", "zip_batch", "malicious", self.scenario))
        elif self.scenario == "exfil":
            if self.rng.random() < 0.11:
                model.emit_action(Event(model.step_idx, "network", self.unique_id, "egress", "bulk_upload", "malicious", self.scenario))
        elif self.scenario == "email_only":
            if self.rng.random() < 0.08:
                model.emit_action(Event(model.step_idx, "email", self.unique_id, "mail", "phish_send", "malicious", self.scenario))


class InsiderModel:
    def __init__(self, seed: int, warmup_steps: int = 60, test_steps: int = 240, threshold: int = 4):
        self.rng = random.Random(seed)
        self.threshold = threshold
        self.warmup_steps = warmup_steps
        self.test_steps = test_steps
        self.total_steps = warmup_steps + test_steps
        self.step_idx = 0
        self.events: list[dict[str, Any]] = []
        self.action_events: list[Event] = []
        scenarios = ["acct_takeover", "stealth", "staging_exfil", "exfil", "email_only"]
        self.attackers = [MaliciousInsider(i, s, self.rng) for i, s in enumerate(scenarios)]
        self.traffic_twin = TrafficTwin(service="traffic", degrade_threshold=0.25)

    def _tag_phase(self, event: Event) -> None:
        event.phase = "train" if self.step_idx < self.warmup_steps else "test"

    def emit_action(self, event: Event) -> None:
        self._tag_phase(event)
        self.action_events.append(event)
        self.events.append(asdict(event))

    def _emit_benign_background(self) -> None:
        for actor_id in range(5, 12):
            if self.rng.random() < 0.2:
                self.emit_action(Event(self.step_idx, "auth", actor_id, "vpn", "login", "benign"))

    def _run_monitors(self) -> None:
        suspicious = sum(1 for e in self.action_events if e.label == "malicious" and e.actor_id >= 0)
        if suspicious >= self.threshold:
            suspects = sorted({e.actor_id for e in self.action_events if e.label == "malicious" and e.actor_id >= 0})
            for a in suspects:
                self.emit_action(Event(self.step_idx, "alert_confirmed", a, "siem", "confirm", "benign"))

    def step(self) -> None:
        self.action_events = []
        self._emit_benign_background()
        for attacker in self.attackers:
            attacker.act(self)
        self.traffic_twin.step(self)
        self._run_monitors()
        if any(e.event_type == "alert_confirmed" for e in self.action_events):
            self.emit_action(
                Event(
                    self.step_idx,
                    "cps_command",
                    -1,
                    "traffic_corridor_A",
                    "ROLLBACK_PLAN",
                    "benign",
                    meta={"service": "traffic", "cmd": "ROLLBACK_PLAN"},
                )
            )
        self.step_idx += 1


def run_simulation(seed: int, warmup_steps: int = 60, test_steps: int = 240, threshold: int = 4) -> list[dict[str, Any]]:
    model = InsiderModel(seed=seed, warmup_steps=warmup_steps, test_steps=test_steps, threshold=threshold)
    for _ in range(model.total_steps):
        model.step()
    return model.events
