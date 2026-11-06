import struct

from src.doodles import Doodle, balance, caption_for, image_size, load_doodles


def test_caption_for_day_files():
    assert caption_for("day-08") == "Day 8"
    assert caption_for("Day_9-2") == "Day 9"
    assert caption_for("awkward-headshot") == "awkward headshot"


def test_load_doodles_orders_naturally_and_skips_empty(tmp_path):
    d = tmp_path / "doodles" / "a"
    d.mkdir(parents=True)
    for name in ["day-10.jpg", "day-9-2.png", "day-9-1.png", "notes.txt"]:
        (d / name).write_bytes(b"")
    (tmp_path / "doodles" / "b").mkdir()
    series = load_doodles(tmp_path, [("a", "A", "", 3), ("b", "B", "", 4)])
    assert [s.folder for s in series] == ["a"]
    assert series[0].per_row == 3
    assert [x.src for x in series[0].doodles] == [
        "doodles/a/day-9-1.png", "doodles/a/day-9-2.png", "doodles/a/day-10.jpg"]


def test_balance_deals_each_picture_to_the_shortest_column():
    tall, short = Doodle("t", "", 2.0), Doodle("s", "", 0.5)
    cols = balance([tall, short, short, short], 2)
    assert [[d.src for d in c] for c in cols] == [["t"], ["s", "s", "s"]]


def test_image_size_reads_png_and_jpeg(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 30, 20) + b"\0" * 5)
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"\xff\xd8\xff\xc0\x00\x11\x08" + struct.pack(">HH", 20, 30) + b"\0" * 10)
    assert image_size(png) == (30, 20)
    assert image_size(jpg) == (30, 20)
