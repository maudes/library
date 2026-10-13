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


def test_mixed_script_author_names():
    assert enrich.authors_match("石黑一雄", ["石黑一雄(Kazuo Ishiguro)"])
    assert enrich.authors_match("Kazuo Ishiguro", ["石黑一雄(Kazuo Ishiguro)"])
    assert enrich.authors_match("韓江", ["韓江 (한강)"])
    assert not enrich.authors_match("石黑一雄", ["Kazuo Ishiguro"])     # needs learning or an alias


def test_author_alias_from_config(monkeypatch):
    monkeypatch.setattr(enrich.config, "AUTHOR_ALIASES", {"伍綺詩": ["Celeste Ng"]})
    assert enrich.authors_match(enrich._aliases("伍綺詩"), ["Celeste Ng"])


def test_descriptor_suffix_ignored():
    assert enrich.titles_match("Crying in H Mart, A Memoir", "Crying in H Mart")
    assert enrich.titles_match("Vanish", "Vanish A Novel")
    assert not enrich.titles_match("A Memoir of Grief", "Grief")


def test_author_name_learned_from_chinese_edition(monkeypatch):
    """The Chinese edition lists "石黑一雄(Kazuo Ishiguro)" without a cover; the
    English edition (author "Kazuo Ishiguro" only) then supplies the cover."""
    zh = {"title": "別讓我走（諾貝爾文學獎得主石黑一雄最受歡迎代表作）", "authors": ["石黑一雄(Kazuo Ishiguro)"],
          "isbn": "9786264600514", "cover": "", "source": "google"}
    en = {"title": "Never Let Me Go", "authors": ["Kazuo Ishiguro"], "isbn": "9781400044832",
          "cover": "https://example.com/en.jpg", "source": "google"}
    impostor = {"title": "Never Let Me Go", "authors": ["J.J. McAvoy"], "isbn": "9781641970549",
                "cover": "https://example.com/wrong.jpg", "source": "google"}
    monkeypatch.setattr(enrich, "search_google",
                        lambda t, a, k="": [zh] if t == "別讓我走" else [impostor, en])
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    m = enrich.find_match(book(title="別讓我走", second_title="Never Let Me Go", author="石黑一雄"))
    assert m["isbn"] == "9786264600514"
    assert m["cover"] == "https://example.com/en.jpg"


def test_titles_match_ignores_leading_article():
    assert enrich.titles_match("Black Book", "The Black Book")
    assert enrich.titles_match("The Silent Wife", "The Silent Wife")
    assert not enrich.titles_match("Black Book", "The Black Book Club")


def test_other_edition_cover_used_when_read_edition_has_none(monkeypatch):
    """Chinese edition found without a cover -> keep its ISBN, borrow the English cover."""
    chinese = {"title": "尋找消失的女孩", "authors": ["Lisa Gardner"], "isbn": "9789570530889",
               "cover": "", "source": "google"}
    english = {"title": "Find Her", "authors": ["Lisa Gardner"], "isbn": "9780698404229",
               "cover": "https://example.com/en.jpg", "source": "google"}
    monkeypatch.setattr(enrich, "search_google",
                        lambda t, a, k="": [chinese] if t == "尋找消失的女孩" else [english])
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    b = book(title="尋找消失的女孩", second_title="Find Her", author="Lisa Gardner")
    m = enrich.find_match(b)
    assert m["isbn"] == "9789570530889"
    assert m["cover"] == "https://example.com/en.jpg"
    assert m["cover_from_other_edition"] is True


def test_read_edition_cover_preferred(monkeypatch):
    chinese = {"title": "素食者", "authors": ["韓江"], "isbn": "9789864894529",
               "cover": "https://example.com/zh.jpg", "source": "google"}
    monkeypatch.setattr(enrich, "search_google", lambda t, a, k="": [chinese])
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    m = enrich.find_match(book(title="素食者", second_title="The Vegetarian", author="韓江"))
    assert m["cover"] == "https://example.com/zh.jpg" and "cover_from_other_edition" not in m


def test_old_entries_without_cover_are_retried_once(sandbox):
    calls, mp = sandbox
    b = book()
    enrich.save_cache({"p1": {"signature": enrich._signature(b), "checked": "2026-10-01",
                              "isbn": "9789570530889", "cover": "", "source": "google",
                              "status": "found"}})          # v1 entry, no cover
    mp.setattr(enrich, "find_match", fake_find(calls, {"isbn": "9789570530889", "cover": "x",
                                                       "source": "google"}))
    enrich.enrich([b], today=date(2026, 10, 2))
    enrich.enrich([book()], today=date(2026, 10, 3))
    assert calls["find"] == 1                               # retried once, then cached


def test_search_plans_try_main_title_first_then_english_second_title():
    assert enrich.search_plans(book()) == ["無聲告白", "Everything I Never Told You"]
    assert enrich.search_plans(book(title="Vanish", second_title="")) == ["Vanish"]
    assert enrich.search_plans(book(title="砂之器", second_title="砂の器")) == ["砂之器", "砂の器"]
    assert enrich.search_plans(book(title="落日", second_title="落日")) == ["落日"]   # same title: once


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


def test_kana_author_alias(monkeypatch):
    monkeypatch.setattr(enrich.config, "AUTHOR_ALIASES", {"湊佳苗": ["湊かなえ", "Kanae Minato"]})
    assert enrich.authors_match(enrich._aliases("湊佳苗"), ["湊かなえ"])
    assert not enrich.authors_match("湊佳苗", ["湊かなえ"])           # only one shared kanji without the alias


def test_title_only_query_retry_still_checks_author(monkeypatch):
    """Query without the author when the first query finds nothing; the
    author is still verified, so a same-title book by someone else is rejected."""
    queries = []
    def fake_google(t, a, k=""):
        queries.append((t, a))
        if a:
            return [{"title": "松本清張全集 第5巻", "authors": ["松本清張"], "isbn": "", "cover": "x", "source": "google"}]
        return [{"title": "砂の器", "authors": ["Someone Else"], "isbn": "", "cover": "bad", "source": "google"},
                {"title": "砂の器", "authors": ["松本清張"], "isbn": "9784101109169", "cover": "good", "source": "google"}]
    monkeypatch.setattr(enrich, "search_google", fake_google)
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    m = enrich.find_match(book(title="砂之器", second_title="砂の器", author="松本清張"))
    assert m["cover"] == "good"
    assert any(author == "" for _, author in queries)        # a title-only query was made


def test_result_may_match_the_other_title(monkeypatch):
    zh = {"title": "法醫與殺人魔", "authors": ["愛蓮娜・厄克特"], "isbn": "9786263", "cover": "zh", "source": "google"}
    monkeypatch.setattr(enrich, "search_google", lambda t, a, k="": [zh])
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    m = enrich.find_match(book(title="The Butcher And The Wren", second_title="法醫與殺人魔", author="愛蓮娜．厄克特"))
    assert m["cover"] == "zh"


def test_cover_override_from_config_wins(sandbox, monkeypatch):
    calls, mp = sandbox
    mp.setattr(enrich.config, "COVER_OVERRIDES", {"無聲告白": "https://example.com/hand-picked.jpg"})
    downloaded = []
    real_download = enrich.download_cover
    mp.setattr(enrich, "download_cover", lambda url, book_id: downloaded.append(url) or real_download(url, book_id))
    mp.setattr(enrich, "find_match", fake_find(calls, {"isbn": "9789865617400", "cover": "https://example.com/auto.jpg",
                                                       "source": "google"}))
    b = book()
    enrich.enrich([b], today=date(2026, 10, 14))
    assert downloaded[0] == "https://example.com/hand-picked.jpg"
    assert b.cover == "covers/p1.jpg"
    assert b.isbn == "9789865617400"                    # ISBN still looked up


def test_unknown_override_title_warns(sandbox, monkeypatch, caplog):
    calls, mp = sandbox
    mp.setattr(enrich.config, "COVER_OVERRIDES", {"不存在的書": "https://example.com/x.jpg"})
    mp.setattr(enrich, "find_match", fake_find(calls, None))
    with caplog.at_level("WARNING"):
        enrich.enrich([book()], today=date(2026, 10, 14))
    assert "不存在的書" in caplog.text


def test_alias_names_are_used_in_queries(monkeypatch):
    monkeypatch.setattr(enrich.config, "AUTHOR_ALIASES", {"湊佳苗": ["湊かなえ"]})
    queries = []
    def fake_google(t, a, k=""):
        queries.append(a)
        return [{"title": "落日", "authors": ["湊かなえ"], "isbn": "9784758414005",
                 "cover": "jp", "source": "google"}] if a == "湊かなえ" else []
    monkeypatch.setattr(enrich, "search_google", fake_google)
    monkeypatch.setattr(enrich, "search_open_library", lambda t, a: [])
    m = enrich.find_match(book(title="落日", second_title="落日", author="湊佳苗"))
    assert m["cover"] == "jp"
    assert queries[:2] == ["湊佳苗", "湊かなえ"]


def test_image_extension_from_bytes():
    assert enrich.image_extension(b"\xff\xd8\xff\xe0rest") == ".jpg"
    assert enrich.image_extension(b"\x89PNG\r\n\x1a\nrest") == ".png"
    assert enrich.image_extension(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == ".webp"
    assert enrich.image_extension(b"<html>not an image") == ""
