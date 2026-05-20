import csv
import json
import sys
import argparse

from leads.scraper import LeadsScraper


def print_table(leads: list) -> None:
    if not leads:
        print("No leads found.")
        return
    cols = ["company_name", "email", "phone", "url"]
    rows = [lead.to_dict() for lead in leads]
    widths = {col: max(len(col), max(len(str(r.get(col) or "")) for r in rows)) for col in cols}
    print("  ".join(col.upper().ljust(widths[col]) for col in cols))
    print("  ".join("-" * widths[col] for col in cols))
    for row in rows:
        print("  ".join(str(row.get(col) or "").ljust(widths[col]) for col in cols))


def output_json(leads: list, out_file: str | None) -> None:
    text = json.dumps([l.to_dict() for l in leads], indent=2)
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
    rows = [l.to_dict() for l in leads]
    dest = open(out_file, "w", newline="") if out_file else sys.stdout
    try:
        writer = csv.DictWriter(dest, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if out_file:
            dest.close()
            print(f"Saved {len(leads)} lead(s) to {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape a list of websites and extract lead contact info.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m leads.main --url acme.com example.com\n"
            "  python -m leads.main --input urls.txt -f csv -o leads.csv\n"
            "\n"
            "urls.txt format — one URL per line:\n"
            "  https://acme.com\n"
            "  example.com\n"
            "  # comments are ignored"
        ),
    )
    parser.add_argument("--url", nargs="+", metavar="URL",
                        help="One or more URLs to scrape")
    parser.add_argument("--input", "-i", metavar="FILE",
                        help="Text file with one URL per line")
    parser.add_argument("-f", "--format", choices=["table", "json", "csv"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="Write output to a file")
    args = parser.parse_args()

    urls = list(args.url or [])

    if args.input:
        with open(args.input) as f:
            urls += f.readlines()

    if not urls:
        parser.print_help()
        print("\nNo URLs provided. Pass --url or --input.")
        sys.exit(0)

    print(f"Scraping {len(urls)} URL(s)...")
    scraper = LeadsScraper()
    leads = scraper.scrape_leads(urls)

    print(f"\n{len(leads)} lead(s) found.\n")

    if args.format == "json":
        output_json(leads, args.output)
    elif args.format == "csv":
        output_csv(leads, args.output)
    else:
        print_table(leads)


if __name__ == "__main__":
    main()
