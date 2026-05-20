"""
Enriches leads with property data from Fulton County's ArcGIS open data portal.

Fulton County publishes a free Tax Parcels dataset via ArcGIS REST API.
No API key required — it's fully public. We query it by address to get:
  - Parcel ID, year built, square footage, land/improvement value, owner mailing address.

ArcGIS REST endpoint (discovered from dataset ID e581a072dca9442e884d3682bff03484):
  https://services1.arcgis.com/Ug5xGQbHsD8zuZzM/arcgis/rest/services/Tax_Parcels/FeatureServer/0
"""

import re
import logging
from leads.scrapers.base import fetch_json

logger = logging.getLogger(__name__)

# Fulton County Tax Parcels FeatureServer — public, no key needed
_PARCELS_URL = (
    "https://services1.arcgis.com/Ug5xGQbHsD8zuZzM/arcgis/rest/services/"
    "Tax_Parcels/FeatureServer/0/query"
)

# Fulton County open data hub metadata endpoint (used to discover the live FeatureServer URL)
_HUB_METADATA_URL = (
    "https://opendata.arcgis.com/api/v3/datasets/e581a072dca9442e884d3682bff03484"
)


def enrich_lead(lead: dict) -> dict:
    """
    Add parcel-level property data to a lead dict in-place.
    Returns the lead with any found fields populated.
    """
    address = lead.get("address", "")
    if not address:
        return lead

    parcel = _query_parcel_by_address(address)
    if not parcel:
        return lead

    attrs = parcel.get("attributes", {})
    lead["parcel_id"] = attrs.get("PARCEL_ID") or attrs.get("PIN") or ""
    lead["year_built"] = str(attrs.get("YEAR_BUILT") or attrs.get("YR_BLT") or "")
    lead["sqft"] = str(attrs.get("BLDG_AREA") or attrs.get("FLOOR_AREA") or "")
    lead["est_market_value"] = _format_value(
        attrs.get("MARKET_VALUE") or attrs.get("APPRSD_VAL") or attrs.get("TOTAL_VALUE")
    )
    # Owner mailing address (often different from property address = absentee owner flag)
    mailing_parts = [
        attrs.get("OWNER_ADDR") or "",
        attrs.get("OWNER_CITY") or "",
        attrs.get("OWNER_STATE") or "",
        attrs.get("OWNER_ZIP") or "",
    ]
    lead["owner_mailing_address"] = ", ".join(p for p in mailing_parts if p)

    # If we got a better owner name from the parcel record, use it
    if not lead.get("owner_name") and attrs.get("OWNER_NAME"):
        lead["owner_name"] = str(attrs["OWNER_NAME"]).title()

    return lead


def _query_parcel_by_address(address: str) -> dict | None:
    """Query the ArcGIS FeatureServer for a parcel matching the given address."""
    # Normalize to street number + name only (strip city/state/zip for the LIKE search)
    street_part = _extract_street(address)
    if not street_part:
        return None

    params = {
        "where": f"UPPER(SITUS_ADDR) LIKE UPPER('%{street_part}%')",
        "outFields": (
            "PARCEL_ID,PIN,SITUS_ADDR,OWNER_NAME,OWNER_ADDR,OWNER_CITY,OWNER_STATE,"
            "OWNER_ZIP,YEAR_BUILT,YR_BLT,BLDG_AREA,FLOOR_AREA,MARKET_VALUE,"
            "APPRSD_VAL,TOTAL_VALUE"
        ),
        "resultRecordCount": 1,
        "f": "json",
    }

    data = fetch_json(_PARCELS_URL, params=params, delay=1.0)
    if not data:
        # Try discovering the live endpoint from the metadata hub
        data = _query_via_hub_discovery(street_part)

    if data and data.get("features"):
        return data["features"][0]
    return None


def _query_via_hub_discovery(street_part: str) -> dict | None:
    """Fall back to discovering the FeatureServer URL from the ArcGIS Hub metadata."""
    meta = fetch_json(_HUB_METADATA_URL, delay=1.0)
    if not meta:
        return None

    service_url = (
        (meta.get("data") or {})
        .get("attributes", {})
        .get("url", "")
    )
    if not service_url:
        return None

    query_url = service_url.rstrip("/") + "/query"
    params = {
        "where": f"UPPER(SITUS_ADDR) LIKE UPPER('%{street_part}%')",
        "outFields": "*",
        "resultRecordCount": 1,
        "f": "json",
    }
    return fetch_json(query_url, params=params, delay=1.0)


def _extract_street(address: str) -> str:
    """Pull the street number + name from a full address string."""
    m = re.match(r"^(\d+\s+[A-Za-z0-9 ]+?)(?:,|\s+(?:Atlanta|GA|\d{5}))", address)
    if m:
        return m.group(1).strip()
    # Fallback: take first two tokens if they look like a number + word
    parts = address.split()
    if parts and parts[0].isdigit():
        return " ".join(parts[:3])
    return ""


def _format_value(raw) -> str:
    if raw is None:
        return ""
    try:
        return f"${int(raw):,}"
    except (ValueError, TypeError):
        return str(raw)
