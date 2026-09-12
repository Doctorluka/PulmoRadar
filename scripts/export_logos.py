#!/usr/bin/env python3
"""Rasterize logo SVGs via macOS qlmanage, then square-pad with Pillow."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "assets" / "logos"

SOURCES = {
    "chronic-lung.svg": [("chronic-lung-512.png", 512)],
    "pah.svg": [("pah-512.png", 512)],
    "chronic-lung-icon.svg": [
        ("chronic-lung-icon-54.png", 54),
        ("chronic-lung-icon-108.png", 108),
        ("chronic-lung-icon-216.png", 216),
    ],
    "pah-icon.svg": [
        ("pah-icon-54.png", 54),
        ("pah-icon-108.png", 108),
        ("pah-icon-216.png", 216),
    ],
}


def _trim(im: Image.Image, threshold: int = 245) -> Image.Image:
    gray = im.convert("L")
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return im
    pad = 8
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(im.width, right + pad)
    bottom = min(im.height, bottom + pad)
    return im.crop((left, top, right, bottom))


def _white_to_transparent(im: Image.Image, threshold: int = 248) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                px[x, y] = (255, 255, 255, 0)
    return im


def _square(im: Image.Image, size: int) -> Image.Image:
    im = _white_to_transparent(im)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def _rasterize(svg: Path, dest: Path) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        subprocess.run(
            ["qlmanage", "-t", "-s", "1024", "-o", str(tmp_path), str(svg)],
            check=True,
            capture_output=True,
        )
        produced = next(tmp_path.glob("*.png"))
        im = Image.open(produced).convert("RGBA")
        # Flatten onto white (qlmanage may add a faint shadow)
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return _trim(bg.convert("RGB")).convert("RGBA")


def main() -> None:
    for src_name, outputs in SOURCES.items():
        src = LOGO_DIR / src_name
        raw = _rasterize(src, LOGO_DIR)
        for dest_name, size in outputs:
            dest = LOGO_DIR / dest_name
            _square(raw, size).save(dest, "PNG", optimize=True)
            print(f"{dest.relative_to(ROOT)}  {size}px")


if __name__ == "__main__":
    main()
