"""Turn books + statistics into the static site in site/."""

import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from src.book import Book

ROOT = Path(__file__).resolve().parent.parent


def pct(rating: int | None) -> str:
    """92 -> "92%", None -> "—"."""
    return "—" if rating is None else f"{rating}%"


def dash(value) -> str:
    """Empty values show as an em dash."""
    return "—" if value in (None, "") else str(value)


def search_text(book: Book) -> str:
    """Lower-case text the search box matches against (title, second title, author, ISBN)."""
    return " ".join([book.title, book.second_title, book.author, book.isbn]).lower()


def render(books: list[Book], stats: dict, out_dir: Path, today: date | None = None) -> None:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["pct"] = pct
    env.filters["dash"] = dash
    env.filters["search_text"] = search_text

    sort_options = [("title", "Title A–Z"), ("rating", "Rating")]
    if config.DATE_PROPERTY:
        sort_options.append(("date", "Date"))

    html = env.get_template("index.html").render(
        books=books,
        stats=stats,
        genres=config.ALL_GENRES,
        stat_genres=config.STAT_GENRES,
        fast_food=config.FAST_FOOD,
        sort_options=sort_options,
        built_on=(today or date.today()).isoformat(),
    )

    # Fresh output folder every build.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "static", out_dir / "static")
    # Tell GitHub Pages not to run Jekyll on the output.
    (out_dir / ".nojekyll").write_text("")
