import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?1?[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})")


class Lead:
    def __init__(self, url: str, company_name: str = "", email: str = "",
                 phone: str = "", description: str = ""):
        self.url = url
        self.company_name = company_name
        self.email = email
        self.phone = phone
        self.description = description

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "company_name": self.company_name,
            "email": self.email,
            "phone": self.phone,
            "description": self.description,
        }


def scrape_url(url: str) -> Optional[Lead]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  {url}: {exc}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    title = soup.find("title")
    company_name = title.get_text(strip=True) if title else ""

    desc_tag = (soup.find("meta", attrs={"name": "description"}) or
                soup.find("meta", attrs={"property": "og:description"}))
    description = (desc_tag.get("content") or "") if desc_tag else ""

    text = soup.get_text(" ")
    emails = [e for e in _EMAIL_RE.findall(text)
              if not e.endswith((".png", ".jpg", ".svg", ".gif"))]
    phones = _PHONE_RE.findall(text)

    return Lead(
        url=url,
        company_name=company_name[:80],
        email=emails[0] if emails else "",
        phone=phones[0].strip() if phones else "",
        description=description[:200],
    )


class LeadsScraper:
    def scrape_leads(self, urls: list) -> list:
        leads = []
        for url in urls:
            url = url.strip()
            if not url or url.startswith("#"):
                continue
            if not url.startswith("http"):
                url = "https://" + url
            print(f"  {url} ...", end=" ", flush=True)
            lead = scrape_url(url)
            if lead:
                leads.append(lead)
                print(lead.email or "(no email found)")
            else:
                print("failed")
        return leads
