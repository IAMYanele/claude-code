import re
import sys
from typing import Optional

from firecrawl import Firecrawl
from firecrawl.v1.client import V1JsonConfig, V1ScrapeOptions


LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "description": "Company or organization name"},
        "email": {"type": "string", "description": "Primary contact email address"},
        "phone": {"type": "string", "description": "Primary phone number"},
        "address": {"type": "string", "description": "Physical address"},
        "description": {"type": "string", "description": "What the company does in one sentence"},
        "contact_name": {"type": "string", "description": "Key contact person full name"},
        "contact_title": {"type": "string", "description": "Contact person job title"},
    },
}

LEAD_PROMPT = (
    "Extract lead information from this page. Look for the company name, "
    "contact email, phone number, physical address, a brief description of "
    "what the company does, and the key contact person's name and title."
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{6,}\d)")


class Lead:
    def __init__(self, url: str, data: dict, title: str = "", description: str = ""):
        self.url = url
        self.company_name = data.get("company_name") or title or ""
        self.email = data.get("email") or ""
        self.phone = data.get("phone") or ""
        self.address = data.get("address") or ""
        self.description = data.get("description") or description or ""
        self.contact_name = data.get("contact_name") or ""
        self.contact_title = data.get("contact_title") or ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "company_name": self.company_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "description": self.description,
            "contact_name": self.contact_name,
            "contact_title": self.contact_title,
        }


def _extract_from_markdown(url: str, markdown: str, title: str, description: str) -> Lead:
    emails = _EMAIL_RE.findall(markdown)
    phones = _PHONE_RE.findall(markdown)
    return Lead(url, {
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
    }, title=title, description=description)


class LeadsScraper:
    def __init__(self, api_key: str):
        self.app = Firecrawl(api_key=api_key)

    # --- search-driven flow ---

    def find_leads(self, query: str, limit: int = 10) -> list:
        """Search for leads matching `query`, then scrape each result."""
        scrape_opts = V1ScrapeOptions(
            formats=["extract", "markdown"],
            extract=V1JsonConfig(prompt=LEAD_PROMPT, schema=LEAD_SCHEMA),
        )
        v1 = self.app._v1_client
        result = v1.search(query, limit=limit, scrape_options=scrape_opts)
        leads = []
        for doc in result.data:
            url = doc.url or ""
            title = doc.title or ""
            description = doc.description or ""
            if doc.extract and isinstance(doc.extract, dict):
                lead = Lead(url, doc.extract, title=title, description=description)
            elif doc.markdown:
                lead = _extract_from_markdown(url, doc.markdown, title, description)
            else:
                lead = Lead(url, {}, title=title, description=description)
            leads.append(lead)
            name = lead.company_name or "(unnamed)"
            print(f"  {name} — {url}")
        return leads

    # --- direct URL scrape flow ---

    def scrape_lead(self, url: str) -> Optional[Lead]:
        try:
            result = self.app._v1_client.scrape_url(
                url,
                formats=["extract", "markdown"],
                extract=V1JsonConfig(prompt=LEAD_PROMPT, schema=LEAD_SCHEMA),
            )
            if result.extract and isinstance(result.extract, dict):
                return Lead(url, result.extract)
            if result.markdown:
                return _extract_from_markdown(url, result.markdown, "", "")
            return None
        except Exception as exc:
            print(f"  Error scraping {url}: {exc}", file=sys.stderr)
            return None

    def scrape_leads(self, urls: list) -> list:
        leads = []
        for url in urls:
            print(f"Scraping {url} ...")
            lead = self.scrape_lead(url)
            if lead:
                leads.append(lead)
                print(f"  Found: {lead.company_name or '(unnamed)'}")
            else:
                print("  No data extracted.")
        return leads
