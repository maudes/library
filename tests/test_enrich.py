from datetime import date

import pytest

from src import enrich
from src.book import Book


def book(**kw):
    base = dict(id="p1", title="無聲告白", second_title="Everything I Never Told You",
                author="伍綺詩", genre="Fiction", year=2018)
    base.update(kw)
    return Book(**base)


# --- Text rules ---------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("The Silent Girl", True),
    ("Tørst", True),
    ("1Q84（1）", True),       # digits aren't letters; "Q" is the only letter
    ("AI 時代的工作", False),  # mostly Chinese
    ("菊花與刀", False),
])
def test_is_english(text, expected):
    assert enrich.is_english(text) is expected


def test_authors_match():
    assert enrich.authors_match("Ruth Benedict", ["Ruth Benedict"])
    assert enrich.authors_match("S. S. Van Dine", ["S.S. Van Dine"])
    assert enrich.authors_match("村上春樹", ["村上春樹", "賴明珠"])
    assert not enrich.authors_match("伍綺詩", ["Celeste Ng"])
    assert not enrich.authors_match("王小明", ["王大同"])   # one shared character isn't enough


def test_titles_match_ignores_subtitles():
    assert enrich.titles_match("Sapiens", "Sapiens: A Brief History of Humankind")
    assert enrich.titles_match("槍砲病菌與鋼鐵", "槍砲、病菌與鋼鐵：人類社會的命運")
    assert enrich.titles_match("Vanish", "Vanish (Jane Rizzoli, Book 5)")
    assert not enrich.titles_match("Vanish", "Body Double")
    assert not enrich.titles_match("Sapiens", "Summary of Sapiens: a Brief History of Humankind")


def test_search_plans_try_main_title_first_then_english_second_title():
    assert enrich.search_plans(book()) == ["無聲告白", "Everything I Never Told You"]
    assert enrich.search_plans(book(title="Vanish", second_title="")) == ["Vanish"]
    assert enrich.search_plans(book(second_title="鐵湖疑案")) == ["無聲告白"]   # non-English second title skipped


def test_title_only_match_is_rejected(monkeypatch):
    """Same title, different author (J.J. McAvoy vs 石黑一雄) must not match."""
    wrong = [{"title": "Never Let Me Go", "authors": ["J.J. McAvoy"], "isbn": "9781641970549",
              "cover": "x", "source": "google"}]
    monkeypatch.setattr(enrich, "search_google", lambda t, a, k="": wrong)
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: wrong)
    b = book(title="別讓我走", second_title="Never Let Me Go", author="石黑一雄")
    assert enrich.find_match(b) is None


# --- Cache behaviour ----------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the cache and covers at a temp folder and fake the network."""
    monkeypatch.setattr(enrich, "CACHE_FILE", tmp_path / "cache" / "books.json")
    monkeypatch.setattr(enrich, "COVERS_DIR", tmp_path / "covers")
    calls = {"find": 0}

    def fake_download(url, book_id):
        (tmp_path / "covers").mkdir(exist_ok=True)
        (tmp_path / "covers" / f"{book_id}.jpg").write_bytes(b"x")
        return f"covers/{book_id}.jpg"

    monkeypatch.setattr(enrich, "download_cover", fake_download)
    return calls, monkeypatch


def fake_find(calls, result):
    def _find(book, api_key=""):
        calls["find"] += 1
        if isinstance(result, Exception):
            raise result
        return result
    return _find


def test_found_result_is_cached_and_reused(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, {"isbn": "9780143127550", "cover": "http://x", "source": "google"}))
    b = book()
    enrich.enrich([b], today=date(2026, 1, 1))
    assert b.isbn == "9780143127550" and b.cover == "covers/p1.jpg"

    b2 = book()
    enrich.enrich([b2], today=date(2026, 1, 2))
    assert calls["find"] == 1                     # second build used the cache
    assert b2.isbn == "9780143127550"


def test_not_found_is_cached_then_retried_after_n_days(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, None))
    enrich.enrich([book()], today=date(2026, 1, 1))
    enrich.enrich([book()], today=date(2026, 1, 10))
    assert calls["find"] == 1
    enrich.enrich([book()], today=date(2026, 3, 1))   # 30+ days later
    assert calls["find"] == 2


def test_network_failure_is_not_cached_and_does_not_raise(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, enrich.LookupError_("down")))
    b = book()
    enrich.enrich([b], today=date(2026, 1, 1))        # must not raise
    assert b.isbn == "" and b.cover == ""
    enrich.enrich([book()], today=date(2026, 1, 2))
    assert calls["find"] == 2                          # retried next build


def test_notion_values_win_and_skip_lookup(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, {"isbn": "9999999999999", "cover": "x", "source": "google"}))
    b = book(isbn="9780000000001", cover_url="https://example.com/c.jpg")
    enrich.enrich([b], today=date(2026, 1, 1))
    assert calls["find"] == 0
    assert b.isbn == "9780000000001" and b.cover == "covers/p1.jpg"


def test_editing_title_in_notion_invalidates_cache(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, None))
    enrich.enrich([book(title="https://www.goodreads.com/x")], today=date(2026, 1, 1))
    enrich.enrich([book(title="One False Move")], today=date(2026, 1, 2))
    assert calls["find"] == 2


def test_deleted_books_are_pruned_unless_disabled(sandbox, tmp_path):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, {"isbn": "9780143127550", "cover": "x", "source": "google"}))
    enrich.enrich([book(id="keep"), book(id="gone")], today=date(2026, 1, 1))
    assert (tmp_path / "covers" / "gone.jpg").exists()

    enrich.enrich([book(id="keep")], today=date(2026, 1, 2), prune=False)   # e.g. a CSV build
    assert "gone" in enrich.load_cache()

    enrich.enrich([book(id="keep")], today=date(2026, 1, 3))
    assert "gone" not in enrich.load_cache()
    assert not (tmp_path / "covers" / "gone.jpg").exists()
    assert (tmp_path / "covers" / "keep.jpg").exists()


def test_offline_mode_never_looks_up(sandbox):
    calls, mp = sandbox
    mp.setattr(enrich, "find_match", fake_find(calls, None))
    enrich.enrich([book()], offline=True)
    assert calls["find"] == 0
