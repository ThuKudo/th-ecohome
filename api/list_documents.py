from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from admin_common import json_response, list_documents, require_auth


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not require_auth(self):
            return
        try:
            json_response(self, {"documents": list_documents()}, HTTPStatus.OK)
        except RuntimeError as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
