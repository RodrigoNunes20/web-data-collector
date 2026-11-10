"""Command line interface: `python -m collector books|github ...`."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__, books, github
from .exporters import SummaryLine, export
from .http import Fetcher, FetchError, build_session

SUPPORTED_OUTPUTS = {".xlsx", ".csv", ".json"}

BOOK_SUMMARY: list[SummaryLine] = [
    ("Total books", "=COUNTA({title})", "#,##0"),
    ("Average price (GBP)", "=IFERROR(AVERAGE({price_gbp}),0)", "#,##0.00"),
    ("Cheapest (GBP)", "=MIN({price_gbp})", "#,##0.00"),
    ("Most expensive (GBP)", "=MAX({price_gbp})", "#,##0.00"),
    ("In stock", "=COUNTIF({in_stock},TRUE)", "#,##0"),
    ("Rated 5 stars", "=COUNTIF({rating},5)", "#,##0"),
    ("Rated 4 stars", "=COUNTIF({rating},4)", "#,##0"),
    ("Rated 3 stars", "=COUNTIF({rating},3)", "#,##0"),
    ("Rated 2 stars", "=COUNTIF({rating},2)", "#,##0"),
    ("Rated 1 star", "=COUNTIF({rating},1)", "#,##0"),
]

GITHUB_SUMMARY: list[SummaryLine] = [
    ("Repositories", "=COUNTA({name})", "#,##0"),
    ("Total stars", "=SUM({stars})", "#,##0"),
    ("Total forks", "=SUM({forks})", "#,##0"),
    ("Open issues", "=SUM({open_issues})", "#,##0"),
    ("Most starred repository", '=IFERROR(INDEX({name},MATCH(MAX({stars}),{stars},0)),"-")', "General"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="collector", description="Collect web and API data into CSV, JSON or Excel.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", type=Path, required=True, help="Output file (.xlsx, .csv or .json)")
    common.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between requests (default 1.0)")
    common.add_argument("-q", "--quiet", action="store_true", help="Only print errors")

    p_books = sub.add_parser("books", parents=[common], help="Scrape the practice bookstore books.toscrape.com")
    p_books.add_argument("--start-url", default=books.DEFAULT_START_URL, help="First listing page to read")
    p_books.add_argument("--max-pages", type=int, default=5, help="Maximum number of listing pages (20 books each)")

    p_gh = sub.add_parser("github", parents=[common], help="List the public repositories of a GitHub user")
    p_gh.add_argument("user", help="GitHub username")
    p_gh.add_argument("--skip-forks", action="store_true", help="Leave out forked repositories")
    return parser


def main(argv: Optional[Sequence[str]] = None, fetcher: Optional[Fetcher] = None) -> int:
    args = build_parser().parse_args(argv)
    log = (lambda message: None) if args.quiet else print

    if args.output.suffix.lower() not in SUPPORTED_OUTPUTS:  # fail early, before any network traffic
        print(f"Error: unsupported output format '{args.output.suffix}'. Use .xlsx, .csv or .json", file=sys.stderr)
        return 2

    if fetcher is None:
        headers = {}
        token = os.environ.get("GITHUB_TOKEN")
        if args.command == "github" and token:
            headers["Authorization"] = f"Bearer {token}"
        fetcher = Fetcher(delay=args.delay, session=build_session(headers=headers))

    try:
        if args.command == "books":
            if args.max_pages < 1:
                print("Error: --max-pages must be at least 1", file=sys.stderr)
                return 2
            found = books.crawl(
                fetcher.get_text,
                start_url=args.start_url,
                max_pages=args.max_pages,
                on_page=lambda n, url, count: log(f"  page {n}: {count} books ({url})"),
            )
            rows = [book.to_dict() for book in found]
            columns, summary, title = books.COLUMNS, BOOK_SUMMARY, "Books collected"
        else:
            rows = github.fetch_repos(fetcher.get_json, args.user, include_forks=not args.skip_forks)
            columns, summary, title = github.COLUMNS, GITHUB_SUMMARY, f"GitHub repositories: {args.user}"

        if not rows:
            print("Error: no data found. Check the address or username.", file=sys.stderr)
            return 1
        export(rows, args.output, columns, summary, title)
    except FetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except PermissionError:
        print(f"Error: cannot write {args.output}. Is the file open in another program?", file=sys.stderr)
        return 1

    log(f"Saved {len(rows)} rows to {args.output}")
    return 0
