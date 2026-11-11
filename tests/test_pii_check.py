import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pii_check


def labels(text):
    return [p.split(": ")[1] for p in pii_check.scan_text("x", text)]


def test_flags_email_phone_and_token():
    assert labels("write me at someone" + "@" + "gmail.com") == ["email"]
    assert labels("call 09" + "12-345-678") == ["Taiwan mobile"]
    assert labels("NOTION_TOKEN=ntn_" + "a" * 30) == ["Notion token"]


def test_allows_bot_email_and_isbns():
    assert labels("41898282+github-actions[bot]@users.noreply.github.com") == []
    assert labels("isbn 9780140449136 and 0140449132") == []
