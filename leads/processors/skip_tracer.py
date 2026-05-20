"""
Free skip tracing using TruePeopleSearch.com.

TruePeopleSearch aggregates public records and provides phone numbers for free.
We search by owner name + state and extract the first matching result.

Expected hit rate: 40-60% (vs 80%+ with paid services like BatchSkipTracing).
To upgrade to paid skip tracing later, replace _lookup_truepeoplesearch() with
a call to your chosen API and update requirements.txt.

Rate limiting: 6-second delay between requests. This is slow but respectful
and avoids being blocked. For 50 leads it takes ~5 minutes total.
"""

import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from leads.config import SKIP_TRACE_DELAY

logger = logging.getLogger(__name__)

_TPS_BASE = "https://www.truepeoplesearch.com"
_TPS_SEARCH = f"{_TPS_BASE}/results"
_FPS_BASE = "https://www.fastpeoplesearch.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": _TPS_BASE,
    "Accept-Language": "en-US,en;q=0.9",
}

_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def skip_trace_leads(leads: list[dict]) -> list[dict]:
    """
    Attempt skip tracing for every lead. Adds phone_1, phone_2, email fields.
    Leads with no name are skipped. Returns the same list with fields populated.
    """
    for i, lead in enumerate(leads):
        owner = lead.get("owner_name", "").strip()
        if not owner or _looks_like_entity(owner):
            lead.setdefault("phone_1", "")
            lead.setdefault("phone_2", "")
            lead.setdefault("email", "")
            continue

        logger.info("Skip tracing %d/%d: %s", i + 1, len(leads), owner)
        result = _lookup_truepeoplesearch(owner, state="GA") or {}
        lead["phone_1"] = result.get("phone_1", "")
        lead["phone_2"] = result.get("phone_2", "")
        lead["email"] = result.get("email", "")

    traced = sum(1 for l in leads if l.get("phone_1"))
    logger.info("Skip trace complete: %d/%d leads have a phone number", traced, len(leads))
    return leads


def _lookup_truepeoplesearch(full_name: str, state: str = "GA") -> dict | None:
    time.sleep(SKIP_TRACE_DELAY + random.uniform(1, 3))

    params = {"name": full_name, "citystatezip": state}
    session = requests.Session()
    session.headers.update(_HEADERS)

    try:
        resp = session.get(_TPS_SEARCH, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("TruePeopleSearch request failed: %s", exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Each person result is in a card-like div; grab the first one
    card = (
        soup.find("div", attrs={"data-detail-link": True})
        or soup.find("div", class_=re.compile(r"card|result|person", re.I))
    )
    if not card:
        return None

    card_text = card.get_text(" ", strip=True)
    phones = _PHONE_RE.findall(card_text)
    emails = _EMAIL_RE.findall(card_text)

    return {
        "phone_1": _format_phone(phones[0]) if phones else "",
        "phone_2": _format_phone(phones[1]) if len(phones) > 1 else "",
        "email": emails[0] if emails else "",
    }


def _format_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def _looks_like_entity(name: str) -> bool:
    """True if the owner appears to be a company/trust, not an individual."""
    entity_words = {"llc", "inc", "corp", "trust", "estate", "holdings", "properties",
                    "realty", "investments", "bank", "financial", "mortgage"}
    return any(w in name.lower() for w in entity_words)
