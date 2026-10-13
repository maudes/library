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
