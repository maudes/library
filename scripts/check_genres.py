"""Check that every listed book has a genre in data/genres.yml, and suggest one if not.

The build (build.py) writes data/cache/genre_gaps.json: the books that have no
genre yet, each with a suggested genre. This script reads that file and ignores
any book you have since added to data/genres.yml, so it needs no Notion access.

    python scripts/check_genres.py              # exit 1 if any book has no genre
    python scripts/check_genres.py --warn-only  # same report, but never fails (CI)

Run as part of scripts/check.sh (pre-push). In CI it is warning-only, so a new
book in Notion can never stop the monthly build.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.taste import title_id  # noqa: E402  (needs ROOT on sys.path first)


def missing_genres(gaps_path: Path, genres_path: Path) -> list[dict]:
    """Gaps from the last build that genres.yml doesn't cover yet."""
    if not gaps_path.exists():
        return []  # no build has recorded any gaps
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
    data = yaml.safe_load(genres_path.read_text(encoding="utf-8")) if genres_path.exists() else None
    listed = {title_id(str(t)) for titles in (data or {}).values() for t in (titles or [])}
    return [g for g in gaps if title_id(g["title"]) not in listed]


def describe(gap: dict) -> str:
    head = f'  - "{gap["title"]}" ({gap["author"]})'
    if not gap["suggested"]:
        return head + "\n      no suggestion: pick a genre from TASTE_GENRES in config.py"
    return (head + f'\n      suggested: {gap["suggested"]} ({gap["reason"]})'
            f'\n      add under "{gap["suggested"]}:" in data/genres.yml:   - "{gap["title"]}"')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--warn-only", action="store_true", help="report, but always exit 0")
    parser.add_argument("--gaps", type=Path, default=ROOT / "data" / "cache" / "genre_gaps.json")
    parser.add_argument("--genres", type=Path, default=ROOT / "data" / "genres.yml")
    args = parser.parse_args(argv)

    missing = missing_genres(args.gaps, args.genres)
    if not missing:
        print("Genre check passed: every listed book has a genre.")
        return 0

    plural = "book has" if len(missing) == 1 else "books have"
    print(f"Genre check: {len(missing)} {plural} no genre in data/genres.yml:")
    for gap in missing:
        print(describe(gap))
        if args.warn_only:  # shows up as an annotation on the GitHub Actions run
            hint = f' (suggested: {gap["suggested"]})' if gap["suggested"] else ""
            print(f'::warning title=Genre missing::"{gap["title"]}" has no genre in data/genres.yml{hint}')
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
