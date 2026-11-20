import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_genres

GAP = {"title": "The Fury", "author": "Alex Michaelides", "suggested": "Classic mystery",
       "reason": "mentions '推理'"}


def setup(tmp_path, gaps, genres_yml="Police procedural:\n  - Some Other Book\n"):
    gaps_file, genres_file = tmp_path / "genre_gaps.json", tmp_path / "genres.yml"
    gaps_file.write_text(json.dumps(gaps, ensure_ascii=False), encoding="utf-8")
    genres_file.write_text(genres_yml, encoding="utf-8")
    return ["--gaps", str(gaps_file), "--genres", str(genres_file)]


def test_missing_genre_fails_and_prints_the_suggestion(tmp_path, capsys):
    assert check_genres.main(setup(tmp_path, [GAP])) == 1
    out = capsys.readouterr().out
    assert '"The Fury" (Alex Michaelides)' in out
    assert "suggested: Classic mystery" in out
    assert 'add under "Classic mystery:"' in out


def test_gap_already_added_to_genres_yml_passes_ignoring_case(tmp_path, capsys):
    args = setup(tmp_path, [GAP], "Classic mystery:\n  - the fury\n")
    assert check_genres.main(args) == 0
    assert "passed" in capsys.readouterr().out


def test_no_gaps_file_passes(tmp_path):
    assert check_genres.main(["--gaps", str(tmp_path / "missing.json"), "--genres", str(tmp_path / "g.yml")]) == 0


def test_warn_only_never_fails_but_annotates(tmp_path, capsys):
    assert check_genres.main(setup(tmp_path, [GAP]) + ["--warn-only"]) == 0
    assert '::warning title=Genre missing::"The Fury"' in capsys.readouterr().out


def test_book_with_no_suggestion_says_how_to_pick(tmp_path, capsys):
    gap = dict(GAP, suggested=None, reason="")
    assert check_genres.main(setup(tmp_path, [gap])) == 1
    assert "no suggestion" in capsys.readouterr().out
