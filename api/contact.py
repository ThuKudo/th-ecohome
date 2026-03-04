import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib import error, request


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def forward_contact(payload: dict, user_agent: str) -> None:
    apps_script_url = get_env("GOOGLE_APPS_SCRIPT_URL")
    upstream_payload = {
        "form_type": payload.get("form_type", ""),
        "name": payload.get("name", ""),
        "phone": payload.get("phone", ""),
        "message": payload.get("message", ""),
        "language": payload.get("language", ""),
        "source": payload.get("source", ""),
        "page_url": payload.get("page_url", ""),
        "user_agent": user_agent,
    }
    req = request.Request(
        apps_script_url,
        data=json.dumps(upstream_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        status_code = getattr(response, "status", 200)
        body = response.read().decode("utf-8", errors="replace")
        if status_code >= 400:
            raise RuntimeError(f"Apps Script error: {status_code}")
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {}
            if parsed.get("ok") is False:
                raise RuntimeError(parsed.get("error", "Apps Script rejected the request."))


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON payload."}, HTTPStatus.BAD_REQUEST)
            return

        name = str(payload.get("name", "")).strip()
        phone = str(payload.get("phone", "")).strip()
        if not name or not phone:
            self._send_json({"error": "Name and phone are required."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            forward_contact(payload, self.headers.get("User-Agent", ""))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        except error.HTTPError as exc:
            self._send_json({"error": f"Apps Script error: {exc.code}"}, HTTPStatus.BAD_GATEWAY)
            return
        except error.URLError:
            self._send_json({"error": "Could not reach Apps Script."}, HTTPStatus.BAD_GATEWAY)
            return
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return
        except Exception:
            self._send_json({"error": "Unexpected server error."}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"status": "ok"}, HTTPStatus.CREATED)

    def _set_headers(self):
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _send_json(self, payload: dict, status: HTTPStatus):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._set_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
