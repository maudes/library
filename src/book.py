"""The Book record shared by every module."""

from dataclasses import dataclass
from datetime import date


@dataclass
class Book:
    id: str                      # Notion page id (or a stable hash for CSV rows)
    title: str
    author: str
    genre: str                   # site label, e.g. "Tool" (already mapped via config.GENRE_MAP)
    year: int                    # year finished
    second_title: str = ""
    rating: int | None = None    # 0–100, None = not rated
    published_year: int | None = None
    summary: str = ""
    finished_date: date | None = None
    isbn: str = ""               # from Notion, or filled in by enrich.py
    cover_url: str = ""          # from Notion (remote URL to download)
    cover: str = ""              # local path under static/, e.g. "covers/abc.jpg"
