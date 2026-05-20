"""
Scrapes the Fulton County Sheriff's Tax Sale listing.

The Sheriff publishes a monthly list of properties scheduled for tax sale
(properties with delinquent taxes, usually 2+ years past due). These owners
are under significant financial pressure and are motivated sellers.

Firecrawl handles the county government site's bot protection.
"""

import re
import logging
from datetime import datetime
from firecrawl import FirecrawlApp
from leads.config import FIRECRAWL_API_KEY

logger = logging.getLogger(__name__)

TAX_SALES_URL = "https://fultoncountyga.gov/inside-fulton-county/fulton-county-departments/sheriff/tax-sales"
NEWSPAPER_NOTICE_URL = "https://www.southfultondailyneighbor.com"


def scrape_tax_sales() -> list[dict]:
    """Return list of tax-delinquent lead dicts for Fulton County."""
    if not FIRECRAWL_API_KEY:
        logger.error("FIRECRAWL_API_KEY not set — skipping Fulton tax sales scraper")
        return []

    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    leads = []

    try:
        result = app.extract(
            [TAX_SALES_URL],
            {
                "prompt": (
                    "This page lists properties scheduled for tax sale by the Fulton County "
                    "Sheriff in Georgia. Extract every property listed. For each property get: "
                    "the property address, the owner name, and the amount of delinquent taxes owed."
                ),
                "schema": {
                    "type": "object",
                    "properties": {
                        "properties": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "address": {"type": "string"},
                                    "owner_name": {"type": "string"},
                                    "taxes_owed": {"type": "string"},
                                    "sale_date": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            },
        )
        properties = (result.get("data") or {}).get("properties", [])
    except Exception as exc:
        logger.warning("Firecrawl extract failed for Fulton tax sales: %s", exc)
        properties = []

    if not properties:
        properties = _scrape_fallback(app)

    today = datetime.now().strftime("%Y-%m-%d")
    for prop in properties:
        address = _clean_address(prop.get("address", ""))
        owner = _clean_name(prop.get("owner_name", ""))
        if not address and not owner:
            continue

        city, state, zip_code = _parse_city_state_zip(address)
        leads.append(
            {
                "date_added": today,
                "address": address,
                "city": city,
                "state": state or "GA",
                "zip": zip_code,
                "owner_name": owner,
                "distress_type": "Tax Delinquent",
                "source": "Fulton County Sheriff Tax Sales",
                "notes": f"Taxes owed: {prop.get('taxes_owed', '')} | Sale: {prop.get('sale_date', '')}",
            }
        )

    logger.info("Fulton County tax sales: %d tax-delinquent leads collected", len(leads))
    return leads


def _scrape_fallback(app: FirecrawlApp) -> list[dict]:
    """Fallback: raw scrape and parse via regex."""
    properties = []
    try:
        result = app.scrape_url(TAX_SALES_URL, params={"formats": ["markdown"]})
        markdown = result.get("markdown", "")
        properties = _parse_tax_sale_markdown(markdown)
    except Exception as exc:
        logger.warning("Fallback scrape of Fulton tax sales failed: %s", exc)
    return properties


def _parse_tax_sale_markdown(markdown: str) -> list[dict]:
    """Parse property records from markdown text."""
    properties = []
    # Common pattern in GA tax sale listings: owner name followed by address on next line
    # e.g. "SMITH JOHN D\n123 MAIN ST ATLANTA GA 30301\n$4,523.67"
    address_re = re.compile(
        r"(\d{2,5}\s+[A-Z][A-Z\s]+(?:ST|AVE|RD|DR|LN|CT|WAY|BLVD|CIR|PL|TER|HWY|PKWY)"
        r"[A-Z\s,]*(?:ATLANTA|ALPHARETTA|ROSWELL|SANDY SPRINGS|EAST POINT|COLLEGE PARK)"
        r"[A-Z\s,]*GA\s+\d{5})",
        re.IGNORECASE,
    )
    amount_re = re.compile(r"\$\s*([\d,]+\.\d{2})")

    lines = markdown.split("\n")
    for i, line in enumerate(lines):
        address_match = address_re.search(line)
        if address_match:
            owner = lines[i - 1].strip() if i > 0 else ""
            amount_match = amount_re.search(lines[i + 1] if i + 1 < len(lines) else "")
            properties.append(
                {
                    "address": address_match.group(1).strip(),
                    "owner_name": owner,
                    "taxes_owed": f"${amount_match.group(1)}" if amount_match else "",
                    "sale_date": "",
                }
            )
    return properties


def _clean_address(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s{2,}", " ", raw.strip().rstrip(",. "))


def _clean_name(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s{2,}", " ", raw.strip()).title()


def _parse_city_state_zip(address: str) -> tuple[str, str, str]:
    m = re.search(
        r",?\s*([A-Za-z\s]+),?\s+(GA|Georgia)\s+(\d{5})", address, re.IGNORECASE
    )
    if m:
        return m.group(1).strip(), "GA", m.group(3)
    return "Atlanta", "GA", ""
