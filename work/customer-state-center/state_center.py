from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def after_seconds(seconds: int) -> str:
    return (datetime.now(TZ) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


STATUSES = {
    "NEW_CUSTOMER",
    "LINK_SENT",
    "LINK_CLICKED",
    "WAITING_INFO",
    "INFO_INCOMPLETE",
    "WAITING_LINK_CLICK",
    "REGISTERED",
    "WAITING_VIDEO",
    "VIDEO_SENT",
    "WAITING_PAYMENT_LINK",
    "PAYMENT_LINK_SENT",
    "PAYMENT_FAILED",
    "QR_SENT",
    "RED_PACKET_RECEIVED",
    "RESOLUTION_ASKED",
    "CUSTOMER_DELETED",
    "FINISHED",
}


ACTION_TYPES = {
    "SEND_LINK",
    "ASK_FOR_IMAGE_INFO",
    "ASK_MISSING_BIRTHDAY",
    "ASK_MISSING_NAME",
    "ASK_CLICK_LINK",
    "CHECK_LINK_CLICKED_AFTER_2MIN",
    "SEND_WAIT_20_MIN_MESSAGE",
    "REGISTER_CUSTOMER",
    "CREATE_VIDEO",
    "SEND_VIDEO",
    "SEND_PAYMENT_LINK",
    "SEND_PAYMENT_QR",
    "SEND_RED_PACKET_REPLY",
    "ASK_DONATION_AMOUNT",
    "FINISH_TASK",
}


@dataclass
class CustomerTask:
    id: str
    customer_id: str
    current_status: str
    link_id: str | None
    link_sent_at: str | None
    link_clicked: bool
    link_clicked_at: str | None
    useful_info_received: bool
    info_complete: bool
    missing_fields: list[str]
    customer_name: str | None
    birth_year: str | None
    birth_month: str | None
    birth_day: str | None
    registered_at: str | None
    wait_message_sent_at: str | None
    video_task_id: str | None
    video_sent_at: str | None
    payment_link_sent_at: str | None
    deleted_by_customer: bool
    final_status: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CustomerTask":
        data = dict(row)
        data["link_clicked"] = bool(data["link_clicked"])
        data["useful_info_received"] = bool(data["useful_info_received"])
        data["info_complete"] = bool(data["info_complete"])
        data["deleted_by_customer"] = bool(data["deleted_by_customer"])
        data["missing_fields"] = json.loads(data["missing_fields"] or "[]")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "current_status": self.current_status,
            "link_id": self.link_id,
            "link_sent_at": self.link_sent_at,
            "link_clicked": self.link_clicked,
            "link_clicked_at": self.link_clicked_at,
            "useful_info_received": self.useful_info_received,
            "info_complete": self.info_complete,
            "missing_fields": self.missing_fields,
            "customer_name": self.customer_name,
            "birth_year": self.birth_year,
            "birth_month": self.birth_month,
            "birth_day": self.birth_day,
            "registered_at": self.registered_at,
            "wait_message_sent_at": self.wait_message_sent_at,
            "video_task_id": self.video_task_id,
            "video_sent_at": self.video_sent_at,
            "payment_link_sent_at": self.payment_link_sent_at,
            "deleted_by_customer": self.deleted_by_customer,
            "final_status": self.final_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class StateCenter:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_task (
              id TEXT PRIMARY KEY,
              customer_id TEXT NOT NULL UNIQUE,
              current_status TEXT NOT NULL,
              link_id TEXT,
              link_sent_at TEXT,
              link_clicked INTEGER NOT NULL DEFAULT 0,
              link_clicked_at TEXT,
              useful_info_received INTEGER NOT NULL DEFAULT 0,
              info_complete INTEGER NOT NULL DEFAULT 0,
              missing_fields TEXT NOT NULL DEFAULT '[]',
              customer_name TEXT,
              birth_year TEXT,
              birth_month TEXT,
              birth_day TEXT,
              registered_at TEXT,
              wait_message_sent_at TEXT,
              video_task_id TEXT,
              video_sent_at TEXT,
              payment_link_sent_at TEXT,
              deleted_by_customer INTEGER NOT NULL DEFAULT 0,
              final_status TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customer_event (
              id TEXT PRIMARY KEY,
              customer_task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              event_payload TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(customer_task_id) REFERENCES customer_task(id)
            );

            CREATE TABLE IF NOT EXISTS action_task (
              id TEXT PRIMARY KEY,
              customer_task_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              payload TEXT NOT NULL,
              status TEXT NOT NULL,
              scheduled_at TEXT NOT NULL,
              executed_at TEXT,
              result TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(customer_task_id) REFERENCES customer_task(id)
            );
            """
        )
        self.conn.commit()

    def create_customer(self, customer_id: str) -> CustomerTask:
        existing = self.get_customer_by_customer_id(customer_id)
        if existing:
            return existing
        ts = now_iso()
        task_id = new_id("CT")
        self.conn.execute(
            """
            INSERT INTO customer_task (
              id, customer_id, current_status, missing_fields, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, customer_id, "NEW_CUSTOMER", "[]", ts, ts),
        )
        self.conn.commit()
        return self.get_customer(task_id)

    def restart_customer(self, task: CustomerTask) -> CustomerTask:
        self.cancel_pending_actions(task.id)
        return self.update_customer(
            task,
            current_status="NEW_CUSTOMER",
            link_id=None,
            link_sent_at=None,
            link_clicked=False,
            link_clicked_at=None,
            useful_info_received=False,
            info_complete=False,
            missing_fields=[],
            customer_name=None,
            birth_year=None,
            birth_month=None,
            birth_day=None,
            registered_at=None,
            wait_message_sent_at=None,
            video_task_id=None,
            video_sent_at=None,
            payment_link_sent_at=None,
            deleted_by_customer=False,
            final_status=None,
        )

    def get_customer(self, task_id: str) -> CustomerTask:
        row = self.conn.execute("SELECT * FROM customer_task WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise KeyError(f"customer_task not found: {task_id}")
        return CustomerTask.from_row(row)

    def get_customer_by_customer_id(self, customer_id: str) -> CustomerTask | None:
        row = self.conn.execute("SELECT * FROM customer_task WHERE customer_id = ?", (customer_id,)).fetchone()
        return CustomerTask.from_row(row) if row else None

    def list_customers(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM customer_task ORDER BY created_at DESC").fetchall()
        return [CustomerTask.from_row(row).to_dict() for row in rows]

    def list_actions(self, status: str | None = None, due_only: bool = False) -> list[dict[str, Any]]:
        params: list[Any] = []
        conditions: list[str] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if due_only:
            conditions.append("scheduled_at <= ?")
            params.append(now_iso())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(f"SELECT * FROM action_task {where} ORDER BY scheduled_at ASC", params).fetchall()
        return [self.action_row_to_dict(row) for row in rows]

    def find_pending_action(self, task_id: str, action_type: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM action_task
            WHERE customer_task_id = ?
              AND action_type = ?
              AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id, action_type),
        ).fetchone()
        return self.action_row_to_dict(row) if row else None

    def action_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["payload"] = json.loads(data["payload"] or "{}")
        data["result"] = json.loads(data["result"] or "null")
        return data

    def record_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO customer_event (id, customer_task_id, event_type, event_payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_id("EV"), task_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
        )
        self.conn.commit()

    def update_customer(self, task: CustomerTask, **changes: Any) -> CustomerTask:
        data = task.to_dict()
        data.update(changes)
        data["updated_at"] = now_iso()
        fields = [
            "current_status",
            "link_id",
            "link_sent_at",
            "link_clicked",
            "link_clicked_at",
            "useful_info_received",
            "info_complete",
            "missing_fields",
            "customer_name",
            "birth_year",
            "birth_month",
            "birth_day",
            "registered_at",
            "wait_message_sent_at",
            "video_task_id",
            "video_sent_at",
            "payment_link_sent_at",
            "deleted_by_customer",
            "final_status",
            "updated_at",
        ]
        values = []
        for field in fields:
            value = data[field]
            if isinstance(value, bool):
                value = int(value)
            if field == "missing_fields":
                value = json.dumps(value, ensure_ascii=False)
            values.append(value)
        set_clause = ", ".join(f"{field} = ?" for field in fields)
        self.conn.execute(f"UPDATE customer_task SET {set_clause} WHERE id = ?", (*values, task.id))
        self.conn.commit()
        return self.get_customer(task.id)

    def create_action(
        self,
        task_id: str,
        action_type: str,
        payload: dict[str, Any] | None = None,
        scheduled_at: str | None = None,
        dedupe: bool = True,
    ) -> dict[str, Any]:
        if action_type not in ACTION_TYPES:
            raise ValueError(f"unknown action_type: {action_type}")
        if dedupe:
            existing = self.find_pending_action(task_id, action_type)
            if existing:
                return existing
        ts = now_iso()
        action_id = new_id("AT")
        self.conn.execute(
            """
            INSERT INTO action_task (
              id, customer_task_id, action_type, payload, status, scheduled_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                task_id,
                action_type,
                json.dumps(payload or {}, ensure_ascii=False),
                "pending",
                scheduled_at or ts,
                ts,
                ts,
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM action_task WHERE id = ?", (action_id,)).fetchone()
        return self.action_row_to_dict(row)

    def complete_action(self, action_task_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        ts = now_iso()
        self.conn.execute(
            """
            UPDATE action_task
            SET status = ?, executed_at = ?, result = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, ts, json.dumps(result or {}, ensure_ascii=False), ts, action_task_id),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM action_task WHERE id = ?", (action_task_id,)).fetchone()
        if not row:
            raise KeyError(f"action_task not found: {action_task_id}")
        action = self.action_row_to_dict(row)
        self.apply_action_result(action, status, result or {})
        return action

    def cancel_pending_actions(self, task_id: str, action_types: list[str] | None = None) -> None:
        if action_types:
            placeholders = ", ".join("?" for _ in action_types)
            self.conn.execute(
                f"""
                UPDATE action_task
                SET status = 'cancelled', updated_at = ?
                WHERE customer_task_id = ?
                  AND status = 'pending'
                  AND action_type IN ({placeholders})
                """,
                (now_iso(), task_id, *action_types),
            )
        else:
            self.conn.execute(
                """
                UPDATE action_task
                SET status = 'cancelled', updated_at = ?
                WHERE customer_task_id = ? AND status = 'pending'
                """,
                (now_iso(), task_id),
            )
        self.conn.commit()

    def handle_event(self, event_type: str, customer_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        task = self.create_customer(customer_id)
        self.record_event(task.id, event_type, payload)

        if task.final_status == "FINISHED" and event_type != "NEW_CUSTOMER":
            return {"customer_task": task.to_dict(), "actions": [], "ignored": True, "reason": "task_already_finished"}

        if event_type == "NEW_CUSTOMER":
            if task.final_status == "FINISHED":
                task = self.restart_customer(task)
            if task.link_sent_at or self.find_pending_action(task.id, "SEND_LINK"):
                return {"customer_task": task.to_dict(), "actions": []}
            task = self.update_customer(task, current_status=task.current_status if task.current_status != "NEW_CUSTOMER" else "NEW_CUSTOMER")
            link_id = task.link_id or new_id("LK")
            action = self.create_action(task.id, "SEND_LINK", {"text": "点链接参与排队", "link_id": link_id})
            task = self.update_customer(task, link_id=action["payload"]["link_id"])
            return {"customer_task": task.to_dict(), "actions": [action]}

        if event_type == "LINK_SENT":
            task = self.update_customer(task, current_status="LINK_SENT", link_sent_at=payload.get("sent_at") or now_iso())
            return {"customer_task": task.to_dict(), "actions": []}

        if event_type == "LINK_CLICKED":
            task = self.update_customer(
                task,
                current_status="LINK_CLICKED",
                link_clicked=True,
                link_clicked_at=payload.get("clicked_at") or now_iso(),
            )
            self.cancel_pending_actions(task.id, ["ASK_CLICK_LINK", "CHECK_LINK_CLICKED_AFTER_2MIN"])
            actions: list[dict[str, Any]] = []
            if task.info_complete and not task.registered_at:
                actions.extend(self.create_registration_actions(task))
                task = self.get_customer(task.id)
            return {"customer_task": task.to_dict(), "actions": actions}

        if event_type == "CUSTOMER_DELETED":
            task = self.finish_task(task, "CUSTOMER_DELETED", "客户已删除或无法触达")
            return {"customer_task": task.to_dict(), "actions": []}

        if event_type == "CUSTOMER_MESSAGE":
            return self.handle_customer_message(task, payload)

        if event_type == "CHECK_LINK_CLICKED_AFTER_2MIN":
            return self.handle_link_check(task)

        raise ValueError(f"unsupported event_type: {event_type}")

    def handle_customer_message(self, task: CustomerTask, payload: dict[str, Any]) -> dict[str, Any]:
        text_value = str(payload.get("text") or "")
        signals = self.detect_message_signals(text_value, payload)
        actions: list[dict[str, Any]] = []
        info = self.merge_customer_info(task, extract_customer_info(text_value, payload))
        missing = missing_fields(info)
        has_useful_info = bool(info["customer_name"] or info["birth_year"] or info["birth_month"] or info["birth_day"])

        if not task.link_clicked:
            task = self.update_customer(
                task,
                current_status="WAITING_LINK_CLICK",
                useful_info_received=has_useful_info,
                info_complete=not missing if has_useful_info else task.info_complete,
                missing_fields=missing if has_useful_info else task.missing_fields,
                customer_name=info["customer_name"] or task.customer_name,
                birth_year=info["birth_year"] or task.birth_year,
                birth_month=info["birth_month"] or task.birth_month,
                birth_day=info["birth_day"] or task.birth_day,
            )
            actions.extend(self.create_link_prompt_actions(task.id))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        if signals["red_packet"]:
            task = self.update_customer(task, current_status="RED_PACKET_RECEIVED")
            actions.append(self.create_action(task.id, "SEND_RED_PACKET_REPLY", {"text": "私人不接受红包，可以扫给上面的道观"}))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        if signals["asks_resolution"]:
            task = self.update_customer(task, current_status="RESOLUTION_ASKED")
            actions.append(self.create_action(task.id, "ASK_DONATION_AMOUNT", {"text": "随喜了多少呢？"}))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        if signals["payment_failed"]:
            task = self.update_customer(task, current_status="PAYMENT_FAILED")
            actions.append(self.create_action(task.id, "SEND_PAYMENT_QR", {"asset_key": "default_payment_qr"}))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        if not has_useful_info:
            task = self.update_customer(task, current_status="WAITING_INFO", useful_info_received=False)
            actions.append(self.create_action(task.id, "ASK_FOR_IMAGE_INFO", {"text": "请把上面图片的信息发我一下"}))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        task = self.update_customer(
            task,
            useful_info_received=True,
            info_complete=not missing,
            missing_fields=missing,
            customer_name=info["customer_name"] or task.customer_name,
            birth_year=info["birth_year"] or task.birth_year,
            birth_month=info["birth_month"] or task.birth_month,
            birth_day=info["birth_day"] or task.birth_day,
        )
        self.cancel_pending_actions(task.id, ["ASK_FOR_IMAGE_INFO", "ASK_MISSING_NAME", "ASK_MISSING_BIRTHDAY"])

        if missing:
            task = self.update_customer(task, current_status="INFO_INCOMPLETE")
            actions.extend(self.actions_for_missing_fields(task.id, missing))
            return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

        actions.extend(self.create_registration_actions(task))
        task = self.get_customer(task.id)
        return {"customer_task": task.to_dict(), "actions": actions, "signals": signals}

    def handle_link_check(self, task: CustomerTask) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        if task.deleted_by_customer or task.final_status == "FINISHED":
            return {"customer_task": task.to_dict(), "actions": actions}
        self.cancel_pending_actions(task.id, ["CHECK_LINK_CLICKED_AFTER_2MIN"])
        if not task.link_clicked:
            task = self.finish_task(task, "FINISHED", "客户未点击链接，结束流程")
        return {"customer_task": task.to_dict(), "actions": actions}

    def merge_customer_info(self, task: CustomerTask, incoming: dict[str, str | None]) -> dict[str, str | None]:
        return {
            "customer_name": incoming.get("customer_name") or task.customer_name,
            "birth_year": incoming.get("birth_year") or task.birth_year,
            "birth_month": incoming.get("birth_month") or task.birth_month,
            "birth_day": incoming.get("birth_day") or task.birth_day,
        }

    def actions_for_missing_fields(self, task_id: str, missing: list[str]) -> list[dict[str, Any]]:
        actions = []
        if "customer_name" in missing:
            actions.append(self.create_action(task_id, "ASK_MISSING_NAME", {"text": "把姓名发我一下"}))
        birthday_missing = {"birth_year", "birth_month", "birth_day"}.intersection(missing)
        if birthday_missing:
            actions.append(self.create_action(task_id, "ASK_MISSING_BIRTHDAY", {"text": "把出生年月日发我一下"}))
        return actions

    def create_link_prompt_actions(self, task_id: str) -> list[dict[str, Any]]:
        actions = []
        if not self.find_pending_action(task_id, "ASK_CLICK_LINK"):
            actions.append(self.create_action(task_id, "ASK_CLICK_LINK", {"text": "点链接参与排队，这会人有点多"}))
        if not self.find_pending_action(task_id, "CHECK_LINK_CLICKED_AFTER_2MIN"):
            actions.append(
                self.create_action(
                    task_id,
                    "CHECK_LINK_CLICKED_AFTER_2MIN",
                    {"event_type": "CHECK_LINK_CLICKED_AFTER_2MIN"},
                    scheduled_at=after_seconds(120),
                )
            )
        return actions

    def create_registration_actions(self, task: CustomerTask) -> list[dict[str, Any]]:
        if task.registered_at:
            return []
        self.cancel_pending_actions(
            task.id,
            [
                "ASK_FOR_IMAGE_INFO",
                "ASK_MISSING_NAME",
                "ASK_MISSING_BIRTHDAY",
                "ASK_CLICK_LINK",
                "CHECK_LINK_CLICKED_AFTER_2MIN",
            ],
        )
        task = self.update_customer(task, current_status="REGISTERED", registered_at=now_iso(), info_complete=True, missing_fields=[])
        return [
            self.create_action(task.id, "REGISTER_CUSTOMER", {"customer": task.to_dict()}),
            self.create_action(task.id, "SEND_WAIT_20_MIN_MESSAGE", {"text": "好的，请稍等20分钟左右"}),
            self.create_action(task.id, "CREATE_VIDEO", {"customer_task_id": task.id}),
            self.create_action(task.id, "SEND_VIDEO", {"customer_task_id": task.id}, scheduled_at=after_seconds(20 * 60)),
        ]

    def apply_action_result(self, action: dict[str, Any], status: str, result: dict[str, Any]) -> None:
        task = self.get_customer(action["customer_task_id"])
        if status != "success":
            if result.get("error_code") == "CUSTOMER_DELETED":
                self.finish_task(task, "CUSTOMER_DELETED", "客户已删除或无法触达")
            return

        action_type = action["action_type"]
        if action_type == "SEND_LINK":
            self.update_customer(task, current_status="LINK_SENT", link_sent_at=now_iso())
        elif action_type == "SEND_WAIT_20_MIN_MESSAGE":
            self.update_customer(task, wait_message_sent_at=now_iso())
        elif action_type == "CREATE_VIDEO":
            self.update_customer(task, current_status="WAITING_VIDEO", video_task_id=result.get("video_task_id") or new_id("VD"))
        elif action_type == "SEND_VIDEO":
            task = self.update_customer(task, current_status="WAITING_PAYMENT_LINK", video_sent_at=now_iso())
            self.create_action(task.id, "SEND_PAYMENT_LINK", {"payment_link": result.get("payment_link") or "PAYMENT_LINK_PLACEHOLDER"}, scheduled_at=after_seconds(6 * 60))
        elif action_type == "SEND_PAYMENT_LINK":
            self.update_customer(task, current_status="PAYMENT_LINK_SENT", payment_link_sent_at=now_iso())
        elif action_type == "SEND_PAYMENT_QR":
            self.update_customer(task, current_status="QR_SENT")
        elif action_type == "FINISH_TASK":
            self.finish_task(task, "FINISHED", result.get("reason") or "手动结束")

    def finish_task(self, task: CustomerTask, status: str, reason: str) -> CustomerTask:
        self.cancel_pending_actions(task.id)
        return self.update_customer(
            task,
            current_status=status,
            deleted_by_customer=status == "CUSTOMER_DELETED" or task.deleted_by_customer,
            final_status="FINISHED",
            missing_fields=task.missing_fields,
        )

    def detect_message_signals(self, text_value: str, payload: dict[str, Any]) -> dict[str, bool]:
        lowered = text_value.lower()
        return {
            "red_packet": bool(payload.get("red_packet") or "红包" in text_value),
            "payment_failed": bool(payload.get("payment_failed") or any(word in text_value for word in ["付不了", "付不了款", "支付不了", "付款失败"])),
            "asks_resolution": bool(payload.get("asks_resolution") or any(word in text_value for word in ["怎么化解", "化解", "怎么办"])),
            "has_screenshot": bool(payload.get("has_screenshot") or "截图" in text_value or "什么都没有" in text_value),
            "deleted": bool(payload.get("deleted") or "已删除" in text_value or "无法触达" in text_value or "deleted" in lowered),
        }


def extract_customer_info(text_value: str, payload: dict[str, Any]) -> dict[str, str | None]:
    info = {
        "customer_name": payload.get("customer_name") or payload.get("name"),
        "birth_year": str(payload.get("birth_year")) if payload.get("birth_year") else None,
        "birth_month": str(payload.get("birth_month")) if payload.get("birth_month") else None,
        "birth_day": str(payload.get("birth_day")) if payload.get("birth_day") else None,
    }

    date_match = re.search(r"(?P<year>\d{4})\s*年?\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})?\s*日?", text_value)
    if date_match:
        info["birth_year"] = info["birth_year"] or date_match.group("year")
        info["birth_month"] = info["birth_month"] or date_match.group("month")
        if date_match.group("day"):
            info["birth_day"] = info["birth_day"] or date_match.group("day")

    if not info["customer_name"]:
        explicit = re.search(r"(?:姓名|名字)[:：]?\s*([\u4e00-\u9fa5]{2,4})", text_value)
        if explicit:
            info["customer_name"] = explicit.group(1)
        else:
            compact = re.sub(r"[，,。.\s\d年月日:/-]", "", text_value)
            if 2 <= len(compact) <= 4 and all("\u4e00" <= ch <= "\u9fff" for ch in compact):
                info["customer_name"] = compact
            elif "，" in text_value or "," in text_value:
                first = re.split(r"[，,]", text_value)[0].strip()
                if 2 <= len(first) <= 4 and all("\u4e00" <= ch <= "\u9fff" for ch in first):
                    info["customer_name"] = first

    return info


def missing_fields(info: dict[str, str | None]) -> list[str]:
    missing = []
    for field in ["customer_name", "birth_year", "birth_month", "birth_day"]:
        if not info.get(field):
            missing.append(field)
    return missing
