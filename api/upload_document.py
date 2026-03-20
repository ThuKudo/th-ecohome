from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib import parse

from admin_common import MAX_UPLOAD_BYTES, json_response, require_auth, upload_document


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not require_auth(self):
            return
        try:
            file_name = parse.unquote(self.headers.get("X-File-Name", "")).strip()
            content_type = self.headers.get("X-Content-Type", "application/octet-stream").strip()
            if not file_name:
                json_response(self, {"error": "Thi?u t?n file."}, HTTPStatus.BAD_REQUEST)
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                json_response(self, {"error": "Kh?ng c? d? li?u file."}, HTTPStatus.BAD_REQUEST)
                return
            if content_length > MAX_UPLOAD_BYTES:
                json_response(
                    self,
                    {"error": f"File v??t qu? gi?i h?n {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            payload = self.rfile.read(content_length)
            uploaded = upload_document(file_name, content_type, payload)
            json_response(self, {"document": uploaded}, HTTPStatus.CREATED)
        except RuntimeError as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        except ValueError:
            json_response(self, {"error": "D? li?u upload kh?ng h?p l?."}, HTTPStatus.BAD_REQUEST)
