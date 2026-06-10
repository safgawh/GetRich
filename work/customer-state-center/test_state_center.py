from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from state_center import StateCenter


class StateCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.center = StateCenter(Path(self.tmp.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self.center.close()
        self.tmp.cleanup()

    def test_new_customer_is_idempotent_for_send_link(self) -> None:
        first = self.center.handle_event("NEW_CUSTOMER", "c1")
        second = self.center.handle_event("NEW_CUSTOMER", "c1")

        self.assertEqual(first["actions"][0]["action_type"], "SEND_LINK")
        self.assertEqual(second["actions"], [])
        pending_send_links = [a for a in self.center.list_actions("pending") if a["action_type"] == "SEND_LINK"]
        self.assertEqual(len(pending_send_links), 1)

    def test_partial_info_merges_with_existing_fields(self) -> None:
        self.center.handle_event("NEW_CUSTOMER", "c2")
        self.center.handle_event("LINK_CLICKED", "c2")
        first = self.center.handle_event("CUSTOMER_MESSAGE", "c2", {"text": "张三"})
        self.assertEqual(first["customer_task"]["current_status"], "INFO_INCOMPLETE")
        self.assertIn("birth_year", first["customer_task"]["missing_fields"])

        second = self.center.handle_event("CUSTOMER_MESSAGE", "c2", {"text": "1998年5月12日"})
        self.assertEqual(second["customer_task"]["current_status"], "REGISTERED")
        self.assertEqual(second["customer_task"]["customer_name"], "张三")
        self.assertEqual(second["customer_task"]["birth_year"], "1998")
        self.assertFalse(second["customer_task"]["missing_fields"])
        self.assertTrue(any(a["action_type"] == "REGISTER_CUSTOMER" for a in second["actions"]))

    def test_link_click_after_waiting_link_click_registers_immediately(self) -> None:
        self.center.handle_event("NEW_CUSTOMER", "c3")
        first = self.center.handle_event("CUSTOMER_MESSAGE", "c3", {"text": "李四，2001年8月12日"})
        self.assertEqual(first["customer_task"]["current_status"], "WAITING_LINK_CLICK")
        self.assertTrue(any(a["action_type"] == "CHECK_LINK_CLICKED_AFTER_2MIN" for a in first["actions"]))

        second = self.center.handle_event("LINK_CLICKED", "c3")
        self.assertEqual(second["customer_task"]["current_status"], "REGISTERED")
        self.assertTrue(any(a["action_type"] == "REGISTER_CUSTOMER" for a in second["actions"]))
        pending_checks = [a for a in self.center.list_actions("pending") if a["action_type"] == "CHECK_LINK_CLICKED_AFTER_2MIN"]
        self.assertEqual(pending_checks, [])

    def test_messages_before_link_click_only_prompt_link(self) -> None:
        self.center.handle_event("NEW_CUSTOMER", "c6")
        result = self.center.handle_event("CUSTOMER_MESSAGE", "c6", {"text": "【红包】", "red_packet": True})
        action_types = [a["action_type"] for a in result["actions"]]

        self.assertEqual(result["customer_task"]["current_status"], "WAITING_LINK_CLICK")
        self.assertIn("ASK_CLICK_LINK", action_types)
        self.assertIn("CHECK_LINK_CLICKED_AFTER_2MIN", action_types)
        self.assertNotIn("SEND_RED_PACKET_REPLY", action_types)

        checked = self.center.handle_event("CHECK_LINK_CLICKED_AFTER_2MIN", "c6")
        self.assertEqual(checked["customer_task"]["current_status"], "FINISHED")
        self.assertEqual(checked["customer_task"]["final_status"], "FINISHED")
        self.assertEqual(self.center.list_actions("pending"), [])

    def test_video_success_schedules_payment_link_after_six_minutes(self) -> None:
        self.center.handle_event("NEW_CUSTOMER", "c4")
        self.center.handle_event("LINK_CLICKED", "c4")
        self.center.handle_event("CUSTOMER_MESSAGE", "c4", {"text": "王五，1999年6月1日"})
        send_video = next(a for a in self.center.list_actions("pending") if a["action_type"] == "SEND_VIDEO")

        self.center.complete_action(send_video["id"], "success", {"payment_link": "https://pay.example/1"})
        task = self.center.get_customer_by_customer_id("c4")
        self.assertEqual(task.current_status, "WAITING_PAYMENT_LINK")
        self.assertIsNotNone(task.video_sent_at)
        payment_actions = [a for a in self.center.list_actions("pending") if a["action_type"] == "SEND_PAYMENT_LINK"]
        self.assertEqual(len(payment_actions), 1)
        self.assertEqual(payment_actions[0]["payload"]["payment_link"], "https://pay.example/1")
        due_actions = [a for a in self.center.list_actions("pending", due_only=True) if a["action_type"] == "SEND_PAYMENT_LINK"]
        self.assertEqual(due_actions, [])

    def test_customer_deleted_finishes_and_cancels_pending_actions(self) -> None:
        self.center.handle_event("NEW_CUSTOMER", "c5")
        self.center.handle_event("LINK_CLICKED", "c5")
        self.center.handle_event("CUSTOMER_MESSAGE", "c5", {"text": "赵六，1997年7月2日"})
        self.assertTrue(self.center.list_actions("pending"))

        result = self.center.handle_event("CUSTOMER_DELETED", "c5")
        self.assertEqual(result["customer_task"]["current_status"], "CUSTOMER_DELETED")
        self.assertEqual(result["customer_task"]["final_status"], "FINISHED")
        self.assertEqual(self.center.list_actions("pending"), [])

        ignored = self.center.handle_event("CUSTOMER_MESSAGE", "c5", {"text": "怎么化解？"})
        self.assertTrue(ignored["ignored"])


if __name__ == "__main__":
    unittest.main()
