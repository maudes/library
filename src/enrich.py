"""Fill in missing ISBNs and covers from Google Books, then Open Library.

Rules:
- ISBN / Cover URL typed in Notion always win; no lookup for those.
- Results (including "not found") are cached in data/cache/books.json,
  keyed by Notion page id, so each book is looked up once.
- "Not found" is retried after config.RETRY_NOT_FOUND_DAYS days.
- If the title/author in Notion changes, the cached result is discarded.
- Network errors never fail the build; the book just shows the placeholder.
- Covers are downloaded into static/covers/ (no hotlinking).
"""

import json
import logging
import re
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import requests

import config
from src.book import Book

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "data" / "cache" / "books.json"
COVERS_DIR = ROOT / "static" / "covers"

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


class LookupError_(Exception):
    """A source could not be reached (as opposed to "reached, but no match")."""


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _latin_share(text: str) -> float:
    """Fraction of the letters in `text` that are Latin (a–z, with accents)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for c in letters if unicodedata.normalize("NFD", c)[0].isascii())
    return latin / len(letters)


def is_english(text: str) -> bool:
    """True when most letters are Latin (so "1Q84（1）" or "AI 時代" don't count)."""
    return _latin_share(text) > 0.5


def _norm(text: str) -> str:
    """Lower-case, accents removed, punctuation and spaces removed."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def _title_core(text: str) -> str:
    """Title without subtitle / series number: "Sapiens: A Brief…" -> "sapiens"."""
    text = re.split(r"[:：(（—–]| - ", text)[0]
    return _norm(text)


def _author_tokens(text: str) -> set[str]:
    """Words of an author name; for Chinese/Japanese names, the characters themselves."""
    tokens = set()
    for part in re.split(r"[\s/,、&;.]+|等", text):
        n = _norm(part)
        if not n:
            continue
        if is_english(part):
            if len(n) > 1:          # skip initials like "S."
                tokens.add(n)
        else:
            tokens.update(n)        # each CJK character
    return tokens


def authors_match(ours: str, theirs: list[str]) -> bool:
    mine = _author_tokens(ours)
    other = set().union(*(_author_tokens(a) for a in theirs)) if theirs else set()
    shared = mine & other
    # Latin names: one shared surname/given-name word is enough.
    # CJK names: need two shared characters (a single common character is too weak).
    return any(len(t) > 1 for t in shared) or len(shared) >= 2


def titles_match(ours: str, theirs: str) -> bool:
    """Main titles (before any ":" subtitle) must be identical.

    Substring matching is too loose: "Sapiens" would match "Summary of Sapiens".
    """
    a, b = _title_core(ours), _title_core(theirs)
    return bool(a) and a == b


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _get_json(url: str, params: dict) -> dict:
    try:
        resp = _session.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise LookupError_(str(exc)) from exc
    if resp.status_code != 200:
        raise LookupError_(f"HTTP {resp.status_code} from {url}")
    time.sleep(0.3)  # be polite to free APIs
    return resp.json()


def _pick_isbn13(isbns: list[str]) -> str:
    clean = [re.sub(r"[^0-9X]", "", i) for i in isbns]
    for i in clean:
        if len(i) == 13 and i[:3] in ("978", "979"):
            return i
    return ""


def search_google(title: str, author: str, api_key: str = "") -> list[dict]:
    # Plain keywords: Google's intitle:/inauthor: operators currently return
    # nothing. Results are checked by title and author in find_match anyway.
    q = f"{title} {author}".strip()
    params = {"q": q, "maxResults": 10, "printType": "books"}
    if api_key:
        params["key"] = api_key
    data = _get_json("https://www.googleapis.com/books/v1/volumes", params)
    results = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        isbns = [x.get("identifier", "") for x in info.get("industryIdentifiers", [])
                 if x.get("type") == "ISBN_13"]
        image = (info.get("imageLinks") or {}).get("thumbnail", "")
        if image:
            # https, and a larger rendition than the default thumbnail
            image = image.replace("http://", "https://").replace("&edge=curl", "")
        # publishedDate is "2019", "2019-05" or "2019-05-01": the year of THIS edition.
        year = (info.get("publishedDate") or "")[:4]
        results.append({
            "title": " ".join(filter(None, [info.get("title", ""), info.get("subtitle", "")])),
            "authors": info.get("authors", []),
            "isbn": _pick_isbn13(isbns),
            "cover": image,
            "published": int(year) if year.isdigit() else None,
            "source": "google",
        })
    return results


def search_open_library(title: str, author: str) -> list[dict]:
    params = {"title": title, "limit": 5, "fields": "title,author_name,isbn,cover_i"}
    if author:
        params["author"] = author
    data = _get_json("https://openlibrary.org/search.json", params)
    results = []
    for doc in data.get("docs", []):
        cover = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg" if doc.get("cover_i") else ""
        results.append({
            "title": doc.get("title", ""),
            "authors": doc.get("author_name", []),
            "isbn": _pick_isbn13(doc.get("isbn", [])),
            "cover": cover,
            # Open Library search only gives the ORIGINAL first-publication year,
            # not the edition's, so it isn't used for Published Year.
            "published": None,
            "source": "openlibrary",
        })
    return results


# ---------------------------------------------------------------------------
# Choosing the right result
# ---------------------------------------------------------------------------

def search_plans(book: Book) -> list[str]:
    """Titles to search for, in order (always together with the author).

    The Main Title first (for Chinese titles this finds the edition you
    actually read), then the second title if it's in English.

    A result must match BOTH title and author. Title-only matches were tried
    and rejected: common titles (e.g. "Never Let Me Go") collide with other
    books, and a wrong cover is worse than the placeholder. For books that
    aren't found, fill in ISBN / Cover URL in Notion.
    """
    titles = [book.title]
    if book.second_title and is_english(book.second_title) and book.second_title != book.title:
        titles.append(book.second_title)
    return titles


def find_match(book: Book, api_key: str = "") -> dict | None:
    """Return the best result, or None if every source answered "no match".

    Raises LookupError_ if a source failed and nothing was found, so the
    caller can avoid caching a false "not found".
    """
    failed = False
    for search in (lambda t, a: search_google(t, a, api_key), search_open_library):
        for title in search_plans(book):
            try:
                results = search(title, book.author)
            except LookupError_ as exc:
                log.info("Lookup failed for %r: %s", book.title, exc)
                failed = True
                break  # this source is down; try the next source
            for r in results:
                if titles_match(title, r["title"]) and authors_match(book.author, r["authors"]):
                    return r
    if failed:
        raise LookupError_("one or more sources unavailable")
    return None


# ---------------------------------------------------------------------------
# Covers
# ---------------------------------------------------------------------------

def _safe_name(book_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", book_id)


def download_cover(url: str, book_id: str) -> str:
    """Save an image to static/covers/; return its path relative to static/ ("" on failure)."""
    try:
        resp = _session.get(url, timeout=config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        log.info("Cover download failed for %s: %s", book_id, exc)
        return ""
    kind = resp.headers.get("Content-Type", "")
    # Tiny images are "no cover available" placeholders from the APIs.
    if resp.status_code != 200 or not kind.startswith("image/") or len(resp.content) < 2000:
        return ""
    ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(kind.split(";")[0], ".jpg")
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(book_id) + ext
    (COVERS_DIR / name).write_bytes(resp.content)
    return f"covers/{name}"


def _openlibrary_cover_by_isbn(isbn: str) -> str:
    # ?default=false makes Open Library return 404 instead of a blank image
    return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")


def _signature(book: Book) -> str:
    """Changes when the fields used for the lookup change in Notion."""
    return "|".join([book.title, book.second_title, book.author, book.isbn, book.cover_url])


def _cover_exists(path: str) -> bool:
    return bool(path) and (COVERS_DIR.parent / path).exists()


def enrich(books: list[Book], api_key: str = "", today: date | None = None,
           offline: bool = False, prune: bool = True) -> None:
    """Fill book.isbn and book.cover in place, using and updating the cache.

    offline=True only uses what's already cached (no network at all).
    prune=True removes cache entries and cover files for books that are no
    longer in Notion. Turn it off for CSV builds, whose ids differ from Notion's.
    """
    today = today or date.today()
    cache = load_cache()
    stats = {"cached": 0, "looked_up": 0, "found": 0, "not_found": 0, "errors": 0}

    for book in books:
        entry = cache.get(book.id)
        sig = _signature(book)
        fresh = (
            entry is not None
            and entry.get("signature") == sig
            # Entries cached before Published Year existed are looked up once more.
            and "published_year" in entry
            and (entry.get("cover") == "" or _cover_exists(entry.get("cover", "")))
            and not (
                entry.get("status") == "not_found"
                and date.fromisoformat(entry["checked"]) + timedelta(days=config.RETRY_NOT_FOUND_DAYS) <= today
            )
        )

        if not fresh and not offline:
            entry = _lookup(book, api_key, sig, today, stats)
            if entry is not None:
                cache[book.id] = entry
            # Save progress regularly so an interrupted build keeps its work.
            if stats["looked_up"] % 10 == 0:
                save_cache(cache)
        elif fresh:
            stats["cached"] += 1

        if entry:
            book.isbn = book.isbn or entry.get("isbn", "")
            book.cover = entry.get("cover", "") if _cover_exists(entry.get("cover", "")) else ""
            # A year typed in Notion always wins over the looked-up one.
            book.published_year = book.published_year or entry.get("published_year")

    if prune:
        # Drop cache entries and covers for books that no longer exist in Notion.
        live = {b.id for b in books}
        for stale in [k for k in cache if k not in live]:
            del cache[stale]
        used = {Path(e.get("cover", "")).name for e in cache.values() if e.get("cover")}
        if COVERS_DIR.exists():
            for f in COVERS_DIR.iterdir():
                if f.name != ".gitkeep" and f.name not in used:
                    f.unlink()

    save_cache(cache)
    log.info("Covers/ISBN: %s", ", ".join(f"{k}={v}" for k, v in stats.items()))


def _lookup(book: Book, api_key: str, sig: str, today: date, stats: dict) -> dict | None:
    """Look one book up. Returns a cache entry, or None if we should retry next build."""
    stats["looked_up"] += 1
    entry = {"signature": sig, "checked": today.isoformat(), "isbn": "", "cover": "",
             "published_year": None, "source": ""}

    match = None
    # Only search when Notion didn't already give us both values.
    if not (book.isbn and book.cover_url):
        try:
            match = find_match(book, api_key)
        except LookupError_:
            stats["errors"] += 1
            if not book.isbn and not book.cover_url:
                return None  # sources were down; don't cache a false "not found"

    isbn = book.isbn or (match or {}).get("isbn", "")
    cover_candidates = [book.cover_url, (match or {}).get("cover", "")]
    if isbn:
        cover_candidates.append(_openlibrary_cover_by_isbn(isbn))

    cover = ""
    for url in filter(None, cover_candidates):
        cover = download_cover(url, book.id)
        if cover:
            break

    entry.update(isbn=isbn if not book.isbn else "", cover=cover,
                 published_year=(match or {}).get("published"),
                 source=(match or {}).get("source", "notion" if book.isbn or book.cover_url else ""))
    entry["status"] = "found" if (isbn or cover) else "not_found"
    stats["found" if entry["status"] == "found" else "not_found"] += 1
    return entry
