import sys
from typing import Optional

from firecrawl import Firecrawl
from firecrawl.v1.client import V1JsonConfig


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
        "website": {"type": "string", "description": "Company website URL"},
    },
}

LEAD_PROMPT = (
    "Extract lead information from this page. Look for the company name, "
    "contact email, phone number, physical address, a brief description of "
    "what the company does, and the key contact person's name and title."
)


class Lead:
    def __init__(self, url: str, data: dict):
        self.url = url
        self.company_name = data.get("company_name") or ""
        self.email = data.get("email") or ""
        self.phone = data.get("phone") or ""
        self.address = data.get("address") or ""
        self.description = data.get("description") or ""
        self.contact_name = data.get("contact_name") or ""
        self.contact_title = data.get("contact_title") or ""
        self.website = data.get("website") or url

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
            "website": self.website,
        }


class LeadsScraper:
    def __init__(self, api_key: str):
        self.app = Firecrawl(api_key=api_key)

    def scrape_lead(self, url: str) -> Optional[Lead]:
        try:
            result = self.app.v1.scrape_url(
                url,
                formats=["extract"],
                extract=V1JsonConfig(prompt=LEAD_PROMPT, schema=LEAD_SCHEMA),
            )
            data = getattr(result, "extract", None)
            if data is None and isinstance(result, dict):
                data = result.get("extract")
            if data and isinstance(data, dict):
                return Lead(url, data)
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
                name = lead.company_name or "(unnamed)"
                print(f"  Found: {name}")
            else:
                print("  No data extracted.")
        return leads
