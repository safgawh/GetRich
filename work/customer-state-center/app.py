from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from state_center import StateCenter


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "state_center.sqlite3"
state_center = StateCenter(DB_PATH)


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
