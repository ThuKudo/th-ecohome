import base64
import hashlib
import hmac
import json
import os
import re
import time
from http import HTTPStatus
from urllib import error, parse, request

SESSION_COOKIE_NAME = "thecohome_admin_session"
SESSION_MAX_AGE = 60 * 60 * 12
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def get_env(name: str, default: str = "", required: bool = True) -> str:
    value = os.getenv(name, default)
    value = value.strip() if isinstance(value, str) else value
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def json_response(handler, payload: dict, status: HTTPStatus = HTTPStatus.OK, headers: dict | None = None) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    if headers:
        for key, value in headers.items():
            handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload.") from exc


def sanitize_filename(file_name: str) -> str:
    cleaned = parse.unquote(file_name or "").strip().replace("\\", "/").split("/")[-1]
    stem, dot, ext = cleaned.rpartition(".")
    base = stem if dot else cleaned
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._") or "document"
    extension = re.sub(r"[^A-Za-z0-9]+", "", ext.lower())[:10]
    return f"{base[:80]}.{extension}" if extension else base[:80]


def _sign(value: str) -> str:
    secret = get_env("ADMIN_SESSION_SECRET")
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_session_token() -> str:
    expires_at = int(time.time()) + SESSION_MAX_AGE
    payload = f"admin|{expires_at}"
    token = f"{payload}|{_sign(payload)}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        padded = token + ("=" * (-len(token) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        role, expires_at, signature = decoded.split("|", 2)
        if role != "admin":
            return False
        if int(expires_at) < int(time.time()):
            return False
        expected = _sign(f"{role}|{expires_at}")
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


def get_cookie(headers, name: str) -> str | None:
    raw_cookie = headers.get("Cookie", "")
    for chunk in raw_cookie.split(";"):
        key, sep, value = chunk.strip().partition("=")
        if sep and key == name:
            return value
    return None


def is_authenticated(headers) -> bool:
    return verify_session_token(get_cookie(headers, SESSION_COOKIE_NAME))


def require_auth(handler) -> bool:
    if is_authenticated(handler.headers):
        return True
    json_response(handler, {"error": "Unauthorized."}, HTTPStatus.UNAUTHORIZED)
    return False


def login_cookie_header() -> str:
    token = issue_session_token()
    return (
        f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_MAX_AGE}"
    )


def logout_cookie_header() -> str:
    return f"{SESSION_COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"


def _supabase_headers(extra: dict | None = None) -> dict:
    service_key = get_env("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
    }
    if extra:
        headers.update(extra)
    return headers


def supabase_request(method: str, path: str, *, body: bytes | None = None, json_body: dict | None = None, headers: dict | None = None) -> tuple[int, str]:
    supabase_url = get_env("SUPABASE_URL").rstrip("/")
    request_headers = _supabase_headers(headers)
    payload = body
    if json_body is not None:
        payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    req = request.Request(f"{supabase_url}{path}", data=payload, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            return getattr(response, "status", 200), response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"Supabase API error: {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError("Could not reach Supabase.") from exc


def storage_bucket() -> str:
    return get_env("SUPABASE_BUCKET")


def storage_prefix() -> str:
    return get_env("SUPABASE_DOCUMENTS_FOLDER", "documents", required=False).strip("/")


def public_file_url(path: str) -> str:
    supabase_url = get_env("SUPABASE_URL").rstrip("/")
    quoted_path = parse.quote(path, safe="/")
    return f"{supabase_url}/storage/v1/object/public/{storage_bucket()}/{quoted_path}"


def upload_document(file_name: str, content_type: str, payload: bytes) -> dict:
    clean_name = sanitize_filename(file_name)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    prefix = storage_prefix()
    object_path = f"{prefix}/{timestamp}-{clean_name}" if prefix else f"{timestamp}-{clean_name}"
    quoted_path = parse.quote(object_path, safe="/")
    supabase_request(
        "POST",
        f"/storage/v1/object/{storage_bucket()}/{quoted_path}",
        body=payload,
        headers={
            "Content-Type": content_type or "application/octet-stream",
            "x-upsert": "true",
            "Cache-Control": "3600",
        },
    )
    return {
        "name": clean_name,
        "path": object_path,
        "url": public_file_url(object_path),
        "size": len(payload),
        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def list_documents() -> list[dict]:
    prefix = storage_prefix()
    _, body = supabase_request(
        "POST",
        f"/storage/v1/object/list/{storage_bucket()}",
        json_body={
            "limit": 100,
            "offset": 0,
            "prefix": prefix,
            "sortBy": {"column": "created_at", "order": "desc"},
        },
    )
    raw_items = json.loads(body or "[]")
    documents = []
    for item in raw_items:
        item_name = item.get("name") or ""
        full_path = f"{prefix}/{item_name}" if prefix else item_name
        metadata = item.get("metadata") or {}
        documents.append(
            {
                "name": item_name,
                "path": full_path,
                "url": public_file_url(full_path),
                "size": metadata.get("size") or metadata.get("contentLength") or 0,
                "created_at": item.get("created_at") or item.get("updated_at") or "",
                "updated_at": item.get("updated_at") or "",
                "content_type": metadata.get("mimetype") or metadata.get("contentType") or "",
            }
        )
    return documents
