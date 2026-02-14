from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TwinState:
    patient_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    risk: float = 0.0
    notes: str | None = None
    metadata: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "TwinState":
        return cls(**json.loads(payload))
