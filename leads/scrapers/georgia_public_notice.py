"""
Scrapes foreclosure notices from GeorgiaPublicNotice.com for Fulton County.

Georgia law (OCGA § 44-14-162) requires lenders to publish a Notice of Sale
Under Power for four consecutive weeks before a foreclosure sale. These notices
contain the property address, borrower name, and sale details.

Firecrawl handles the ASP.NET ViewState complexity and any bot-detection on this site.
"""

import re
import logging
from datetime import datetime
from firecrawl import FirecrawlApp
from leads.config import FIRECRAWL_API_KEY

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.georgiapublicnotice.com"

# Regex patterns for parsing Georgia foreclosure notice text
_ADDRESS_RE = re.compile(
    r"(?:known as|located at|property address[:\s]+|premises (?:known as|located at))[:\s]+"
    r"(\d+\s+[A-Za-z0-9 ,.#-]{5,80}?(?:Atlanta|Alpharetta|Roswell|Sandy Springs|Johns Creek|"
    r"Dunwoody|East Point|College Park|Union City|Fairburn|Palmetto)[^,\n]{0,30}(?:GA|Georgia)"
    r"[\s,]+\d{5})",
    re.IGNORECASE,
)

_ADDRESS_FALLBACK_RE = re.compile(
    r"(\d{2,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Way|Blvd|Boulevard|Circle|Cir|"
    r"Place|Pl|Terrace|Ter|Trail|Trl|Highway|Hwy|Parkway|Pkwy)[^,\n]{0,40},"
    r"\s*(?:Atlanta|Alpharetta|Roswell|Sandy Springs|Dunwoody|East Point|College Park)"
    r"[^,\n]{0,20}GA[\s,]+\d{5})",
    re.IGNORECASE,
)

# Borrower name: "from JOHN SMITH to ABC Bank" (deed to secure debt language)
_BORROWER_RE = re.compile(
    r"Deed to Secure Debt from\s+([A-Z][A-Z\s,\.'-]{3,60}?)\s+(?:to|and)\s+[A-Z]",
    re.IGNORECASE,
)

_AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)", re.IGNORECASE)


def scrape_foreclosures() -> list[dict]:
    """
    Return list of pre-foreclosure lead dicts for Fulton County.
    Each dict matches the schema used by main.py.
    """
    if not FIRECRAWL_API_KEY:
        logger.error("FIRECRAWL_API_KEY not set — skipping Georgia Public Notice scraper")
        return []

    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    leads = []

    # Use Firecrawl's extract to pull structured notice data directly
    try:
        result = app.extract(
            [SEARCH_URL],
            {
                "prompt": (
                    "This is the Georgia Public Notice website. Find all foreclosure notices "
                    "(Notice of Sale Under Power) for Fulton County Georgia. "
                    "For each notice extract: the property street address, the borrower/owner name "
                    "(the person whose property is being foreclosed), the original loan amount, "
                    "and the scheduled sale date if mentioned."
                ),
                "schema": {
                    "type": "object",
                    "properties": {
                        "notices": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "address": {"type": "string"},
                                    "owner_name": {"type": "string"},
                                    "amount": {"type": "string"},
                                    "sale_date": {"type": "string"},
                                    "raw_excerpt": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            },
        )
        notices = (result.get("data") or {}).get("notices", [])
    except Exception as exc:
        logger.warning("Firecrawl extract failed for Georgia Public Notice: %s", exc)
        notices = []

    # Fall back to scraping individual search result pages if extract returns nothing
    if not notices:
        notices = _scrape_search_pages(app)

    today = datetime.now().strftime("%Y-%m-%d")
    for notice in notices:
        address = _clean_address(notice.get("address", ""))
        owner = _clean_name(notice.get("owner_name", ""))
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
                "distress_type": "Pre-Foreclosure",
                "source": "Georgia Public Notice",
                "notes": f"Loan amt: {notice.get('amount', '')} | Sale: {notice.get('sale_date', '')}",
            }
        )

    logger.info("Georgia Public Notice: %d foreclosure leads collected", len(leads))
    return leads


def _scrape_search_pages(app: FirecrawlApp) -> list[dict]:
    """Fallback: scrape the search results page and parse notices manually."""
    notices = []
    search_url = f"{SEARCH_URL}/Index.aspx?county=Fulton&category=Foreclosures"
    try:
        result = app.scrape_url(search_url, params={"formats": ["markdown"]})
        markdown = result.get("markdown", "")
        notices = _parse_markdown_notices(markdown)
    except Exception as exc:
        logger.warning("Fallback scrape of Georgia Public Notice failed: %s", exc)
    return notices


def _parse_markdown_notices(markdown: str) -> list[dict]:
    """Extract notice data from raw markdown using regex."""
    notices = []
    # Split on notice boundaries (each notice starts with "NOTICE OF SALE")
    blocks = re.split(r"(?=NOTICE OF SALE UNDER POWER)", markdown, flags=re.IGNORECASE)
    for block in blocks:
        if len(block) < 100:
            continue
        address_match = _ADDRESS_RE.search(block) or _ADDRESS_FALLBACK_RE.search(block)
        borrower_match = _BORROWER_RE.search(block)
        amount_match = _AMOUNT_RE.search(block)
        if address_match or borrower_match:
            notices.append(
                {
                    "address": address_match.group(1).strip() if address_match else "",
                    "owner_name": borrower_match.group(1).strip() if borrower_match else "",
                    "amount": f"${amount_match.group(1)}" if amount_match else "",
                    "sale_date": "",
                    "raw_excerpt": block[:300],
                }
            )
    return notices


def _clean_address(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s{2,}", " ", raw.strip().rstrip(",. "))


def _clean_name(raw: str) -> str:
    if not raw:
        return ""
    # Remove extra whitespace, fix all-caps formatting
    name = re.sub(r"\s{2,}", " ", raw.strip())
    return name.title()


def _parse_city_state_zip(address: str) -> tuple[str, str, str]:
    m = re.search(
        r",\s*([A-Za-z\s]+),?\s+(GA|Georgia)\s+(\d{5})", address, re.IGNORECASE
    )
    if m:
        return m.group(1).strip(), "GA", m.group(3)
    return "Atlanta", "GA", ""
