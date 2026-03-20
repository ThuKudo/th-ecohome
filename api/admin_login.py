from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from admin_common import get_env, json_response, login_cookie_header, read_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = read_json(self)
            password = str(payload.get("password", "")).strip()
            if not password:
                json_response(self, {"error": "Password is required."}, HTTPStatus.BAD_REQUEST)
                return
            if password != get_env("ADMIN_PASSWORD"):
                json_response(self, {"error": "Sai m?t kh?u."}, HTTPStatus.UNAUTHORIZED)
                return
            json_response(
                self,
                {"status": "ok"},
                HTTPStatus.OK,
                headers={"Set-Cookie": login_cookie_header()},
            )
        except RuntimeError as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        except ValueError as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
