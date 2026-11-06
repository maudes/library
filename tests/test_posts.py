from datetime import date

import pytest

from src.posts import load_posts, parse_post

POST = """---
title: 範例
date: 2025-03-01
book: 某本書
medium_url: https://medium.com/@x/y
---

第一段 **粗體**。

第二段。
"""


def test_parse_post_reads_header_and_renders_markdown():
    p = parse_post("demo", POST)
    assert (p.title, p.date, p.book) == ("範例", date(2025, 3, 1), "某本書")
    assert p.medium_url == "https://medium.com/@x/y"
    assert "<strong>粗體</strong>" in p.html
    assert p.summary == "第一段 粗體。"


def test_parse_post_requires_title_and_date():
    with pytest.raises(ValueError):
        parse_post("x", "---\ntitle: only title\n---\nbody")
    with pytest.raises(ValueError):
        parse_post("x", "no header")


def test_load_posts_sorts_newest_first_skips_drafts_and_broken(tmp_path):
    (tmp_path / "old.md").write_text("---\ntitle: Old\ndate: 2024-01-01\n---\nx")
    (tmp_path / "new.md").write_text("---\ntitle: New\ndate: 2025-01-01\n---\nx")
    (tmp_path / "wip.md").write_text("---\ntitle: WIP\ndate: 2026-01-01\ndraft: true\n---\nx")
    (tmp_path / "bad.md").write_text("no header")
    assert [p.slug for p in load_posts(tmp_path)] == ["new", "old"]
