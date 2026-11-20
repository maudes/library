import logging

import pytest

from src.notion_source import _property_value, capitalize_words, load_from_csv, make_book


def raw(**overrides):
    base = {"title": "Book", "author": "Someone", "genre": "Fiction", "year": 2026}
    base.update(overrides)
    return base


@pytest.mark.parametrize("before,after", [
    ("My sister, the serial killer", "My Sister, The Serial Killer"),
    ("The bay at midnight", "The Bay At Midnight"),
    ("1Q84（1）", "1Q84（1）"),
    ("McAvoy's book", "McAvoy's Book"),            # only first letters change
    ("Howl’s Moving Castle", "Howl’s Moving Castle"),
    ("Pipi Caca Popo──Histoire anecdotique de la scatologie",
     "Pipi Caca Popo──Histoire Anecdotique De La Scatologie"),
    ("Y 的悲劇", "Y 的悲劇"),                        # mostly Chinese: untouched
    ("거짓말이다", "거짓말이다"),
    ("", ""),
])
def test_capitalize_words(before, after):
    assert capitalize_words(before) == after


def test_genre_values_are_mapped_to_site_labels():
    assert make_book("1", raw(genre="Tool books")).genre == "Tool"
    assert make_book("1", raw(genre="Fast-food type")).genre == "Fast-food"


def test_multi_select_genre(caplog):
    assert make_book("1", raw(genre=["Tool books"])).genre == "Tool"
    assert make_book("1", raw(genre=[])) is None                 # no genre -> skipped
    with caplog.at_level(logging.WARNING):
        assert make_book("1", raw(genre=["Fiction", "Tool books"])).genre == "Fiction"
    assert "several genres" in caplog.text


def test_year_stored_as_text():
    assert make_book("1", raw(year=" 2024 ")).year == 2024


def test_missing_required_field_skips_row_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        assert make_book("1", raw(author="  ")) is None
        assert make_book("1", raw(year=None)) is None
    assert "missing author" in caplog.text


def test_unknown_genre_is_skipped(caplog):
    with caplog.at_level(logging.WARNING):
        assert make_book("1", raw(genre="Poetry")) is None
    assert "unknown genre" in caplog.text


def test_text_is_trimmed():
    b = make_book("1", raw(title="  設計心理學  ", second_title=" The  Design "))
    assert b.title == "設計心理學"
    assert b.second_title == "The Design"


def test_csv_percent_rating_and_blank_rating():
    assert make_book("1", raw(rating="60%")).rating == 60
    assert make_book("1", raw(rating="")).rating is None


def test_isbn_hyphens_removed():
    assert make_book("1", raw(isbn="978-0-14-312755-0")).isbn == "9780143127550"


def test_notion_percent_number_is_scaled():
    prop = {"type": "number", "number": 0.6}
    assert _property_value(prop, percent=True) == 60
    assert _property_value(prop, percent=False) == 0.6


def test_notion_text_select_and_title():
    assert _property_value({"type": "title", "title": [{"plain_text": "A"}, {"plain_text": "B"}]}) == "AB"
    assert _property_value({"type": "select", "select": {"name": "Fiction"}}) == "Fiction"
    assert _property_value({"type": "select", "select": None}) is None


def test_load_from_csv(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(
        "﻿Main Title,/2nd Title,朕已閱,Rating,作者 | Arthur,Year,Genre,Summary | 朕．批閱\n"
        "菊花與刀,The Chrysanthemum and the Sword,Done,80%,Ruth Benedict,2018,Non-fiction,日本\n"
        "No author,,Done,,,2018,Fiction,\n",
        encoding="utf-8",
    )
    books = load_from_csv(str(path))
    assert len(books) == 1
    assert books[0].rating == 80
    assert books[0].genre == "Non-fiction"


def test_notion_created_time_keeps_time_of_day():
    from datetime import datetime
    from src.notion_source import _to_datetime
    value = _property_value({"type": "created_time", "created_time": "2025-05-14T09:05:00.000Z"})
    assert _to_datetime(value) == datetime(2025, 5, 14, 9, 5)
    assert _to_datetime("2025-05-14") == datetime(2025, 5, 14)
    assert _to_datetime("") is None


# --- Reading status: only finished books are listed ---------------------------

@pytest.mark.parametrize("status", ["預計讀", "正在讀", "", "Abandoned"])
def test_unfinished_books_are_not_listed(status):
    assert make_book("1", raw(status=status)) is None


def test_done_books_are_listed():
    assert make_book("1", raw(status="Done")).title == "Book"


def test_missing_status_column_lists_everything():
    # status is absent (API: column not in the database) or None (CSV: no such column)
    assert make_book("1", raw()) is not None
    assert make_book("1", raw(status=None)) is not None


def test_unfinished_entry_without_genre_or_year_is_skipped_quietly(caplog):
    """A to-read entry often has only a title; that must not produce warnings."""
    with caplog.at_level(logging.INFO):
        assert make_book("1", {"title": "Into the Black Nowhere", "status": "預計讀"}) is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "Not listed yet" in caplog.text and "預計讀" in caplog.text


def test_status_rule_can_be_turned_off(monkeypatch):
    monkeypatch.setattr("config.STATUS_DONE", [])
    assert make_book("1", raw(status="預計讀")) is not None


def test_notion_status_value():
    assert _property_value({"type": "status", "status": {"name": "Done"}}) == "Done"
    assert _property_value({"type": "status", "status": None}) == ""


def test_csv_skips_unfinished_rows(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(
        "Main Title,/2nd Title,朕已閱,Rating,作者 | Arthur,Year,Genre,Summary | 朕．批閱\n"
        "Finished,,Done,80%,Someone,2025,Fiction,\n"
        "Reading now,,正在讀,,Someone,2026,Fiction,\n"
        "Want to read,,預計讀,,Someone,2026,Fiction,\n",
        encoding="utf-8",
    )
    assert [b.title for b in load_from_csv(str(path))] == ["Finished"]
