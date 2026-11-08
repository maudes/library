"""Numbers and lists for the "Reading taste" page.

Everything is computed here at build time, like src/stats.py. Three small
hand-edited files feed it:
  data/genres.yml  topic genre of each book you've read
  data/tbr.yml     books you want to read
  data/picks.yml   pool of acclaimed books "read next" is chosen from
"""

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

import config
from src.book import Book
from src.stats import counts_in_stats

log = logging.getLogger(__name__)


def title_id(title: str) -> str:
    """Case, width and spacing don't matter when matching titles by hand."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", title)).strip().casefold()


# ---------------------------------------------------------------------------
# Genres of the books you've read
# ---------------------------------------------------------------------------

def load_genres(path: Path, books: list[Book]) -> dict[str, str]:
    """{book id: taste genre}. Warns about typos and untagged books; never fails."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    by_title = {}
    for b in books:
        for t in (b.title, b.second_title):
            if t:
                by_title.setdefault(title_id(t), b)
    result: dict[str, str] = {}
    for genre, titles in (data or {}).items():
        if genre not in config.TASTE_GENRES:
            log.warning("genres.yml: %r is not in TASTE_GENRES (config.py)", genre)
            continue
        for title in titles or []:
            book = by_title.get(title_id(str(title)))
            if book is None:
                log.warning("genres.yml: no book titled %r", title)
            elif book.id in result:
                log.warning("genres.yml: %r is listed twice", title)
            else:
                result[book.id] = genre
    for b in books:
        if counts_in_stats(b) and b.id not in result:
            log.warning("genres.yml: %r has no genre yet (not counted on the taste page)", b.title)
    return result


def _round_shares(counts: list[int]) -> list[int]:
    """Whole percentages that add up to 100 (largest-remainder method)."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    exact = [c * 100 / total for c in counts]
    floors = [int(x) for x in exact]
    order = sorted(range(len(counts)), key=lambda i: exact[i] - floors[i], reverse=True)
    for i in order[:100 - sum(floors)]:
        floors[i] += 1
    return floors


def genre_summary(books: list[Book], genre_of: dict[str, str]) -> dict:
    """Every genre's count and average rating, plus the top-N ratio rows.

    `top` rows (and a final "Other" row for everything else) have pct values that
    add up to 100 and start/end positions for the donut chart.
    """
    tagged = [b for b in books if counts_in_stats(b) and b.id in genre_of]
    rows = []
    for g in config.TASTE_GENRES:
        members = [b for b in tagged if genre_of[b.id] == g]
        rated = [b.rating for b in members if b.rating is not None]
        rows.append({
            "genre": g, "count": len(members), "rated": len(rated),
            "avg": round(sum(rated) / len(rated)) if rated else None,
        })
    rows = [r for r in rows if r["count"]]
    # More books first; ties keep the order of TASTE_GENRES (sort is stable).
    rows.sort(key=lambda r: -r["count"])

    top = rows[:config.TASTE_TOP_GENRES]
    rest = rows[config.TASTE_TOP_GENRES:]
    chart = [dict(r) for r in top]
    if rest:
        chart.append({"genre": "Other", "count": sum(r["count"] for r in rest), "avg": None, "other": True})
    start = 0
    for r, pct in zip(chart, _round_shares([r["count"] for r in chart])):
        r["pct"], r["start"], r["end"] = pct, start, start + pct
        start += pct
    best = [r for r in rows if r["rated"] >= config.TASTE_MIN_RATED and r["avg"] is not None]
    return {
        "total": len(tagged),
        "chart": chart,
        "all": rows,
        "top_genre": rows[0]["genre"] if rows else None,
        "best_genre": max(best, key=lambda r: (r["avg"], r["count"]))["genre"] if best else None,
    }


# ---------------------------------------------------------------------------
# To-be-read list and the "read next" pool
# ---------------------------------------------------------------------------

@dataclass
class ShelfBook:
    """A book that isn't in Notion (to-read, or a recommendation)."""
    book: Book                       # gets its cover from src/enrich.py like any other book
    note: str = ""
    genre: str = ""
    sources: list[str] = field(default_factory=list)
    reason: str = ""
    shown: bool = False      # part of the first set of recommendations (the rest appear on shuffle)


def _shelf_book(prefix: str, entry: dict) -> ShelfBook | None:
    title = str(entry.get("title") or "").strip()
    author = str(entry.get("author") or "").strip()
    if not title or not author:
        log.warning("%s: an entry needs both title and author: %r", prefix, entry)
        return None
    # A stable id (cache key and cover file name) that doesn't change when the list is reordered.
    uid = hashlib.sha1(f"{title}|{author}".encode()).hexdigest()[:16]
    book = Book(
        id=f"{prefix}-{uid}", title=title, author=author, genre="", year=0,
        second_title=str(entry.get("second_title") or "").strip(),
        isbn=re.sub(r"[^0-9Xx]", "", str(entry.get("isbn") or "")),
        cover_url=str(entry.get("cover_url") or "").strip(),
    )
    genre = str(entry.get("genre") or "").strip()
    if genre and genre not in config.TASTE_GENRES:
        log.warning("%s: %r has unknown genre %r", prefix, title, genre)
        genre = ""
    sources = entry.get("sources") or []
    return ShelfBook(book=book, note=str(entry.get("note") or "").strip(), genre=genre,
                     sources=[str(s) for s in sources])


def _load_shelf(path: Path, prefix: str) -> list[ShelfBook]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    items = [_shelf_book(prefix, e) for e in (data or []) if isinstance(e, dict)]
    return [i for i in items if i]


def load_tbr(path: Path) -> list[ShelfBook]:
    return _load_shelf(path, "tbr")


def load_pool(path: Path) -> list[ShelfBook]:
    return _load_shelf(path, "pick")


def recommend(pool: list[ShelfBook], summary: dict, books: list[Book],
              tbr: list[ShelfBook], n: int | None = None) -> list[ShelfBook]:
    """Every pool book that fits your taste, best first, each with a reason.

    score = how much you read the genre x how highly you rate it, plus a small
    bonus per list the book appears on. Books you've read or already want to
    read are left out. The first n books with distinct genres are marked
    `shown` (the page's first set); the page's Shuffle button picks other
    combinations from the rest.
    """
    n = config.TASTE_PICKS if n is None else n
    known = {title_id(t) for b in books for t in (b.title, b.second_title) if t}
    known |= {title_id(s.book.title) for s in tbr}
    by_genre = {r["genre"]: r for r in summary["all"]}
    total = summary["total"] or 1

    scored = []
    for s in pool:
        if title_id(s.book.title) in known or (s.book.second_title and title_id(s.book.second_title) in known):
            continue
        row = by_genre.get(s.genre)
        share = row["count"] / total if row else 0
        avg = (row["avg"] or 70) / 100 if row else 0.7
        if row:
            avg_text = f", {row['avg']}% on average" if row["avg"] is not None else ""
            s.reason = f"You've read {row['count']} in {s.genre}{avg_text}"
        else:
            s.reason = "Something outside your usual genres"
        scored.append((share * avg + 0.04 * len(s.sources), s))
    scored.sort(key=lambda t: -t[0])

    seen = set()
    for _, s in scored:
        if len(seen) < n and s.genre not in seen:
            seen.add(s.genre)
            s.shown = True
    return [s for _, s in scored]


def build_taste(books: list[Book], all_time: dict, genre_of: dict[str, str],
                tbr: list[ShelfBook], pool: list[ShelfBook]) -> dict:
    """Everything templates/taste.html shows."""
    summary = genre_summary(books, genre_of)
    return {
        "summary": summary,
        "genre_of": genre_of,
        "top_books": all_time["top10"],
        "total": all_time["total"],
        "avg_rating": all_time["avg_rating"],
        "picks": recommend(pool, summary, books, tbr),
        "picks_count": config.TASTE_PICKS,
        "tbr": tbr,
        "playlist_id": config.PLAYLIST_ID,
        "playlist_title": config.PLAYLIST_TITLE,
    }
