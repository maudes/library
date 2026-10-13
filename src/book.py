"""The Book record shared by every module."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Book:
    id: str                      # Notion page id (or a stable hash for CSV rows)
    title: str
    author: str
    genre: str                   # site label, e.g. "Tool" (already mapped via config.GENRE_MAP)
    year: int                    # year finished
    second_title: str = ""
    rating: int | None = None    # 0–100, None = not rated
    summary: str = ""
    read_at: datetime | None = None   # reading-order timestamp (config.DATE_PROPERTY)
    isbn: str = ""               # from Notion, or filled in by enrich.py
    cover_url: str = ""          # from Notion (remote URL to download)
    cover: str = ""              # local path under static/, e.g. "covers/abc.jpg"
