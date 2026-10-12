"""Every statistic and every sort order on the site is computed here.

The browser never recalculates anything: it only shows/hides what this module
prepared and re-orders rows by the rank numbers produced here.
"""

import unicodedata
from datetime import date

from pypinyin import Style, pinyin

import config
from src.book import Book

# ---------------------------------------------------------------------------
# Title sort key: English A–Z first, then Chinese in ㄅㄆㄇㄈ (Zhuyin) order
# ---------------------------------------------------------------------------

# Zhuyin tone marks -> tone number. First tone has no mark.
_TONES = {"ˊ": 2, "ˇ": 3, "ˋ": 4, "˙": 5}


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def _zhuyin_key(ch: str) -> tuple:
    """Turn one Chinese character into a sortable tuple.

    The Unicode code points of ㄅ…ㄩ (U+3105–U+3129) are already in
    ㄅㄆㄇㄈ order, so comparing the symbols' code points sorts correctly.
    """
    reading = pinyin(ch, style=Style.BOPOMOFO)[0][0]
    tone = 1
    symbols = []
    for s in reading:
        if s in _TONES:
            tone = _TONES[s]
        else:
            symbols.append(ord(s))
    # The character itself is the last tie-breaker (same sound, same tone).
    return (tuple(symbols), tone, ord(ch))


def title_key(title: str) -> tuple:
    """Sort key for a title.

    Group 0 = Latin letters and digits (accents removed, case ignored),
    group 1 = Chinese characters (Zhuyin order), group 2 = anything else
    (Japanese kana, Korean, ...). Spaces and punctuation are ignored.
    Comparing group numbers first puts English titles before Chinese ones.
    """
    # NFKC turns full-width "Ｘ" into "X"; NFD then splits "é" into "e" + accent.
    text = unicodedata.normalize("NFKC", title).lower()
    key = []
    for ch in text:
        if _is_cjk(ch):
            key.append((1, _zhuyin_key(ch)))
            continue
        base = unicodedata.normalize("NFD", ch)[0]
        if base.isascii() and base.isalnum():
            key.append((0, (ord(base),)))
        elif ch.isalnum():
            key.append((2, (ord(ch),)))
        # spaces / punctuation: skipped
    return tuple(key)


# ---------------------------------------------------------------------------
# Ranking (shared by Top 3 and the "Rating" sort)
# ---------------------------------------------------------------------------

def rank_key(book: Book) -> tuple:
    """Rating high→low, then finished date early→late, then title A–Z.

    Books without a date sort after books with one (when ratings tie).
    Unrated books sort after all rated books.
    """
    rating = book.rating if book.rating is not None else -1
    date_part = (0, book.finished_date) if book.finished_date else (1, date.min)
    return (-rating, date_part, title_key(book.title))


def counts_in_stats(book: Book) -> bool:
    """Fast-food books appear in the list but never in statistics."""
    return book.genre != config.FAST_FOOD


def top_n(books: list[Book], n: int) -> list[Book]:
    """The n best rated books (Fast-food and unrated books excluded)."""
    rated = [b for b in books if counts_in_stats(b) and b.rating is not None]
    return sorted(rated, key=rank_key)[:n]


def top3(books: list[Book]) -> list[Book]:
    return top_n(books, 3)


def is_highly_rated(book: Book) -> bool:
    """For the list's "80%+" filter. Like the other list filters, Fast-food counts."""
    return book.rating is not None and book.rating >= config.HIGH_RATING


def average_rating(books: list[Book]) -> int | None:
    ratings = [b.rating for b in books if counts_in_stats(b) and b.rating is not None]
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings))


def genre_ratio(books: list[Book]) -> list[dict]:
    """Share of each stat genre. Percentages are whole numbers that add up to 100.

    Uses the "largest remainder" method so 33.3 + 33.3 + 33.3 becomes 34/33/33
    instead of 33/33/33 (= 99).
    """
    counted = [b for b in books if counts_in_stats(b)]
    total = len(counted)
    rows = []
    for g in config.STAT_GENRES:
        n = sum(1 for b in counted if b.genre == g)
        rows.append({"genre": g, "count": n, "exact": (n * 100 / total) if total else 0})

    if total:
        floors = [int(r["exact"]) for r in rows]
        leftover = 100 - sum(floors)
        by_remainder = sorted(range(len(rows)), key=lambda i: rows[i]["exact"] - floors[i], reverse=True)
        for i in by_remainder[:leftover]:
            floors[i] += 1
    else:
        floors = [0] * len(rows)

    # Pie slices: each slice starts where the previous one ended (in percent).
    start = 0
    for r, pct in zip(rows, floors):
        r["pct"] = pct
        r["start"] = start
        r["end"] = start + pct
        start += pct
        del r["exact"]
    return rows


# ---------------------------------------------------------------------------
# Everything the page needs
# ---------------------------------------------------------------------------

def year_stats(books_in_year: list[Book]) -> dict:
    counted = [b for b in books_in_year if counts_in_stats(b)]
    return {
        "total": len(counted),
        "top3": top3(books_in_year),
        "avg_rating": average_rating(books_in_year),
        "genre_ratio": genre_ratio(books_in_year),
        "count_all": len(books_in_year),  # includes Fast-food (for "Showing N books")
    }


def default_year(years: list[int], today: date | None = None) -> int | None:
    """This year if it has books, otherwise the latest year that does."""
    if not years:
        return None
    current = (today or date.today()).year
    return current if current in years else max(years)


def list_ranks(books: list[Book]) -> dict[str, dict[str, int]]:
    """Position of every book in each list sort order.

    The browser sorts rows by these numbers, so the Zhuyin title order and the
    rating rules only exist here in Python.
    """
    by_title = sorted(books, key=lambda b: (title_key(b.title), b.id))
    by_rating = sorted(books, key=lambda b: (rank_key(b), b.id))
    ranks = {b.id: {} for b in books}
    for i, b in enumerate(by_title):
        ranks[b.id]["title"] = i
    for i, b in enumerate(by_rating):
        ranks[b.id]["rating"] = i
    if config.DATE_PROPERTY:
        # Newest first; books without a date go last (then title order).
        by_date = sorted(
            books,
            key=lambda b: (
                b.finished_date is None,
                -(b.finished_date.toordinal()) if b.finished_date else 0,
                title_key(b.title),
            ),
        )
        for i, b in enumerate(by_date):
            ranks[b.id]["date"] = i
    return ranks


def build_stats(books: list[Book], today: date | None = None) -> dict:
    years = sorted({b.year for b in books}, reverse=True)
    by_year = {y: year_stats([b for b in books if b.year == y]) for y in years}
    # "All years" uses the same numbers over every book, plus a Top 10.
    all_time = year_stats(books)
    all_time["top10"] = top_n(books, 10)
    return {
        "years": years,
        "default_year": default_year(years, today),
        "by_year": by_year,
        "all_time": all_time,
        "ranks": list_ranks(books),
    }
