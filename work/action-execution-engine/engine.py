from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, parse, request

from adapters import ExecutionResult, SimulatedActionAdapter
from config import EngineConfig


class ActionAdapter(Protocol):
    def execute(self, action: dict[str, Any]) -> ExecutionResult:
        ...


@dataclass
class StateCenterClient:
    base_url: str
    timeout_seconds: float = 10

    def get_due_actions(self) -> list[dict[str, Any]]:
        query = parse.urlencode({"status": "pending", "due": "1"})
        return self._request_json("GET", f"/actions?{query}")

    def get_customer(self, customer_task_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/customers/{parse.quote(customer_task_id)}")

    def complete_action(self, action_id: str, result: ExecutionResult) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/actions/{parse.quote(action_id)}/complete",
            {"status": result.status, "result": result.result},
        )

    def trigger_event(self, event_type: str, customer_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/events",
            {"event_type": event_type, "customer_id": customer_id, "payload": payload or {}},
        )

    def _request_json(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"state center HTTP {exc.code}: {raw}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"cannot reach state center: {exc.reason}") from exc


class ActionExecutionEngine:
    def __init__(self, client: StateCenterClient, adapter: ActionAdapter):
        self.client = client
        self.adapter = adapter

    def run_forever(self, poll_interval_seconds: float = 2) -> None:
        print(f"Action execution engine polling every {poll_interval_seconds:g}s")
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(poll_interval_seconds)

    def run_once(self) -> int:
        actions = self.client.get_due_actions()
        for action in actions:
            self.process_action(action)
        return len(actions)

    def process_action(self, action: dict[str, Any]) -> None:
        action_id = str(action["id"])
        action_type = str(action["action_type"])
        print(f"[engine] executing {action_type} {action_id}")

        if action_type == "CHECK_LINK_CLICKED_AFTER_2MIN":
            result = self.trigger_scheduled_event(action)
        else:
            result = self.adapter.execute(action)

        self.client.complete_action(action_id, result)
        print(f"[engine] completed {action_type} {action_id}: {result.status}")

    def trigger_scheduled_event(self, action: dict[str, Any]) -> ExecutionResult:
        payload = action.get("payload") or {}
        event_type = payload.get("event_type") or action["action_type"]
        customer_id = payload.get("customer_id") or self.resolve_customer_id(action)
        if not customer_id:
            return ExecutionResult.failed("MISSING_CUSTOMER_ID", "scheduled event action has no customer_id")
        response = self.client.trigger_event(event_type, customer_id, payload)
        return ExecutionResult.success(event_type=event_type, customer_id=customer_id, response=response)

    def resolve_customer_id(self, action: dict[str, Any]) -> str | None:
        payload = action.get("payload") or {}
        customer = payload.get("customer") or {}
        customer_id = payload.get("customer_id") or customer.get("customer_id")
        if customer_id:
            return str(customer_id)
        customer_task_id = action.get("customer_task_id")
        if not customer_task_id:
            return None
        customer_data = self.client.get_customer(str(customer_task_id))
        return customer_data.get("customer_id")


def build_engine(config: EngineConfig | None = None) -> ActionExecutionEngine:
    config = config or EngineConfig.from_env()
    client = StateCenterClient(config.state_center_base_url)
    adapter = SimulatedActionAdapter(
        customer_deleted_action_ids=config.simulate_customer_deleted_action_ids,
        dry_run=config.dry_run,
    )
    return ActionExecutionEngine(client, adapter)


def main() -> None:
    config = EngineConfig.from_env()
    print(f"State center: {config.state_center_base_url}")
    print(f"Dry run: {config.dry_run}")
    build_engine(config).run_forever(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
