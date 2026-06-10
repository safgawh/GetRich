from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    result: dict[str, Any]

    @classmethod
    def success(cls, **result: Any) -> "ExecutionResult":
        return cls(status="success", result=result)

    @classmethod
    def failed(cls, error_code: str, reason: str) -> "ExecutionResult":
        return cls(status="failed", result={"error_code": error_code, "reason": reason})


class SimulatedActionAdapter:
    """Replace this adapter with real WeCom/RPA/video/payment integrations later."""

    message_action_types = {
        "SEND_LINK",
        "ASK_FOR_IMAGE_INFO",
        "ASK_MISSING_BIRTHDAY",
        "ASK_MISSING_NAME",
        "ASK_CLICK_LINK",
        "SEND_WAIT_20_MIN_MESSAGE",
        "SEND_PAYMENT_LINK",
        "SEND_RED_PACKET_REPLY",
        "ASK_DONATION_AMOUNT",
    }

    def __init__(self, customer_deleted_action_ids: set[str] | None = None, dry_run: bool = False):
        self.customer_deleted_action_ids = customer_deleted_action_ids or set()
        self.dry_run = dry_run

    def execute(self, action: dict[str, Any]) -> ExecutionResult:
        action_id = str(action["id"])
        action_type = str(action["action_type"])
        payload = action.get("payload") or {}

        if action_id in self.customer_deleted_action_ids:
            return ExecutionResult.failed("CUSTOMER_DELETED", "客户已删除或无法触达")

        if action_type in self.message_action_types:
            return self.send_message(action_id, action_type, payload)
        if action_type == "REGISTER_CUSTOMER":
            return self.register_customer(action_id, payload)
        if action_type == "CREATE_VIDEO":
            return self.create_video(action_id, payload)
        if action_type == "SEND_VIDEO":
            return self.send_video(action_id, payload)
        if action_type == "SEND_PAYMENT_QR":
            return self.send_payment_qr(action_id, payload)
        if action_type == "FINISH_TASK":
            return self.finish_task(payload)

        return ExecutionResult.failed("UNSUPPORTED_ACTION_TYPE", f"unsupported action_type: {action_type}")

    def send_message(self, action_id: str, action_type: str, payload: dict[str, Any]) -> ExecutionResult:
        result: dict[str, Any] = {
            "message_id": self.stable_id("MSG", action_id),
            "channel": "simulated_wecom",
            "action_type": action_type,
            "dry_run": self.dry_run,
        }
        if "link_id" in payload:
            result["link_id"] = payload["link_id"]
        if "payment_link" in payload:
            result["payment_link"] = payload["payment_link"]
        return ExecutionResult.success(**result)

    def register_customer(self, action_id: str, payload: dict[str, Any]) -> ExecutionResult:
        customer = payload.get("customer") or {}
        return ExecutionResult.success(
            registration_id=self.stable_id("REG", action_id),
            customer_task_id=customer.get("id") or payload.get("customer_task_id"),
            dry_run=self.dry_run,
        )

    def create_video(self, action_id: str, payload: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult.success(
            video_task_id=self.stable_id("VD", action_id),
            customer_task_id=payload.get("customer_task_id"),
            dry_run=self.dry_run,
        )

    def send_video(self, action_id: str, payload: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult.success(
            video_message_id=self.stable_id("VMSG", action_id),
            customer_task_id=payload.get("customer_task_id"),
            payment_link=payload.get("payment_link") or "https://pay.example/simulated",
            dry_run=self.dry_run,
        )

    def send_payment_qr(self, action_id: str, payload: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult.success(
            message_id=self.stable_id("MSG", action_id),
            qr_asset_key=payload.get("asset_key") or "default_payment_qr",
            dry_run=self.dry_run,
        )

    def finish_task(self, payload: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult.success(
            reason=payload.get("reason") or "任务已结束",
            finished_at=datetime.now(TZ).isoformat(timespec="seconds"),
            dry_run=self.dry_run,
        )

    def stable_id(self, prefix: str, value: str) -> str:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
        return f"{prefix}_{digest}"
