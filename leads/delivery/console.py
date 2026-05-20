"""
Delivers leads as a formatted table printed to stdout (visible in this chat)
and saves a CSV file to leads/output/YYYY-MM-DD.csv in the repo.

No accounts, no API keys, no setup required.
"""

import csv
import logging
import os
from datetime import datetime
from leads.config import SHEET_HEADERS

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "leads", "output")


def deliver_leads(leads: list[dict]) -> str:
    """Print leads as a table and save CSV. Returns the CSV file path."""
    if not leads:
        print("\nNo leads collected today.\n")
        return ""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.abspath(os.path.join(OUTPUT_DIR, f"{today}.csv"))
    _save_csv(leads, csv_path)
    _print_table(leads)

    logger.info("CSV saved: %s", csv_path)
    return csv_path


def _save_csv(leads: list[dict], path: str) -> None:
    field_map = {
        "Date Added": "date_added",
        "Address": "address",
        "City": "city",
        "State": "state",
        "Zip": "zip",
        "Owner Name": "owner_name",
        "Distress Type": "distress_type",
        "Source": "source",
        "Priority": "priority",
        "Phone 1": "phone_1",
        "Phone 2": "phone_2",
        "Email": "email",
        "Owner Mailing Address": "owner_mailing_address",
        "Est Market Value": "est_market_value",
        "Year Built": "year_built",
        "Sqft": "sqft",
        "Parcel ID": "parcel_id",
        "Notes": "notes",
        "Status": "status",
    }
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(field_map.keys()))
        writer.writeheader()
        for lead in leads:
            writer.writerow({
                header: lead.get(key, "New" if key == "status" else "")
                for header, key in field_map.items()
            })


def _print_table(leads: list[dict]) -> None:
    # Columns shown in the chat-friendly summary table
    cols = [
        ("Priority", "priority", 8),
        ("Owner Name", "owner_name", 22),
        ("Address", "address", 35),
        ("Distress Type", "distress_type", 18),
        ("Phone 1", "phone_1", 16),
        ("Est Value", "est_market_value", 12),
    ]

    high = [l for l in leads if l.get("priority") == "HIGH"]
    normal = [l for l in leads if l.get("priority") != "HIGH"]
    ordered = high + normal

    header = "  ".join(label.ljust(width) for label, _, width in cols)
    divider = "  ".join("-" * width for _, _, width in cols)

    print(f"\n{'='*80}")
    print(f"  DAILY LEADS — {datetime.now().strftime('%B %d, %Y')}   "
          f"({len(leads)} total  |  {len(high)} HIGH priority)")
    print(f"{'='*80}")
    print(header)
    print(divider)

    for lead in ordered:
        row_parts = []
        for label, key, width in cols:
            val = str(lead.get(key, "") or "")
            row_parts.append(val[:width].ljust(width))
        marker = " ★" if lead.get("priority") == "HIGH" else "  "
        print(marker + "  ".join(row_parts))

    print(f"{'='*80}\n")
    print(f"  Full details saved to: leads/output/{datetime.now().strftime('%Y-%m-%d')}.csv\n")
