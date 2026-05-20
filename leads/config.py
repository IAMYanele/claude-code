import os
from dotenv import load_dotenv

load_dotenv()

TARGET_COUNTY = "Fulton"
TARGET_STATE = "GA"
TARGET_STATE_FULL = "Georgia"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
LEADS_SHEET_NAME = "Leads"

# Only skip-trace properties at or above this estimated value
MIN_PROPERTY_VALUE_FOR_SKIP_TRACE = 80_000

# Seconds to wait between skip trace lookups (be respectful)
SKIP_TRACE_DELAY = 6

SHEET_HEADERS = [
    "Date Added",
    "Address",
    "City",
    "State",
    "Zip",
    "Owner Name",
    "Distress Type",
    "Source",
    "Priority",
    "Phone 1",
    "Phone 2",
    "Email",
    "Owner Mailing Address",
    "Est Market Value",
    "Year Built",
    "Sqft",
    "Parcel ID",
    "Notes",
    "Status",
]
