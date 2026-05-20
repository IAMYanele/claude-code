#!/usr/bin/env python3
"""
Daily Lead Delivery — Fulton County GA

Runs nightly via GitHub Actions at 2 AM ET.
Delivers fresh distressed property leads to Google Sheets by 6 AM.

Sources:
  - GeorgiaPublicNotice.com  → Pre-Foreclosure (Notice of Sale Under Power)
  - Fulton County Sheriff    → Tax Delinquent (scheduled tax sales)

Pipeline:
  Scrape → Deduplicate → Enrich (GIS) → Skip Trace → Deliver

Environment variables required (store as GitHub Secrets):
  FIRECRAWL_API_KEY         — get free key at firecrawl.dev (500 credits/month)
  GOOGLE_CREDENTIALS_JSON   — service account credentials JSON (single line)
  SPREADSHEET_ID            — ID from your Google Sheet URL
"""

import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def run() -> int:
    logger.info("=" * 60)
    logger.info("Daily Lead Collection — %s", datetime.now().strftime("%Y-%m-%d"))
    logger.info("=" * 60)

    all_leads: list[dict] = []

    # ── Stage 1: Scrape ──────────────────────────────────────────────────────
    from leads.scrapers.georgia_public_notice import scrape_foreclosures
    from leads.scrapers.fulton_tax_sales import scrape_tax_sales

    logger.info("[1/4] Scraping Georgia Public Notice (foreclosures)...")
    foreclosure_leads = scrape_foreclosures()
    logger.info("      → %d leads", len(foreclosure_leads))
    all_leads.extend(foreclosure_leads)

    logger.info("[1/4] Scraping Fulton County Sheriff (tax sales)...")
    tax_leads = scrape_tax_sales()
    logger.info("      → %d leads", len(tax_leads))
    all_leads.extend(tax_leads)

    if not all_leads:
        logger.warning("No leads scraped. Check scraper logs above for errors.")
        return 1

    # ── Stage 2: Deduplicate ─────────────────────────────────────────────────
    from leads.processors.deduplicator import deduplicate

    logger.info("[2/4] Deduplicating %d raw leads...", len(all_leads))
    unique_leads = deduplicate(all_leads)
    logger.info("      → %d unique leads", len(unique_leads))

    # ── Stage 3: Enrich (property data from GIS) ─────────────────────────────
    from leads.scrapers.fulton_gis import enrich_lead

    logger.info("[3/4] Enriching with Fulton County GIS data...")
    enriched = []
    for i, lead in enumerate(unique_leads):
        enriched.append(enrich_lead(lead))
        if (i + 1) % 10 == 0:
            logger.info("      enriched %d/%d...", i + 1, len(unique_leads))
    logger.info("      → enrichment complete")

    # ── Stage 4: Skip trace ──────────────────────────────────────────────────
    from leads.processors.skip_tracer import skip_trace_leads

    logger.info("[4/4] Skip tracing leads (this takes a few minutes)...")
    final_leads = skip_trace_leads(enriched)
    traced = sum(1 for l in final_leads if l.get("phone_1"))
    logger.info("      → phone number found for %d/%d leads", traced, len(final_leads))

    # ── Deliver ──────────────────────────────────────────────────────────────
    from leads.delivery.google_sheets import append_leads

    logger.info("Delivering %d leads to Google Sheets...", len(final_leads))
    append_leads(final_leads)

    logger.info("=" * 60)
    logger.info("DONE. %d leads delivered. Your team can start dialing.", len(final_leads))
    logger.info(
        "  HIGH priority (multi-list): %d",
        sum(1 for l in final_leads if l.get("priority") == "HIGH"),
    )
    logger.info("  With phone number: %d", traced)
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run())
