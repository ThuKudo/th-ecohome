import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_SHEET_NAME = "Contacts"
HEADERS = [
    "Submitted At",
    "Form Type",
    "Full Name",
    "Phone",
    "Message",
    "Language",
    "Source",
    "Page URL",
    "User Agent",
]


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def build_sheets_service():
    service_account_json = get_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = get_env("GOOGLE_SHEET_ID")
    sheet_name = os.getenv("GOOGLE_SHEET_NAME", DEFAULT_SHEET_NAME).strip() or DEFAULT_SHEET_NAME

    credentials_info = json.loads(service_account_json)
    credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    return service, sheet_id, sheet_name


def ensure_sheet_exists(service, spreadsheet_id: str, sheet_name: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_titles = [sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])]

    if sheet_name not in sheet_titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()

    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:I1")
        .execute()
        .get("values", [])
    )
    if not values:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:I1",
            valueInputOption="RAW",
            body={"values": [HEADERS]},
        ).execute()


def append_contact(payload: dict, user_agent: str) -> None:
    service, spreadsheet_id, sheet_name = build_sheets_service()
    ensure_sheet_exists(service, spreadsheet_id, sheet_name)

    row = [
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        payload.get("form_type", ""),
        payload.get("name", ""),
        payload.get("phone", ""),
        payload.get("message", ""),
        payload.get("language", ""),
        payload.get("source", ""),
        payload.get("page_url", ""),
        user_agent,
    ]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:I",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


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
            append_contact(payload, self.headers.get("User-Agent", ""))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        except HttpError as exc:
            self._send_json({"error": f"Google Sheets API error: {exc.status_code}"}, HTTPStatus.BAD_GATEWAY)
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
