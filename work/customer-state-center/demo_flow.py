from __future__ import annotations

import json
from pathlib import Path

from state_center import StateCenter


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "demo.sqlite3"


def show(title: str, data) -> None:
    print(f"\n## {title}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    center = StateCenter(DB_PATH)

    show("1. 新客户进入", center.handle_event("NEW_CUSTOMER", "wx_customer_A"))

    first_action = center.list_actions(status="pending")[0]
    show("2. 任务二回传：链接已发送", center.complete_action(first_action["id"], "success", {"message_id": "MSG_LINK"}))

    show("3. 客户点链接", center.handle_event("LINK_CLICKED", "wx_customer_A"))

    show(
        "4. 客户只发截图没资料",
        center.handle_event("CUSTOMER_MESSAGE", "wx_customer_A", {"text": "【截图】什么都没有", "has_screenshot": True}),
    )

    show(
        "5. 客户补完整资料",
        center.handle_event("CUSTOMER_MESSAGE", "wx_customer_A", {"text": "张三，1998年5月12日"}),
    )

    show("6. 当前待执行动作", center.list_actions(status="pending"))

    send_video = next(action for action in center.list_actions(status="pending") if action["action_type"] == "SEND_VIDEO")
    show(
        "6.1 任务二回传：视频已发送，自动生成6分钟后付款链接",
        center.complete_action(send_video["id"], "success", {"video_message_id": "MSG_VIDEO", "payment_link": "https://pay.example/order/001"}),
    )
    show("6.2 查看自动生成的付款链接任务", [a for a in center.list_actions(status="pending") if a["action_type"] == "SEND_PAYMENT_LINK"])

    show("7. 第二个客户没点链接但发了资料", center.handle_event("NEW_CUSTOMER", "wx_customer_B"))
    show(
        "8. 先要求点链接，并安排2分钟检查",
        center.handle_event("CUSTOMER_MESSAGE", "wx_customer_B", {"text": "李四，2001年8月12日"}),
    )
    show("9. 模拟2分钟后仍未点击，也登记", center.handle_event("CHECK_LINK_CLICKED_AFTER_2MIN", "wx_customer_B"))

    show("10. 红包场景", center.handle_event("CUSTOMER_MESSAGE", "wx_customer_A", {"text": "【红包】", "red_packet": True}))
    show("11. 化解咨询", center.handle_event("CUSTOMER_MESSAGE", "wx_customer_A", {"text": "怎么化解？"}))
    show("12. 付款失败", center.handle_event("CUSTOMER_MESSAGE", "wx_customer_A", {"text": "我付不了款"}))


if __name__ == "__main__":
    main()
