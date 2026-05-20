"""
Appends daily leads to a Google Sheet.

Setup (one-time, free):
  1. Go to https://console.cloud.google.com → New Project
  2. Enable the Google Sheets API
  3. Create a Service Account (IAM & Admin → Service Accounts)
  4. Create a JSON key for the service account and download it
  5. Share your Google Sheet with the service account's email (Editor access)
  6. Set GOOGLE_CREDENTIALS_JSON env var to the full JSON content (single line)
  7. Set SPREADSHEET_ID env var to the ID in your sheet's URL

The sheet is auto-created with frozen headers and color-coded priority rows
on first run. Subsequent runs append to the bottom.
"""

import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from leads.config import GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID, LEADS_SHEET_NAME, SHEET_HEADERS

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def append_leads(leads: list[dict]) -> None:
    """Append all leads as new rows in the Google Sheet."""
    if not leads:
        logger.info("No leads to append.")
        return

    if not GOOGLE_CREDENTIALS_JSON or not SPREADSHEET_ID:
        logger.error(
            "GOOGLE_CREDENTIALS_JSON or SPREADSHEET_ID not set — skipping sheet delivery"
        )
        return

    service = _build_service()
    if not service:
        return

    _ensure_headers(service)

    rows = [_lead_to_row(lead) for lead in leads]
    try:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{LEADS_SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        logger.info("Appended %d rows to Google Sheet", len(rows))
        _apply_priority_formatting(service, leads)
    except HttpError as exc:
        logger.error("Google Sheets append failed: %s", exc)


def _lead_to_row(lead: dict) -> list:
    return [
        lead.get("date_added", datetime.now().strftime("%Y-%m-%d")),
        lead.get("address", ""),
        lead.get("city", ""),
        lead.get("state", "GA"),
        lead.get("zip", ""),
        lead.get("owner_name", ""),
        lead.get("distress_type", ""),
        lead.get("source", ""),
        lead.get("priority", "NORMAL"),
        lead.get("phone_1", ""),
        lead.get("phone_2", ""),
        lead.get("email", ""),
        lead.get("owner_mailing_address", ""),
        lead.get("est_market_value", ""),
        lead.get("year_built", ""),
        lead.get("sqft", ""),
        lead.get("parcel_id", ""),
        lead.get("notes", ""),
        "New",  # Status — team updates this
    ]


def _ensure_headers(service) -> None:
    """Write header row if the sheet is empty."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{LEADS_SHEET_NAME}!A1:A1",
        ).execute()
        if result.get("values"):
            return  # Headers already exist

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{LEADS_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS]},
        ).execute()

        # Freeze the header row and bold it
        sheet_id = _get_sheet_id(service)
        if sheet_id is not None:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": sheet_id,
                                    "gridProperties": {"frozenRowCount": 1},
                                },
                                "fields": "gridProperties.frozenRowCount",
                            }
                        },
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 0,
                                    "endRowIndex": 1,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "textFormat": {"bold": True},
                                        "backgroundColor": {
                                            "red": 0.2,
                                            "green": 0.2,
                                            "blue": 0.2,
                                        },
                                        "textFormat": {
                                            "bold": True,
                                            "foregroundColor": {
                                                "red": 1.0,
                                                "green": 1.0,
                                                "blue": 1.0,
                                            },
                                        },
                                    }
                                },
                                "fields": "userEnteredFormat(backgroundColor,textFormat)",
                            }
                        },
                    ]
                },
            ).execute()
        logger.info("Headers written and formatted in Google Sheet")
    except HttpError as exc:
        logger.warning("Could not ensure headers: %s", exc)


def _apply_priority_formatting(service, leads: list[dict]) -> None:
    """Highlight HIGH priority rows in yellow after appending."""
    sheet_id = _get_sheet_id(service)
    if sheet_id is None:
        return

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{LEADS_SHEET_NAME}!I:I",
        ).execute()
        values = result.get("values", [])
    except HttpError:
        return

    requests = []
    for row_idx, cell in enumerate(values):
        if cell and cell[0] == "HIGH":
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_idx,
                            "endRowIndex": row_idx + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 1.0,
                                    "green": 0.95,
                                    "blue": 0.6,
                                }
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            )

    if requests:
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": requests},
            ).execute()
            logger.info("Applied HIGH priority highlighting to %d rows", len(requests))
        except HttpError as exc:
            logger.warning("Could not apply priority formatting: %s", exc)


def _get_sheet_id(service) -> int | None:
    try:
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID
        ).execute()
        for sheet in spreadsheet.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("title") == LEADS_SHEET_NAME:
                return props.get("sheetId")
    except HttpError:
        pass
    return None


def _build_service():
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        logger.error("Failed to build Google Sheets service: %s", exc)
        return None
