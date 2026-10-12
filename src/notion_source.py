"""Read books from Notion (or from a Notion CSV export) into Book records.

Both sources go through `make_book`, so cleanup and validation rules are the
same no matter where the data came from.
"""

import csv
import hashlib
import logging
import re
import unicodedata
from datetime import date

import config
from src.book import Book

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared cleanup / validation
# ---------------------------------------------------------------------------

def _clean_text(value) -> str:
    """Trim and collapse runs of whitespace; None -> ""."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(str(value).replace("%", "").strip())))
    except ValueError:
        return None


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def make_book(page_id: str, raw: dict) -> Book | None:
    """Build a Book from {internal field name: raw value}.

    Returns None (and logs a warning) if a required field is missing or invalid,
    so one bad row never stops the build.
    """
    title = _clean_text(raw.get("title"))
    label = title or f"(untitled row {page_id})"

    # Genre may come from a multi-select column: a book should have exactly one.
    genre_value = raw.get("genre")
    if isinstance(genre_value, list):
        if len(genre_value) > 1:
            log.warning("%r has several genres %s — using %r", label, genre_value, genre_value[0])
        genre_value = genre_value[0] if genre_value else None
    notion_genre = _clean_text(genre_value)
    genre = config.GENRE_MAP.get(notion_genre)
    values = {
        "title": title,
        "author": _clean_text(raw.get("author")),
        "genre": genre,
        "year": _to_int(raw.get("year")),
    }
    if notion_genre and genre is None:
        log.warning("Skipping %r: unknown genre %r (add it to GENRE_MAP in config.py)", label, notion_genre)
        return None
    missing = [f for f in config.REQUIRED if not values.get(f)]
    if missing:
        log.warning("Skipping %r: missing %s", label, ", ".join(missing))
        return None
    if re.match(r"https?://", title):
        log.warning("Title of %r looks like a link — please fix it in Notion", title)

    rating = _to_int(raw.get("rating"))
    if rating is not None and not 0 <= rating <= 100:
        log.warning("Ignoring rating %s for %r (must be 0–100)", rating, label)
        rating = None

    return Book(
        id=page_id,
        title=title,
        second_title=_clean_text(raw.get("second_title")),
        author=values["author"],
        rating=rating,
        genre=genre,
        year=values["year"],
        summary=_clean_text(raw.get("summary")),
        finished_date=_to_date(raw.get("finished_date")),
        isbn=re.sub(r"[^0-9Xx]", "", _clean_text(raw.get("isbn"))),
        cover_url=_clean_text(raw.get("cover_url")),
    )


def capitalize_words(text: str) -> str:
    """"My sister, the serial killer" -> "My Sister, The Serial Killer".

    Only the first letter of each word changes; the rest stays as typed, so
    "1Q84" and "McAvoy" are untouched. Titles that are mostly Chinese are
    left alone.
    """
    if not _is_mostly_latin(text):
        return text
    return re.sub(r"(^|[\s(\"“‘])([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), text)


def _is_mostly_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    latin = sum(1 for c in letters if unicodedata.normalize("NFD", c)[0].isascii())
    return bool(letters) and latin / len(letters) > 0.5


def capitalize_titles(books: list[Book]) -> None:
    """Apply capitalize_words to every English Main / Second Title (display only).

    Run this AFTER enrich(): the cover cache is keyed on the titles as typed in
    Notion, so changing them earlier would trigger a full re-lookup.
    """
    for b in books:
        b.title = capitalize_words(b.title)
        b.second_title = capitalize_words(b.second_title)


def _field_names() -> dict[str, str]:
    """Internal field -> Notion column name, including the optional date column."""
    names = {k: v for k, v in config.PROPERTIES.items() if v}
    if config.DATE_PROPERTY:
        names["finished_date"] = config.DATE_PROPERTY
    return names


# ---------------------------------------------------------------------------
# Notion API
# ---------------------------------------------------------------------------

def _property_value(prop: dict, percent: bool = False):
    """Extract a plain Python value from one Notion property object."""
    kind = prop.get("type")
    if kind in ("title", "rich_text"):
        return "".join(t.get("plain_text", "") for t in prop[kind])
    if kind == "number":
        value = prop["number"]
        # A number column formatted as "percent" stores 60% as 0.6.
        if value is not None and percent:
            value = value * 100
        return value
    if kind == "select":
        return prop["select"]["name"] if prop["select"] else None
    if kind == "multi_select":
        # Returned as a list; make_book decides what to do with several values.
        return [o["name"] for o in prop["multi_select"]]
    if kind == "date":
        return prop["date"]["start"] if prop["date"] else None
    if kind == "url":
        return prop["url"]
    return None


def load_from_notion(token: str, database_id: str) -> list[Book]:
    """Fetch every page of the database's (first) data source."""
    from notion_client import Client  # imported here so CSV mode works without it

    client = Client(auth=token)
    database = client.databases.retrieve(database_id=database_id)
    data_sources = database.get("data_sources") or []
    if not data_sources:
        raise RuntimeError("This Notion database has no data source the integration can read.")
    source_id = data_sources[0]["id"]

    schema = client.data_sources.retrieve(data_source_id=source_id)["properties"]
    names = _field_names()
    for field, column in names.items():
        if column not in schema:
            log.warning("Notion column %r (for %s) not found — it will show as empty", column, field)
    percent_columns = {
        name for name, p in schema.items()
        if p.get("type") == "number" and p["number"].get("format") == "percent"
    }

    books, cursor = [], None
    while True:
        kwargs = {"page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.data_sources.query(data_source_id=source_id, **kwargs)
        for page in resp["results"]:
            props = page.get("properties", {})
            raw = {
                field: _property_value(props[column], percent=column in percent_columns)
                for field, column in names.items()
                if column in props
            }
            book = make_book(page["id"], raw)
            if book:
                books.append(book)
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    return books


# ---------------------------------------------------------------------------
# CSV export (for local previews and tests)
# ---------------------------------------------------------------------------

def load_from_csv(path: str) -> list[Book]:
    """Read a Notion "Export → CSV" file. Ratings like "60%" are understood."""
    names = _field_names()
    books = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = {field: row.get(column) for field, column in names.items()}
            # CSV rows have no Notion id: derive a stable one from the content.
            basis = "|".join(_clean_text(raw.get(k)) for k in ("title", "author", "year"))
            page_id = "csv-" + hashlib.sha1(basis.encode()).hexdigest()[:12]
            book = make_book(page_id, raw)
            if book:
                books.append(book)
    return books
