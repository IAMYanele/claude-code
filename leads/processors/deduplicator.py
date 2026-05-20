"""
Deduplicates leads by address.

If the same property appears on multiple distress lists (e.g. both tax delinquent
AND pre-foreclosure), that's a HIGH PRIORITY signal — multiple financial pressures
on the same owner. We merge those records and flag them accordingly.
"""

import re
import logging

logger = logging.getLogger(__name__)

_STREET_TYPE_MAP = {
    "street": "st", "avenue": "ave", "road": "rd", "drive": "dr",
    "lane": "ln", "court": "ct", "boulevard": "blvd", "circle": "cir",
    "place": "pl", "terrace": "ter", "trail": "trl", "highway": "hwy",
    "parkway": "pkwy", "way": "way",
}


def deduplicate(leads: list[dict]) -> list[dict]:
    """
    Collapse duplicate addresses. Multi-source matches are flagged HIGH priority.
    Returns a flat list of unique leads sorted by priority (HIGH first).
    """
    buckets: dict[str, list[dict]] = {}

    for lead in leads:
        key = _address_key(lead.get("address", ""))
        if not key:
            key = _name_key(lead.get("owner_name", ""))
        if not key:
            continue
        buckets.setdefault(key, []).append(lead)

    merged = []
    for key, group in buckets.items():
        merged.append(_merge_group(group))

    high = [l for l in merged if l.get("priority") == "HIGH"]
    normal = [l for l in merged if l.get("priority") != "HIGH"]
    result = high + normal
    logger.info(
        "Deduplication: %d raw leads → %d unique (%d HIGH priority)",
        len(leads), len(result), len(high),
    )
    return result


def _merge_group(group: list[dict]) -> dict:
    """Merge duplicate records. Prefer the most complete value for each field."""
    if len(group) == 1:
        base = group[0].copy()
        base.setdefault("priority", "NORMAL")
        return base

    # Multiple signals on same property → HIGH priority
    base = group[0].copy()
    for other in group[1:]:
        for field, value in other.items():
            if value and not base.get(field):
                base[field] = value

    sources = list({g.get("source", "") for g in group if g.get("source")})
    distress_types = list({g.get("distress_type", "") for g in group if g.get("distress_type")})
    base["source"] = " + ".join(sources)
    base["distress_type"] = " + ".join(distress_types)
    base["priority"] = "HIGH"
    base["notes"] = (
        f"[MULTI-LIST: {len(group)} signals] " + (base.get("notes") or "")
    ).strip()
    return base


def _address_key(address: str) -> str:
    """Normalize an address to a stable comparison key."""
    if not address:
        return ""
    key = address.lower()
    key = re.sub(r"[^\w\s]", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    for long, short in _STREET_TYPE_MAP.items():
        key = re.sub(rf"\b{long}\b", short, key)
    # Keep only street number + first two words of street name (ignore city/state/zip)
    parts = key.split()
    return " ".join(parts[:4]) if len(parts) >= 2 else key


def _name_key(name: str) -> str:
    """Fallback key from owner name when address is missing."""
    if not name:
        return ""
    return re.sub(r"\s+", "", name.lower())
