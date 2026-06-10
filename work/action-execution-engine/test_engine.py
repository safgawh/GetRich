from __future__ import annotations

import unittest
from typing import Any

from adapters import ExecutionResult, SimulatedActionAdapter
from engine import ActionExecutionEngine


class FakeClient:
    def __init__(self, actions: list[dict[str, Any]], customers: dict[str, dict[str, Any]] | None = None):
        self.actions = actions
        self.customers = customers or {}
        self.completed: list[tuple[str, ExecutionResult]] = []
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def get_due_actions(self) -> list[dict[str, Any]]:
        return list(self.actions)

    def complete_action(self, action_id: str, result: ExecutionResult) -> dict[str, Any]:
        self.completed.append((action_id, result))
        return {"id": action_id, "status": result.status, "result": result.result}

    def get_customer(self, customer_task_id: str) -> dict[str, Any]:
        return self.customers[customer_task_id]

    def trigger_event(self, event_type: str, customer_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.events.append((event_type, customer_id, payload or {}))
        return {"ok": True, "event_type": event_type}


def action(action_type: str, payload: dict[str, Any] | None = None, action_id: str | None = None) -> dict[str, Any]:
    return {
        "id": action_id or f"AT_{action_type}",
        "customer_task_id": "CT_1",
        "action_type": action_type,
        "payload": payload or {},
    }


class ActionExecutionEngineTests(unittest.TestCase):
    def test_message_action_completes_successfully(self) -> None:
        client = FakeClient([action("SEND_LINK", {"text": "点链接参与排队", "link_id": "LK_1"})])
        engine = ActionExecutionEngine(client, SimulatedActionAdapter())

        processed = engine.run_once()

        self.assertEqual(processed, 1)
        self.assertEqual(len(client.completed), 1)
        action_id, result = client.completed[0]
        self.assertEqual(action_id, "AT_SEND_LINK")
        self.assertEqual(result.status, "success")
        self.assertIn("message_id", result.result)
        self.assertEqual(result.result["link_id"], "LK_1")

    def test_all_main_action_types_have_success_handlers(self) -> None:
        action_types = [
            "SEND_LINK",
            "ASK_FOR_IMAGE_INFO",
            "ASK_MISSING_BIRTHDAY",
            "ASK_MISSING_NAME",
            "ASK_CLICK_LINK",
            "REGISTER_CUSTOMER",
            "SEND_WAIT_20_MIN_MESSAGE",
            "CREATE_VIDEO",
            "SEND_VIDEO",
            "SEND_PAYMENT_LINK",
            "SEND_PAYMENT_QR",
            "SEND_RED_PACKET_REPLY",
            "ASK_DONATION_AMOUNT",
            "FINISH_TASK",
        ]
        client = FakeClient([action(action_type) for action_type in action_types])
        engine = ActionExecutionEngine(client, SimulatedActionAdapter())

        processed = engine.run_once()

        self.assertEqual(processed, len(action_types))
        self.assertEqual(len(client.completed), len(action_types))
        self.assertTrue(all(result.status == "success" for _, result in client.completed))

    def test_simulated_customer_deleted_failure_is_reported(self) -> None:
        client = FakeClient([action("SEND_LINK", action_id="AT_DELETE_ME")])
        engine = ActionExecutionEngine(client, SimulatedActionAdapter(customer_deleted_action_ids={"AT_DELETE_ME"}))

        engine.run_once()

        _, result = client.completed[0]
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.result["error_code"], "CUSTOMER_DELETED")
        self.assertEqual(result.result["reason"], "客户已删除或无法触达")

    def test_check_link_action_triggers_event_instead_of_adapter(self) -> None:
        client = FakeClient(
            [
                action(
                    "CHECK_LINK_CLICKED_AFTER_2MIN",
                    {"event_type": "CHECK_LINK_CLICKED_AFTER_2MIN", "customer_id": "wx_customer_1"},
                )
            ]
        )
        engine = ActionExecutionEngine(client, SimulatedActionAdapter())

        engine.run_once()

        self.assertEqual(client.events, [("CHECK_LINK_CLICKED_AFTER_2MIN", "wx_customer_1", {"event_type": "CHECK_LINK_CLICKED_AFTER_2MIN", "customer_id": "wx_customer_1"})])
        _, result = client.completed[0]
        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["event_type"], "CHECK_LINK_CLICKED_AFTER_2MIN")

    def test_check_link_action_can_resolve_customer_id_from_customer_task(self) -> None:
        client = FakeClient(
            [action("CHECK_LINK_CLICKED_AFTER_2MIN", {"event_type": "CHECK_LINK_CLICKED_AFTER_2MIN"})],
            customers={"CT_1": {"id": "CT_1", "customer_id": "wx_customer_from_task"}},
        )
        engine = ActionExecutionEngine(client, SimulatedActionAdapter())

        engine.run_once()

        self.assertEqual(client.events[0][1], "wx_customer_from_task")
        _, result = client.completed[0]
        self.assertEqual(result.status, "success")

    def test_unknown_action_type_reports_failed_result(self) -> None:
        client = FakeClient([action("UNKNOWN_ACTION")])
        engine = ActionExecutionEngine(client, SimulatedActionAdapter())

        engine.run_once()

        _, result = client.completed[0]
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.result["error_code"], "UNSUPPORTED_ACTION_TYPE")


if __name__ == "__main__":
    unittest.main()
