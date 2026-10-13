from datetime import date, datetime

from src.book import Book
from src.stats import (
    average_rating,
    build_stats,
    default_year,
    genre_ratio,
    list_ranks,
    title_key,
    top3,
)


def book(title, rating=None, genre="Fiction", year=2026, finished=None, **kw):
    return Book(id=title, title=title, author="A", genre=genre, year=year,
                rating=rating, read_at=finished, **kw)


def titles(books):
    return [b.title for b in books]


# --- Top 3 / ranking ---------------------------------------------------------

def test_four_tied_ratings_keep_earliest_three():
    books = [
        book("Delta", 90, finished=datetime(2026, 5, 1)),
        book("Alpha", 90, finished=datetime(2026, 3, 1)),
        book("Charlie", 90, finished=datetime(2026, 1, 1)),
        book("Bravo", 90, finished=datetime(2026, 2, 1)),
    ]
    assert titles(top3(books)) == ["Charlie", "Bravo", "Alpha"]


def test_higher_rating_beats_earlier_date():
    books = [book("Early", 80, finished=datetime(2026, 1, 1)),
             book("Late", 95, finished=datetime(2026, 12, 1))]
    assert titles(top3(books)) == ["Late", "Early"]


def test_missing_date_ranks_after_dated_then_by_title():
    books = [
        book("Zebra", 90),                                  # no date
        book("Apple", 90),                                  # no date
        book("Mango", 90, finished=datetime(2026, 6, 1)),
    ]
    assert titles(top3(books)) == ["Mango", "Apple", "Zebra"]


def test_all_dates_missing_falls_back_to_title():
    books = [book("Cherry", 70), book("apple", 70), book("Banana", 70), book("Date", 70)]
    assert titles(top3(books)) == ["apple", "Banana", "Cherry"]


def test_fast_food_never_in_top3_even_if_best():
    books = [
        book("Snack", 100, genre="Fast-food"),
        book("Novel", 60),
        book("Essay", 50, genre="Non-fiction"),
    ]
    assert titles(top3(books)) == ["Novel", "Essay"]


def test_unrated_books_never_in_top3():
    books = [book("Rated", 40), book("Unrated A"), book("Unrated B"), book("Unrated C")]
    assert titles(top3(books)) == ["Rated"]


def test_top3_with_fewer_than_three_books():
    assert titles(top3([book("Only", 70)])) == ["Only"]
    assert top3([]) == []


# --- Year statistics ---------------------------------------------------------

def test_fast_food_excluded_from_total_average_and_genre_ratio():
    books = [
        book("F1", 80), book("N1", 60, genre="Non-fiction"),
        book("Snack", 10, genre="Fast-food"), book("Snack 2", genre="Fast-food"),
    ]
    stats = build_stats(books, today=date(2026, 10, 1))
    y = stats["by_year"][2026]
    assert y["total"] == 2
    assert y["count_all"] == 4                     # list still shows Fast-food
    assert y["avg_rating"] == 70                   # (80 + 60) / 2, Snack's 10 ignored
    assert {r["genre"]: r["count"] for r in y["genre_ratio"]} == {
        "Fiction": 1, "Non-fiction": 1, "Tool": 0,
    }


def test_average_ignores_unrated_and_rounds():
    assert average_rating([book("a", 80), book("b", 75), book("c")]) == 78  # 77.5 -> 78
    assert average_rating([book("a")]) is None


def test_genre_percentages_add_up_to_100():
    rows = genre_ratio([book("a"), book("b", genre="Non-fiction"), book("c", genre="Tool")])
    assert [r["pct"] for r in rows] == [34, 33, 33]
    assert rows[-1]["end"] == 100


def test_genre_ratio_with_no_books():
    assert [r["pct"] for r in genre_ratio([])] == [0, 0, 0]


def test_all_time_top3_spans_years():
    books = [book("Old", 95, year=2019), book("New", 90, year=2026), book("Mid", 99, year=2023),
             book("Low", 10, year=2024)]
    stats = build_stats(books, today=date(2026, 1, 1))
    assert titles(stats["all_time"]["top3"]) == ["Mid", "Old", "New"]


def test_all_years_stats_and_top10():
    books = [book(f"B{i:02}", rating=50 + i, year=2018 + i % 5) for i in range(12)]
    books += [book("Snack", 100, genre="Fast-food", year=2020), book("Unrated", year=2021)]
    stats = build_stats(books, today=date(2026, 1, 1))
    all_time = stats["all_time"]
    assert all_time["total"] == 13                 # 12 rated + Unrated; Snack excluded
    assert all_time["count_all"] == 14
    assert titles(all_time["top10"]) == [f"B{i:02}" for i in range(11, 1, -1)]
    assert titles(all_time["top3"]) == ["B11", "B10", "B09"]
    assert sum(r["count"] for r in all_time["genre_ratio"]) == 13


def test_highly_rated_threshold():
    from src.stats import is_highly_rated
    assert is_highly_rated(book("a", 80))
    assert not is_highly_rated(book("b", 79))
    assert not is_highly_rated(book("c"))
    assert is_highly_rated(book("d", 95, genre="Fast-food"))   # list filter includes Fast-food


def test_default_year():
    assert default_year([2026, 2025], date(2026, 3, 1)) == 2026
    assert default_year([2025, 2024], date(2026, 3, 1)) == 2025   # no 2026 books yet
    assert default_year([], date(2026, 3, 1)) is None


# --- Title order: English A–Z, then Chinese ㄅㄆㄇㄈ -----------------------------

def sort_titles(names):
    return sorted(names, key=title_key)


def test_english_before_chinese():
    assert sort_titles(["人類大歷史", "Sapiens", "apple"]) == ["apple", "Sapiens", "人類大歷史"]


def test_chinese_follows_zhuyin_order():
    # 八 ㄅㄚ, 怕 ㄆㄚ, 媽 ㄇㄚ, 發 ㄈㄚ, 大 ㄉㄚ
    assert sort_titles(["大", "發", "媽", "怕", "八"]) == ["八", "怕", "媽", "發", "大"]


def test_zhuyin_tone_order():
    # 媽 ㄇㄚ (1st) < 麻 ㄇㄚˊ (2nd) < 馬 ㄇㄚˇ (3rd) < 罵 ㄇㄚˋ (4th)
    assert sort_titles(["罵", "馬", "媽", "麻"]) == ["媽", "麻", "馬", "罵"]


def test_title_key_ignores_case_accents_spaces_and_fullwidth():
    assert title_key("Ｘ的悲劇")[0] == title_key("x")[0]
    assert sort_titles(["Émile", "Eve", "Adam"]) == ["Adam", "Émile", "Eve"]


# --- List sort ranks ----------------------------------------------------------

def test_list_ranks_put_unrated_last():
    books = [book("B"), book("A", 50), book("C", 90)]
    ranks = list_ranks(books)
    by_rating = sorted(books, key=lambda b: ranks[b.id]["rating"])
    assert titles(by_rating) == ["C", "A", "B"]
    by_title = sorted(books, key=lambda b: ranks[b.id]["title"])
    assert titles(by_title) == ["A", "B", "C"]


# --- Reading order (config.DATE_PROPERTY) -------------------------------------

def test_same_day_entries_keep_their_time_order():
    books = [book("Later", 90, finished=datetime(2025, 5, 14, 9, 30)),
             book("Earlier", 90, finished=datetime(2025, 5, 14, 9, 5))]
    assert titles(top3(books)) == ["Earlier", "Later"]


def test_reading_order_ranks(monkeypatch):
    import config
    monkeypatch.setattr(config, "DATE_PROPERTY", "Date")
    books = [book("Second", finished=datetime(2025, 6, 1)),
             book("First", finished=datetime(2025, 5, 1)),
             book("No date"),
             book("Third", finished=datetime(2025, 7, 1))]
    ranks = list_ranks(books)
    first_to_last = sorted(books, key=lambda b: ranks[b.id]["date"])
    latest_first = sorted(books, key=lambda b: ranks[b.id]["latest"])
    assert titles(first_to_last) == ["First", "Second", "Third", "No date"]
    assert titles(latest_first) == ["Third", "Second", "First", "No date"]
