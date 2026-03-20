from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from admin_common import json_response, logout_cookie_header


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        json_response(
            self,
            {"status": "ok"},
            HTTPStatus.OK,
            headers={"Set-Cookie": logout_cookie_header()},
        )
