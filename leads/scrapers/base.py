import time
import random
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def polite_delay(base=2.0):
    time.sleep(base + random.uniform(0.5, 2.0))


def fetch_json(url, params=None, delay=1.5):
    """Fetch a JSON endpoint directly (for ArcGIS REST APIs, etc.)."""
    polite_delay(delay)
    try:
        resp = requests.get(
            url,
            params=params,
            headers={**BROWSER_HEADERS, "Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("fetch_json failed for %s: %s", url, exc)
        return None


def fetch_html(url, params=None, delay=2.0):
    """Lightweight fallback HTML fetch (for simple static pages)."""
    polite_delay(delay)
    try:
        resp = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.warning("fetch_html failed for %s: %s", url, exc)
        return None
