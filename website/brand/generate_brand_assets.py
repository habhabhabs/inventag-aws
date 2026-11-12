#!/usr/bin/env python3
"""Regenerate InvenTag's web brand assets from the SVG sources in ./src.

Run from anywhere:
    python3 website/brand/generate_brand_assets.py

Requirements: `rsvg-convert` (librsvg: `brew install librsvg`,
`apt install librsvg2-bin`) and Pillow (`pip install pillow`).
No fonts are needed: all text in the SVG sources is already outlined.

It writes to website/static/img/:
  logo.svg, logo-dark.svg           mark for light / dark backgrounds
  logo-on-brand.svg                 white mark for the blue navbar and hero
  logo-wordmark*.svg, logo-mono*.svg lockups and one-colour marks
  favicon.svg                       small-size mark, follows the OS colour scheme
  favicon.ico                       16, 32 and 48 px
  favicon-32.png, logo-192.png, logo-512.png
  apple-touch-icon.png              180 px on an opaque white tile
  social-card.png                   1200x630 Open Graph / Twitter card
and website/brand/preview.png, a one-page sheet for eyeballing the result.

To change the shapes or the wordmark, edit build_logo_sources.py and run it
first (it needs fonttools + uharfbuzz and the Inter font).
"""
import io
import pathlib
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

BRAND = pathlib.Path(__file__).resolve().parent
SRC = BRAND / "src"
OUT = BRAND.parent / "static" / "img"

COPY_SVGS = [
    "logo.svg", "logo-dark.svg", "logo-on-brand.svg", "logo-small.svg", "logo-mono.svg",
    "logo-mono-black.svg", "logo-mono-white.svg", "logo-wordmark.svg",
    "logo-wordmark-dark.svg", "logo-wordmark-mono.svg", "favicon.svg",
]


def render(svg, width=None, height=None):
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert not found: install librsvg (see the docstring)")
    cmd = ["rsvg-convert", str(svg)]
    if width:
        cmd += ["-w", str(width)]
    if height:
        cmd += ["-h", str(height)]
    png = subprocess.run(cmd, check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")


def save_png(img, path):
    img.save(path, optimize=True)
    print(f"  {path.relative_to(BRAND.parent.parent)}  {img.size[0]}x{img.size[1]}  "
          f"{path.stat().st_size // 1024} KB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("SVG copies:")
    for name in COPY_SVGS:
        shutil.copyfile(SRC / name, OUT / name)
        print(f"  website/static/img/{name}")

    print("PNG / ICO:")
    small, big = SRC / "logo-small.svg", SRC / "logo.svg"
    # <= 32 px uses the pixel-aligned small mark; larger sizes use the full mark
    save_png(render(small, 32, 32), OUT / "favicon-32.png")
    save_png(render(big, 192, 192), OUT / "logo-192.png")
    save_png(render(big, 512, 512), OUT / "logo-512.png")

    tile = Image.new("RGBA", (180, 180), "white")  # iOS paints transparency black
    mark = render(big, 140, 140)
    tile.alpha_composite(mark, (20, 20))
    save_png(tile.convert("RGB"), OUT / "apple-touch-icon.png")

    icons = [render(small, s, s) for s in (16, 32)] + [render(big, 48, 48)]
    icons[2].save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                  append_images=icons[:2])
    print("  website/static/img/favicon.ico  16/32/48")

    card = render(SRC / "social-card.svg", 1200, 630).convert("RGB")
    save_png(card, OUT / "social-card.png")

    preview()


def render_recoloured(svg_path, size):
    """Small mark in the dark-background blue (what favicon.svg shows in dark mode)."""
    tmp = BRAND / ".tmp-small-dark.svg"
    tmp.write_text(svg_path.read_text().replace("#1d4ed8", "#60a5fa"))
    try:
        return render(tmp, size, size)
    finally:
        tmp.unlink()


def preview():
    """One sheet: mark at 16/32/64/256, both lockups, on light and dark."""
    W, H = 1600, 760
    sheet = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(sheet)
    d.rectangle([0, H // 2, W, H], fill="#0f172a")
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 18)
    except OSError:
        font = ImageFont.load_default()

    def row(y, bg_dark):
        ink = "#cbd5e1" if bg_dark else "#334155"
        mark = SRC / ("logo-dark.svg" if bg_dark else "logo.svg")
        x = 60
        for size in (16, 32, 64, 256):
            src = SRC / "logo-small.svg" if size <= 32 else mark
            if bg_dark and size <= 32:
                img = render_recoloured(SRC / "logo-small.svg", size)
            else:
                img = render(src, size, size)
            top = y + 40 + (256 - size) // 2
            sheet.paste(img, (x, top), img)
            label = f"{size}px" + (" (small variant)" if size <= 32 else "")
            d.text((x, y + 310), label, fill=ink, font=font)
            x += max(size, 150) + 60
        lock = render(SRC / ("logo-wordmark-dark.svg" if bg_dark else "logo-wordmark.svg"),
                      height=96)
        sheet.paste(lock, (x, y + 60), lock)
        d.text((x, y + 170), "wordmark lockup", fill=ink, font=font)
        mono = render(SRC / ("logo-mono-white.svg" if bg_dark else "logo-mono-black.svg"), 96, 96)
        sheet.paste(mono, (x, y + 200), mono)
        d.text((x + 110, y + 240), "one-colour mark", fill=ink, font=font)
        d.text((60, y + 10), "on dark" if bg_dark else "on light", fill=ink, font=font)
        # 16px favicon pixels, enlarged 8x without smoothing
        fav = render(SRC / "logo-small.svg", 16, 16)
        if bg_dark:
            fav = render_recoloured(SRC / "logo-small.svg", 16)
        zoom = fav.resize((128, 128), Image.NEAREST)
        sheet.paste(zoom, (1420, y + 60), zoom)
        d.text((1420, y + 200), "16px, 8x zoom", fill=ink, font=font)

    row(0, False)
    row(H // 2, True)
    save_png(sheet, BRAND / "preview.png")


if __name__ == "__main__":
    main()
