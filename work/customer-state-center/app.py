from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from state_center import StateCenter


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "state_center.sqlite3"
state_center = StateCenter(DB_PATH)


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>客户状态中台测试窗口</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #edf1f5;
      --panel: #ffffff;
      --line: #d9e0e7;
      --text: #17202a;
      --muted: #687584;
      --green: #16a34a;
      --green-dark: #12813b;
      --blue: #2563eb;
      --orange: #d97706;
      --red: #dc2626;
      --shadow: 0 14px 36px rgba(31, 42, 55, 0.14);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }

    .sidebar {
      background: #263442;
      color: #fff;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      border-right: 1px solid rgba(255,255,255,0.08);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 2px 0 10px;
      border-bottom: 1px solid rgba(255,255,255,0.12);
    }

    .mark {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: var(--green);
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 18px;
    }

    h1 {
      font-size: 17px;
      line-height: 1.35;
      margin: 0;
    }

    .subtitle {
      margin-top: 3px;
      font-size: 12px;
      color: rgba(255,255,255,0.68);
    }

    .field, .panel {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    label {
      font-size: 13px;
      color: rgba(255,255,255,0.74);
    }

    input, textarea, button {
      font: inherit;
    }

    .sidebar input {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.16);
      background: rgba(255,255,255,0.08);
      color: #fff;
      border-radius: 6px;
      padding: 10px 11px;
      outline: none;
    }

    .sidebar input:focus {
      border-color: rgba(74, 222, 128, 0.7);
      background: rgba(255,255,255,0.12);
    }

    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    button {
      border: 0;
      border-radius: 6px;
      cursor: pointer;
      min-height: 40px;
      padding: 9px 11px;
      color: #fff;
      background: #455767;
      transition: background .16s ease, transform .16s ease;
    }

    button:hover { transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    .primary { background: var(--green); }
    .primary:hover { background: var(--green-dark); }
    .blue { background: var(--blue); }
    .orange { background: var(--orange); }
    .red { background: var(--red); }
    .wide { grid-column: 1 / -1; }

    .snapshot {
      margin-top: auto;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      padding: 12px;
      min-height: 180px;
    }

    .snapshot-title {
      font-size: 13px;
      color: rgba(255,255,255,0.78);
      margin-bottom: 10px;
    }

    .kv {
      display: grid;
      grid-template-columns: 82px 1fr;
      gap: 7px;
      font-size: 13px;
      line-height: 1.4;
    }

    .kv span:nth-child(odd) { color: rgba(255,255,255,0.58); }
    .kv span:nth-child(even) { color: #fff; word-break: break-word; }

    .main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      height: 100vh;
    }

    .topbar {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .contact {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      background: #9aa8b6;
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 700;
      flex: 0 0 auto;
    }

    .name {
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .status {
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }

    .chat {
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .bubble-row {
      display: flex;
      gap: 8px;
      align-items: flex-end;
      max-width: min(760px, 92%);
    }

    .bubble-row.customer {
      align-self: flex-start;
    }

    .bubble-row.system {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .bubble-avatar {
      width: 30px;
      height: 30px;
      border-radius: 6px;
      display: grid;
      place-items: center;
      font-size: 12px;
      color: #fff;
      background: #7b8794;
      flex: 0 0 auto;
    }

    .system .bubble-avatar {
      background: var(--green);
    }

    .bubble {
      border-radius: 8px;
      padding: 10px 12px;
      line-height: 1.55;
      box-shadow: 0 2px 8px rgba(25, 35, 45, 0.08);
      word-break: break-word;
      white-space: pre-wrap;
    }

    .customer .bubble {
      background: #fff;
      border: 1px solid var(--line);
    }

    .system .bubble {
      background: #9fe870;
    }

    .meta-note {
      align-self: center;
      color: var(--muted);
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
    }

    .composer {
      background: var(--panel);
      border-top: 1px solid var(--line);
      padding: 13px 16px 16px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: end;
    }

    textarea {
      width: 100%;
      min-height: 46px;
      max-height: 140px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      outline: none;
      line-height: 1.5;
    }

    textarea:focus {
      border-color: #8ab4f8;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
    }

    .send {
      min-width: 82px;
      background: var(--green);
    }

    .pending {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      position: fixed;
      right: 20px;
      bottom: 82px;
      width: min(360px, calc(100vw - 40px));
      max-height: 260px;
      overflow: auto;
      padding: 12px;
      display: none;
    }

    .pending.show { display: block; }
    .pending h2 {
      margin: 0 0 9px;
      font-size: 14px;
    }
    .pending-item {
      border-top: 1px solid var(--line);
      padding: 9px 0 0;
      margin-top: 9px;
      font-size: 12px;
      color: var(--muted);
    }
    .pending-item strong { color: var(--text); }

    @media (max-width: 800px) {
      .app { grid-template-columns: 1fr; }
      .sidebar {
        min-height: auto;
        display: block;
      }
      .field, .panel, .snapshot { margin-top: 12px; }
      .main { height: calc(100vh - 340px); min-height: 560px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="mark">状</div>
        <div>
          <h1>客户状态中台测试窗口</h1>
          <div class="subtitle">Dev1 本地模拟，任务一只判断和派发动作</div>
        </div>
      </div>

      <div class="field">
        <label for="customerId">客户 ID</label>
        <input id="customerId" value="wx_customer_demo" autocomplete="off">
      </div>

      <div class="panel">
        <label>快捷事件</label>
        <div class="actions">
          <button class="primary wide" id="newCustomer">新客户进入</button>
          <button class="blue" id="clickLink">客户点链接</button>
          <button id="screenshot">发截图</button>
          <button id="redPacket">发红包</button>
          <button class="orange" id="resolution">问化解</button>
          <button class="red" id="deleted">删除客户</button>
          <button class="wide" id="resetChat">清空窗口</button>
        </div>
      </div>

      <div class="snapshot">
        <div class="snapshot-title">当前客户状态</div>
        <div class="kv" id="snapshot">
          <span>状态</span><span>未开始</span>
          <span>链接</span><span>-</span>
          <span>资料</span><span>-</span>
          <span>动作</span><span>-</span>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="contact">
          <div class="avatar">客</div>
          <div>
            <div class="name" id="contactName">wx_customer_demo</div>
            <div class="status" id="topStatus">等待开始</div>
          </div>
        </div>
        <button id="togglePending">动作队列</button>
      </header>

      <section class="chat" id="chat">
        <div class="meta-note">点击“新客户进入”开始模拟</div>
      </section>

      <form class="composer" id="composer">
        <textarea id="message" placeholder="输入客户消息，例如：张三，1998年5月12日"></textarea>
        <button class="send" type="submit">发送</button>
      </form>
    </main>
  </div>

  <section class="pending" id="pending">
    <h2>待执行动作</h2>
    <div id="pendingList">暂无</div>
  </section>

  <script>
    const chat = document.getElementById("chat");
    const customerIdInput = document.getElementById("customerId");
    const contactName = document.getElementById("contactName");
    const topStatus = document.getElementById("topStatus");
    const snapshot = document.getElementById("snapshot");
    const pendingPanel = document.getElementById("pending");
    const pendingList = document.getElementById("pendingList");
    const message = document.getElementById("message");

    const actionText = {
      SEND_LINK: (a) => `请点这个链接参与排队：${demoLink(a.payload.link_id)}`,
      ASK_FOR_IMAGE_INFO: (a) => a.payload.text || "请把上面图片的信息发我一下",
      ASK_MISSING_BIRTHDAY: (a) => a.payload.text || "把出生年月日发我一下",
      ASK_MISSING_NAME: (a) => a.payload.text || "把姓名发我一下",
      ASK_CLICK_LINK: (a) => `${a.payload.text || "点链接参与排队"}：${demoLink()}`,
      SEND_WAIT_20_MIN_MESSAGE: (a) => a.payload.text || "好的，请稍等20分钟左右",
      SEND_PAYMENT_LINK: (a) => `付款链接：${a.payload.payment_link || "https://pay.example/order/demo"}`,
      SEND_PAYMENT_QR: () => "我发你付款二维码，你扫这个就可以。",
      SEND_RED_PACKET_REPLY: (a) => a.payload.text || "私人不接受红包，可以扫给上面的道观",
      ASK_DONATION_AMOUNT: (a) => a.payload.text || "随喜了多少呢？",
      REGISTER_CUSTOMER: () => "资料已登记。",
      CREATE_VIDEO: () => "视频任务已创建。",
      SEND_VIDEO: () => "视频已排队，默认 20 分钟后发送。",
      FINISH_TASK: () => "客户任务已结束。"
    };

    function customerId() {
      const value = customerIdInput.value.trim() || "wx_customer_demo";
      contactName.textContent = value;
      return value;
    }

    function demoLink(linkId) {
      return `https://queue.example/${linkId || "demo"}`;
    }

    function addBubble(who, text) {
      const row = document.createElement("div");
      row.className = `bubble-row ${who}`;
      const avatar = document.createElement("div");
      avatar.className = "bubble-avatar";
      avatar.textContent = who === "customer" ? "客" : "中";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = text;
      row.append(avatar, bubble);
      chat.appendChild(row);
      chat.scrollTop = chat.scrollHeight;
    }

    function addNote(text) {
      const note = document.createElement("div");
      note.className = "meta-note";
      note.textContent = text;
      chat.appendChild(note);
      chat.scrollTop = chat.scrollHeight;
    }

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || data.error || response.statusText);
      return data;
    }

    async function sendEvent(eventType, payload = {}, shownText = null) {
      if (shownText) addBubble("customer", shownText);
      const data = await postJson("/events", {
        event_type: eventType,
        customer_id: customerId(),
        payload
      });
      await renderResult(data);
      await refreshPending();
      return data;
    }

    async function completeAction(action, result = {}) {
      const data = await postJson(`/actions/${action.id}/complete`, {
        status: "success",
        result
      });
      await refreshPending();
      return data;
    }

    async function autoCompleteImmediate(actions) {
      for (const action of actions) {
        if (["SEND_LINK", "SEND_WAIT_20_MIN_MESSAGE"].includes(action.action_type)) {
          await completeAction(action, { message_id: `MSG_${Date.now()}` });
        }
      }
    }

    async function renderResult(data) {
      const task = data.customer_task;
      updateSnapshot(task, data.actions || []);
      if (data.ignored) {
        addNote("任务已结束，本条消息被忽略");
        return;
      }
      const actions = data.actions || [];
      if (!actions.length) {
        addNote(`状态：${task.current_status}`);
        return;
      }
      for (const action of actions) {
        const textFactory = actionText[action.action_type];
        if (textFactory) addBubble("system", textFactory(action));
        addNote(`生成动作：${action.action_type}`);
      }
      await autoCompleteImmediate(actions);
      const refreshed = await fetch(`/customers/${task.id}`).then((response) => response.json());
      updateSnapshot(refreshed, actions);
    }

    function updateSnapshot(task, actions) {
      const missing = task.missing_fields && task.missing_fields.length ? task.missing_fields.join(", ") : "完整或未填写";
      topStatus.textContent = task.current_status || "未开始";
      snapshot.innerHTML = `
        <span>状态</span><span>${task.current_status || "-"}</span>
        <span>链接</span><span>${task.link_clicked ? "已点击" : (task.link_id ? "未点击" : "-")}</span>
        <span>资料</span><span>${task.info_complete ? "完整" : missing}</span>
        <span>动作</span><span>${actions.map(a => a.action_type).join(", ") || "-"}</span>
      `;
    }

    async function refreshPending() {
      const response = await fetch("/actions?status=pending");
      const actions = await response.json();
      if (!actions.length) {
        pendingList.textContent = "暂无";
        return;
      }
      pendingList.innerHTML = "";
      for (const action of actions.slice(0, 20)) {
        const item = document.createElement("div");
        item.className = "pending-item";
        item.innerHTML = `<strong>${action.action_type}</strong><br>${action.scheduled_at}<br>${JSON.stringify(action.payload)}`;
        pendingList.appendChild(item);
      }
    }

    document.getElementById("newCustomer").addEventListener("click", async () => {
      addNote("新客户进入");
      await sendEvent("NEW_CUSTOMER");
    });

    document.getElementById("clickLink").addEventListener("click", async () => {
      await sendEvent("LINK_CLICKED", {}, "我点链接了");
    });

    document.getElementById("screenshot").addEventListener("click", async () => {
      await sendEvent("CUSTOMER_MESSAGE", { text: "【截图】什么都没有", has_screenshot: true }, "【截图】什么都没有");
    });

    document.getElementById("redPacket").addEventListener("click", async () => {
      await sendEvent("CUSTOMER_MESSAGE", { text: "【红包】", red_packet: true }, "【红包】");
    });

    document.getElementById("resolution").addEventListener("click", async () => {
      await sendEvent("CUSTOMER_MESSAGE", { text: "怎么化解？" }, "怎么化解？");
    });

    document.getElementById("deleted").addEventListener("click", async () => {
      await sendEvent("CUSTOMER_DELETED", {}, "我把你删了");
    });

    document.getElementById("resetChat").addEventListener("click", () => {
      customerIdInput.value = `wx_customer_${Date.now()}`;
      customerId();
      chat.innerHTML = '<div class="meta-note">窗口已清空，可以换一个客户 ID 重新开始</div>';
      snapshot.innerHTML = "<span>状态</span><span>未开始</span><span>链接</span><span>-</span><span>资料</span><span>-</span><span>动作</span><span>-</span>";
      topStatus.textContent = "等待开始";
    });

    document.getElementById("togglePending").addEventListener("click", async () => {
      pendingPanel.classList.toggle("show");
      await refreshPending();
    });

    customerIdInput.addEventListener("input", customerId);

    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = message.value.trim();
      if (!text) return;
      message.value = "";
      await sendEvent("CUSTOMER_MESSAGE", { text }, text);
    });

    customerIdInput.value = `wx_customer_${Date.now()}`;
    customerId();
    refreshPending();
  </script>
</body>
</html>
"""


def json_response(handler: BaseHTTPRequestHandler, status: int, body: dict | list) -> None:
    data = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


class Handler(BaseHTTPRequestHandler):
    server_version = "CustomerStateCenter/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[state-center] {self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/":
                data = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if path == "/health":
                json_response(self, 200, {"ok": True, "service": "customer-state-center"})
                return

            if path == "/customers":
                json_response(self, 200, state_center.list_customers())
                return

            if path.startswith("/customers/"):
                task_id = path.split("/", 2)[2]
                json_response(self, 200, state_center.get_customer(task_id).to_dict())
                return

            if path == "/actions":
                status = query.get("status", [None])[0]
                due_only = query.get("due", ["0"])[0] in {"1", "true", "yes"}
                json_response(self, 200, state_center.list_actions(status=status, due_only=due_only))
                return

            json_response(self, 404, {"error": "not_found"})
        except Exception as exc:
            json_response(self, 500, {"error": type(exc).__name__, "message": str(exc)})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            body = read_json(self)

            if path == "/events":
                result = state_center.handle_event(
                    event_type=body["event_type"],
                    customer_id=body["customer_id"],
                    payload=body.get("payload") or {},
                )
                json_response(self, 200, result)
                return

            if path.startswith("/actions/") and path.endswith("/complete"):
                action_id = path.split("/")[2]
                result = state_center.complete_action(
                    action_task_id=action_id,
                    status=body.get("status", "success"),
                    result=body.get("result") or {},
                )
                json_response(self, 200, result)
                return

            json_response(self, 404, {"error": "not_found"})
        except KeyError as exc:
            json_response(self, 400, {"error": "missing_field", "message": str(exc)})
        except Exception as exc:
            json_response(self, 500, {"error": type(exc).__name__, "message": str(exc)})


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Customer state center listening on http://{host}:{port}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    run()
