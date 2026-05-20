import csv
import json
import os
import sys
import argparse

from leads.scraper import LeadsScraper


def print_table(leads: list) -> None:
    if not leads:
        print("No leads found.")
        return

    cols = ["company_name", "email", "phone", "contact_name", "url"]
    rows = [lead.to_dict() for lead in leads]
    widths = {col: max(len(col), max(len(str(r.get(col, "") or "")) for r in rows)) for col in cols}

    header = "  ".join(col.upper().ljust(widths[col]) for col in cols)
    divider = "  ".join("-" * widths[col] for col in cols)
    print(header)
    print(divider)
    for row in rows:
        print("  ".join(str(row.get(col, "") or "").ljust(widths[col]) for col in cols))


def output_json(leads: list, out_file: str | None) -> None:
    data = [lead.to_dict() for lead in leads]
    text = json.dumps(data, indent=2)
    if out_file:
        with open(out_file, "w") as f:
            f.write(text)
        print(f"Saved {len(leads)} lead(s) to {out_file}")
    else:
        print(text)


def output_csv(leads: list, out_file: str | None) -> None:
    if not leads:
        print("No leads to write.")
        return
    rows = [lead.to_dict() for lead in leads]
    fieldnames = list(rows[0].keys())
    dest = open(out_file, "w", newline="") if out_file else sys.stdout
    try:
        writer = csv.DictWriter(dest, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if out_file:
            dest.close()
            print(f"Saved {len(leads)} lead(s) to {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape websites for lead data using Firecrawl.",
        epilog="Example: python -m leads.main https://example.com https://acme.com",
    )
    parser.add_argument("urls", nargs="*", metavar="URL", help="One or more URLs to scrape")
    parser.add_argument(
        "--format",
        "-f",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument("--output", "-o", metavar="FILE", help="Write output to a file")
    args = parser.parse_args()

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.urls:
        parser.print_help()
        print("\nNo URLs provided — nothing to scrape.")
        sys.exit(0)

    scraper = LeadsScraper(api_key)
    leads = scraper.scrape_leads(args.urls)

    print()
    if args.format == "json":
        output_json(leads, args.output)
    elif args.format == "csv":
        output_csv(leads, args.output)
    else:
        print_table(leads)


if __name__ == "__main__":
    main()
