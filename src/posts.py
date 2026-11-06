"""Reading notes (blog posts): Markdown files in posts/ -> Post records.

Each file is posts/<slug>.md, starting with a small header between --- lines:

    ---
    title: 書名 — 我的心得
    date: 2025-03-01
    book: 書名                   (optional: the book it's about)
    medium_url: https://...      (optional: shows "Originally published on Medium")
    summary: One sentence for the list page.   (optional; defaults to the first paragraph)
    draft: true                  (optional: skipped when building)
    ---

    The post itself, in Markdown.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import markdown

log = logging.getLogger(__name__)

_HEADER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class Post:
    slug: str                    # file name without .md; becomes blog/<slug>/
    title: str
    date: date
    html: str                    # body rendered from Markdown
    book: str = ""
    medium_url: str = ""
    summary: str = ""


def parse_post(slug: str, text: str) -> Post:
    """Parse one file's text. Raises ValueError if the header or title/date is missing."""
    m = _HEADER.match(text.lstrip("﻿"))
    if not m:
        raise ValueError("missing --- header")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
    if not meta.get("title") or not meta.get("date"):
        raise ValueError("header needs title and date")
    body = m.group(2).strip()
    html = markdown.markdown(body, extensions=["extra", "sane_lists", "smarty"])
    summary = meta.get("summary") or _first_paragraph(body)
    return Post(slug=slug, title=meta["title"], date=date.fromisoformat(meta["date"]),
                html=html, book=meta.get("book", ""), medium_url=meta.get("medium_url", ""),
                summary=summary)


def _first_paragraph(body: str) -> str:
    """Plain text of the first paragraph (no Markdown marks), cut to ~140 chars."""
    for para in re.split(r"\n\s*\n", body):
        text = re.sub(r"[#>*_`\[\]]|\(https?://[^)]*\)", "", para).strip()
        if text:
            return text if len(text) <= 140 else text[:140].rstrip() + "…"
    return ""


def load_posts(folder: Path) -> list[Post]:
    """All published posts, newest first. A broken file is skipped with a warning."""
    posts = []
    for path in sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if re.search(r"^draft:\s*true\s*$", text.split("\n---", 1)[0], re.M | re.I):
                continue
            posts.append(parse_post(path.stem, text))
        except ValueError as err:
            log.warning("Skipping post %s: %s", path.name, err)
    return sorted(posts, key=lambda p: (p.date, p.slug), reverse=True)
