"""Doodles: images in static/doodles/<folder>/ -> Series records."""

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_DAY = re.compile(r"^day[-_ ]?0*(\d+)", re.IGNORECASE)
THUMB_WIDTH = 640       # px; about twice the widest column, for sharp screens
CAPTION_HEIGHT = 0.08   # a caption line, as a fraction of the column width


@dataclass
class Doodle:
    src: str        # path under static/, e.g. "doodles/30-days-challenge/day-08.jpg"
    caption: str    # "Day 8" for day-<n> files, otherwise the file name (hyphens -> spaces)
    ratio: float = 1.0   # height / width
    thumb: str = ""      # small copy shown on the page, e.g. "doodles/<folder>/thumbs/day-08.webp"


@dataclass
class Series:
    folder: str
    title: str
    blurb: str
    per_row: int = 4     # columns on wide screens
    doodles: list[Doodle] = field(default_factory=list)
    columns: list[list[Doodle]] = field(default_factory=list)


def _natural_key(name: str) -> list:
    """day-9 sorts before day-10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def caption_for(stem: str) -> str:
    m = _DAY.match(stem)
    return f"Day {m.group(1)}" if m else re.sub(r"[-_]+", " ", stem)


def image_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of a PNG or JPEG, or None if it can't be read."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def balance(doodles: list[Doodle], n: int) -> list[list[Doodle]]:
    """Split pictures into n columns of about the same height.

    Starts by dealing each picture, in order, to the currently shortest column,
    then keeps moving or swapping single pictures between columns while that
    makes the shortest and tallest column closer in height. Within a column the
    pictures stay in their original order.
    """
    cost = [d.ratio + CAPTION_HEIGHT for d in doodles]
    heights = [0.0] * n
    where = []
    for i, c in enumerate(cost):
        col = heights.index(min(heights))
        where.append(col)
        heights[col] += c

    def spread(h: list[float]) -> float:
        return max(h) - min(h)

    improved = True
    while improved:
        improved = False
        for i, c in enumerate(cost):
            for col in range(n):
                if col == where[i]:
                    continue
                trial = heights[:]
                trial[where[i]] -= c
                trial[col] += c
                if spread(trial) < spread(heights) - 1e-9:
                    heights, where[i], improved = trial, col, True
                    break
                for j, c2 in enumerate(cost):
                    if where[j] != col:
                        continue
                    trial = heights[:]
                    trial[where[i]] += c2 - c
                    trial[col] += c - c2
                    if spread(trial) < spread(heights) - 1e-9:
                        heights, improved = trial, True
                        where[i], where[j] = col, where[i]
                        break
                if improved:
                    break
            if improved:
                break

    columns: list[list[Doodle]] = [[] for _ in range(n)]
    for d, col in zip(doodles, where):
        columns[col].append(d)
    return columns


def load_doodles(static_dir: Path, series_config: list[tuple[str, str, str, int]]) -> list[Series]:
    """One Series per configured folder; folders with no images are left out."""
    result = []
    for folder, title, blurb, per_row in series_config:
        files = sorted((p for p in (static_dir / "doodles" / folder).glob("*")
                        if p.suffix.lower() in IMAGE_SUFFIXES),
                       key=lambda p: _natural_key(p.name))
        if not files:
            continue
        doodles = []
        for p in files:
            size = image_size(p)
            doodles.append(Doodle(f"doodles/{folder}/{p.name}", caption_for(p.stem),
                                  size[1] / size[0] if size else 1.0,
                                  f"doodles/{folder}/thumbs/{p.stem}.webp"))
        result.append(Series(folder, title, blurb, per_row, doodles, balance(doodles, per_row)))
    return result


def write_thumbnails(series: list[Series], static_dir: Path, out_static: Path) -> None:
    """Write each picture's small WebP copy (THUMB_WIDTH wide) into out_static."""
    for s in series:
        for d in s.doodles:
            dest = out_static / d.thumb
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(static_dir / d.src) as im:
                im = ImageOps.exif_transpose(im)   # phone photos: apply the rotate flag
                im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
                if im.width > THUMB_WIDTH:
                    im = im.resize((THUMB_WIDTH, round(im.height * THUMB_WIDTH / im.width)), Image.LANCZOS)
                im.save(dest, "WEBP", quality=80)
