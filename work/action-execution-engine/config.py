from __future__ import annotations

import os
from dataclasses import dataclass


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


@dataclass(frozen=True)
class EngineConfig:
    state_center_base_url: str
    poll_interval_seconds: float
    dry_run: bool
    simulate_customer_deleted_action_ids: set[str]

    @classmethod
    def from_env(cls) -> "EngineConfig":
        return cls(
            state_center_base_url=os.getenv("STATE_CENTER_BASE_URL", "http://127.0.0.1:8787").rstrip("/"),
            poll_interval_seconds=float(os.getenv("POLL_INTERVAL_SECONDS", "2")),
            dry_run=parse_bool(os.getenv("DRY_RUN"), default=False),
            simulate_customer_deleted_action_ids=parse_csv(os.getenv("SIMULATE_CUSTOMER_DELETED_ACTION_IDS")),
        )
