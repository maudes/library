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
