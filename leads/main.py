import csv
import json
import os
import sys
import argparse

from leads.scraper import LeadsScraper

_ALLOWLIST_HINT = (
    "\nThis usually means your Firecrawl API key has an IP allowlist configured.\n"
    "Fix: go to app.firecrawl.dev → API Keys → remove the IP restriction, or add\n"
    "this server's IP to the allowed list."
)


def print_table(leads: list) -> None:
    if not leads:
        print("No leads found.")
        return
    cols = ["company_name", "email", "phone", "contact_name", "url"]
    rows = [lead.to_dict() for lead in leads]
    widths = {col: max(len(col), max(len(str(r.get(col) or "")) for r in rows)) for col in cols}
    header = "  ".join(col.upper().ljust(widths[col]) for col in cols)
    divider = "  ".join("-" * widths[col] for col in cols)
    print(header)
    print(divider)
    for row in rows:
        print("  ".join(str(row.get(col) or "").ljust(widths[col]) for col in cols))


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
        description="Generate leads by searching the web with Firecrawl.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m leads.main 'marketing agencies in Austin'\n"
            "  python -m leads.main 'e-commerce startups NYC' --limit 20 --format csv -o leads.csv\n"
            "  python -m leads.main --url https://example.com https://acme.com"
        ),
    )
    parser.add_argument("query", nargs="?", metavar="QUERY",
                        help="Search query describing the leads you want (e.g. 'law firms in Chicago')")
    parser.add_argument("--url", nargs="+", metavar="URL",
                        help="Scrape specific URLs instead of searching")
    parser.add_argument("--limit", "-n", type=int, default=10,
                        help="Max results when using a search query (default: 10)")
    parser.add_argument("--format", "-f", choices=["table", "json", "csv"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--output", "-o", metavar="FILE",
                        help="Write output to a file")
    args = parser.parse_args()

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.query and not args.url:
        args.query = input("What leads are you looking for? (e.g. 'SaaS companies in London'): ").strip()
        if not args.query:
            parser.print_help()
            sys.exit(0)

    scraper = LeadsScraper(api_key)

    try:
        if args.url:
            print(f"Scraping {len(args.url)} URL(s)...")
            leads = scraper.scrape_leads(args.url)
        else:
            print(f"Searching for: {args.query!r}  (limit {args.limit})")
            leads = scraper.find_leads(args.query, limit=args.limit)
    except Exception as exc:
        msg = str(exc)
        if "allowlist" in msg.lower() or "403" in msg:
            print(f"\nError: Firecrawl API key is restricted. {_ALLOWLIST_HINT}", file=sys.stderr)
        else:
            print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(leads)} lead(s) found.\n")

    if args.format == "json":
        output_json(leads, args.output)
    elif args.format == "csv":
        output_csv(leads, args.output)
    else:
        print_table(leads)


if __name__ == "__main__":
    main()
