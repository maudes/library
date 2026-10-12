"""Build the site.

    python build.py                    # read Notion (needs .env), look up covers, write site/
    python build.py --csv export.csv   # use a Notion CSV export instead of the API
    python build.py --offline          # no cover/ISBN lookups; only use the cache
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.enrich import enrich
from src.notion_source import load_from_csv, load_from_notion
from src.render import render
from src.stats import build_stats

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Maude's Library into site/")
    parser.add_argument("--csv", help="read books from a Notion CSV export instead of the API")
    parser.add_argument("--offline", action="store_true", help="skip cover/ISBN lookups (use cache only)")
    parser.add_argument("--out", default=str(ROOT / "site"), help="output folder (default: site/)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    # Hide per-request noise from the HTTP libraries.
    for noisy in ("httpx", "urllib3", "notion_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger("build")

    load_dotenv(ROOT / ".env")

    if args.csv:
        books = load_from_csv(args.csv)
    else:
        token = os.environ.get("NOTION_TOKEN")
        database_id = os.environ.get("NOTION_DATABASE_ID")
        if not token or not database_id:
            log.error("NOTION_TOKEN and NOTION_DATABASE_ID must be set (in .env locally, or GitHub Secrets).")
            return 1
        books = load_from_notion(token, database_id)
    log.info("Loaded %d books", len(books))

    # CSV rows have different ids from Notion pages, so never prune the
    # (Notion-keyed) cache during a CSV build.
    enrich(books, api_key=os.environ.get("GOOGLE_BOOKS_API_KEY", ""),
           offline=args.offline, prune=not args.csv)
    stats = build_stats(books)
    render(books, stats, Path(args.out))
    log.info("Site written to %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
