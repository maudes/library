import config
from src.book import Book
from src.taste import ShelfBook, genre_summary, load_genres, recommend


def book(title, genre_label="Police procedural", rating=None, site_genre="Fiction", **kw):
    b = Book(id=title, title=title, author="A", genre=site_genre, year=2026, rating=rating, **kw)
    return b, genre_label


def make(specs):
    pairs = [book(*s) if isinstance(s, tuple) else book(s) for s in specs]
    return [b for b, _ in pairs], {b.id: g for b, g in pairs}


def test_ratio_adds_up_to_100_and_groups_the_rest():
    specs = [("a%d" % i, g) for i, g in enumerate(["Police procedural"] * 4 + ["Psychological thriller"] * 3 + ["Classic mystery"] * 2 +
                                                  ["Literary fiction", "Society & politics", "History & anthropology", "Science & tools"])]
    books, genre_of = make(specs)
    s = genre_summary(books, genre_of)
    assert [r["genre"] for r in s["chart"]][:2] == ["Police procedural", "Psychological thriller"]
    assert len(s["chart"]) == config.TASTE_TOP_GENRES + 1
    assert s["chart"][-1]["genre"] == "Other"
    assert sum(r["pct"] for r in s["chart"]) == 100
    assert s["chart"][-1]["end"] == 100


def test_fast_food_is_left_out():
    books, genre_of = make([("x", "Police procedural", None, "Fast-food"), ("y", "Police procedural")])
    assert genre_summary(books, genre_of)["total"] == 1


def test_best_genre_needs_enough_rated_books():
    specs = [("a%d" % i, "Police procedural", 70) for i in range(3)] + [("b", "Literary fiction", 99)]
    books, genre_of = make(specs)
    assert genre_summary(books, genre_of)["best_genre"] == "Police procedural"


def test_load_genres_matches_titles_ignoring_case(tmp_path):
    f = tmp_path / "genres.yml"
    f.write_text("Police procedural:\n  - the silent girl\n  - Missing Book\n", encoding="utf-8")
    books = [Book(id="1", title="The Silent Girl", author="A", genre="Fiction", year=2026)]
    assert load_genres(f, books) == {"1": "Police procedural"}


def shelf(title, genre, sources=()):
    return ShelfBook(book=Book(id=title, title=title, author="A", genre="", year=0), genre=genre, sources=list(sources))


def test_recommend_skips_read_and_listed_books_and_marks_one_per_genre():
    books, genre_of = make([("Read", "Police procedural", 80), ("Other", "Police procedural", 80), ("Lit", "Literary fiction", 80)])
    summary = genre_summary(books, genre_of)
    pool = [shelf("Read", "Police procedural"), shelf("New crime", "Police procedural", ["x"]), shelf("Second crime", "Police procedural", ["x"]),
            shelf("Listed", "Literary fiction"), shelf("New lit", "Literary fiction")]
    picks = recommend(pool, summary, books, tbr=[shelf("Listed", "")], n=5)
    assert [p.book.title for p in picks] == ["New crime", "Second crime", "New lit"]
    assert [p.book.title for p in picks if p.shown] == ["New crime", "New lit"]
    assert "Police procedural" in picks[0].reason


# --- Books with no genre yet: suggestions -------------------------------------

import json
import logging

from src.taste import genre_gaps, suggest_genre, write_genre_gaps


def lib_book(id, title="T", author="Someone", notion="Fiction", summary="", second=""):
    return Book(id=id, title=title, second_title=second, author=author, genre=notion, year=2026, summary=summary)


def test_suggest_same_author_wins_and_ties_go_to_the_first_listed_genre():
    new = lib_book("new", author="Tess Gerritsen")
    old = [lib_book("a", "Vanish", "Tess Gerritsen"), lib_book("b", "Bones", "Tess Gerritsen"),
           lib_book("c", "Silent Girl", "Tess Gerritsen"), lib_book("d", "Other", "Someone Else")]
    genre_of = {"a": "Police procedural", "b": "Police procedural", "c": "Psychological thriller", "d": "Gender studies"}
    assert suggest_genre(new, old + [new], genre_of) == ("Police procedural", "same author as 'Vanish'")
    tie = {"a": "Psychological thriller", "b": "Police procedural", "c": "Classic mystery"}
    guess = suggest_genre(new, old[:3] + [new], tie)
    assert guess[0] == "Police procedural"      # listed before the other two in TASTE_GENRES


def test_suggest_matches_authors_in_a_multi_author_field():
    new = lib_book("new", author="Peter Morville")
    other = lib_book("a", "Information Architecture", "Louis Rosenfeld/ Peter Morville/ Jorge Arango")
    assert suggest_genre(new, [new, other], {"a": "Science & tools"})[0] == "Science & tools"


def test_suggest_from_keywords_in_title_or_summary():
    new = lib_book("new", author="Nobody Known", summary="法醫與警探追查連環殺手")
    assert suggest_genre(new, [new], {}) == ("Police procedural", "mentions '警探'")
    assert suggest_genre(lib_book("n2", second="A Feminist Manifesto"), [], {})[0] == "Gender studies"


def test_suggest_from_notion_genre_then_most_common_genre():
    tool = lib_book("t", notion="Tool")
    assert suggest_genre(tool, [tool], {}) == ("Science & tools", "marked Tool in Notion")

    new = lib_book("new", author="Unknown Author")
    others = [lib_book(str(i), author=f"Author {i}") for i in range(3)]
    genre_of = {"0": "Classic mystery", "1": "Classic mystery", "2": "Police procedural"}
    genre, why = suggest_genre(new, others + [new], genre_of)
    assert genre == "Classic mystery" and "low confidence" in why


def test_no_suggestion_when_there_is_nothing_to_go_on():
    only = lib_book("x", author="Lone Author")
    assert suggest_genre(only, [only], {}) is None


def test_genre_gaps_skip_tagged_and_fast_food_books():
    tagged = lib_book("a", "Tagged", "Author A")
    snack = lib_book("b", "Snack", "Author B", notion="Fast-food")
    gap = lib_book("c", "Needs A Genre", "Author C", summary="推理")
    gaps = genre_gaps([tagged, snack, gap], {"a": "Police procedural"})
    assert [g["title"] for g in gaps] == ["Needs A Genre"]
    assert gaps[0]["suggested"] == "Classic mystery"


def test_load_genres_warning_names_a_suggestion(tmp_path, caplog):
    f = tmp_path / "genres.yml"
    f.write_text("Police procedural:\n  - Known Book\n", encoding="utf-8")
    books = [lib_book("1", "Known Book", "Same Author"), lib_book("2", "New Book", "Same Author")]
    with caplog.at_level(logging.WARNING):
        load_genres(f, books)
    assert "'New Book' has no genre yet" in caplog.text
    assert "Suggested: Police procedural (same author as 'Known Book')" in caplog.text


def test_write_genre_gaps_is_sorted_and_keeps_chinese(tmp_path):
    path = tmp_path / "cache" / "genre_gaps.json"
    write_genre_gaps(path, [{"title": "Zeta", "author": "a", "suggested": None, "reason": ""},
                            {"title": "alpha 書", "author": "b", "suggested": "Classic mystery", "reason": "x"}])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [g["title"] for g in data] == ["alpha 書", "Zeta"]
    assert "alpha 書" in path.read_text(encoding="utf-8")        # not \u-escaped
    write_genre_gaps(path, [])
    assert json.loads(path.read_text(encoding="utf-8")) == []
