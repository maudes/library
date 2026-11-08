"""Turn books + statistics into the static site in site/."""

import hashlib
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from src.book import Book
from src.doodles import THUMB_WIDTH, load_doodles, write_thumbnails
from src.posts import Post
from src.stats import is_highly_rated

ROOT = Path(__file__).resolve().parent.parent


def pct(rating: int | None) -> str:
    """92 -> "92%", None -> "—"."""
    return "—" if rating is None else f"{rating}%"


def dash(value) -> str:
    """Empty values show as an em dash."""
    return "—" if value in (None, "") else str(value)


def asset_version(name: str) -> str:
    """Short fingerprint of a static file, e.g. "a1b2c3d4".

    Used as style.css?v=... so browsers load the new file after each change
    instead of an old cached copy.
    """
    return hashlib.sha1((ROOT / "static" / name).read_bytes()).hexdigest()[:8]


def cover_version(path: str) -> str:
    """Fingerprint of a cover file, so a replaced cover isn't shown from the browser's cache."""
    return hashlib.sha1((ROOT / "static" / path).read_bytes()).hexdigest()[:8]


def search_text(book: Book) -> str:
    """Lower-case text the search box matches against (title, second title, author, ISBN)."""
    return " ".join([book.title, book.second_title, book.author, book.isbn]).lower()


def render(books: list[Book], stats: dict, out_dir: Path, today: date | None = None,
           posts: list[Post] | None = None, taste: dict | None = None) -> None:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["pct"] = pct
    env.filters["dash"] = dash
    env.filters["search_text"] = search_text
    env.filters["cover_version"] = cover_version

    sort_options = [("title", "Title A–Z"), ("rating", "Rating")]
    if config.DATE_PROPERTY:
        sort_options.append(("date", "Reading order: first → last"))
        sort_options.append(("latest", "Reading order: latest first"))

    # Every choice in the year switcher: "All years" first, then each year.
    # `key` matches the <option value> and the data-year attributes in the HTML.
    periods = [{"key": "all", "label": "All years", "in_label": "across all years",
                "stats": stats["all_time"], "is_all": True}]
    for y in stats["years"]:
        periods.append({"key": str(y), "label": str(y), "in_label": f"in {y}",
                        "stats": stats["by_year"][y], "is_all": False})

    # Variables every page (library and blog) needs.
    common = dict(
        palettes=config.PALETTES,
        ga_id=config.GA_MEASUREMENT_ID,
        site_hostname=config.SITE_HOSTNAME,
        css_version=asset_version("style.css"),
        js_version=asset_version("app.js"),
        built_on=(today or date.today()).isoformat(),
    )

    html = env.get_template("index.html").render(
        **common,
        books=books,
        stats=stats,
        periods=periods,
        default_period=str(stats["default_year"]),
        high_rating=config.HIGH_RATING,
        is_high=is_highly_rated,
        genres=config.ALL_GENRES,
        stat_genres=config.STAT_GENRES,
        fast_food=config.FAST_FOOD,
        sort_options=sort_options,
    )

    # Fresh output folder every build.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "static", out_dir / "static")
    render_blog(env, posts or [], out_dir, common)
    render_doodles(env, out_dir, common)
    if taste:
        render_taste(env, out_dir, common, taste)
    # Tell GitHub Pages not to run Jekyll on the output.
    (out_dir / ".nojekyll").write_text("")


def render_blog(env: Environment, posts: list[Post], out_dir: Path, common: dict) -> None:
    """blog/index.html (the list) and blog/<slug>/index.html for each post."""
    blog_dir = out_dir / "blog"
    blog_dir.mkdir()
    (blog_dir / "index.html").write_text(
        env.get_template("blog_index.html").render(**common, root="../", posts=posts),
        encoding="utf-8")
    for post in posts:
        (blog_dir / post.slug).mkdir()
        (blog_dir / post.slug / "index.html").write_text(
            env.get_template("blog_post.html").render(**common, root="../../", post=post),
            encoding="utf-8")


def render_doodles(env: Environment, out_dir: Path, common: dict) -> None:
    """doodles/index.html: the pictures in static/doodles/<series>/."""
    (out_dir / "doodles").mkdir()
    series = load_doodles(ROOT / "static", config.DOODLE_SERIES)
    write_thumbnails(series, ROOT / "static", out_dir / "static")
    (out_dir / "doodles" / "index.html").write_text(
        env.get_template("doodles.html").render(
            **common, root="../", current_page="doodles", series=series, thumb_width=THUMB_WIDTH,
            doodles_js_version=asset_version("doodles.js")),
        encoding="utf-8")


def render_taste(env: Environment, out_dir: Path, common: dict, taste: dict) -> None:
    """taste/index.html: genre ratio, favourites, what to read next, to-read list."""
    (out_dir / "taste").mkdir()
    (out_dir / "taste" / "index.html").write_text(
        env.get_template("taste.html").render(
            **common, root="../", current_page="taste", taste=taste,
            taste_js_version=asset_version("taste.js")),
        encoding="utf-8")
