#!/usr/bin/env python3
"""Regenerate InvenTag's web brand assets from the SVG sources in ./src.

Run from anywhere:
    python3 website/brand/generate_brand_assets.py      (or: cd website && npm run brand)

Requirements: `rsvg-convert` (librsvg: `brew install librsvg`,
`apt install librsvg2-bin`) and Pillow (`pip install pillow`).
No fonts are needed: all text in the SVG sources is already outlined.

Writes to website/static/:
  img/logo.svg, img/logo-dark.svg      mark for light / dark backgrounds
  img/logo-on-brand.svg                one-colour ink mark for a vermilion field
  img/logo-small*.svg                  pixel-aligned mark for 16-32 px
  img/logo-wordmark*.svg, img/logo-mono*.svg   lockups and one-colour marks
  img/favicon.svg                      small mark, follows the OS colour scheme
  img/favicon.ico                      16, 32 and 48 px (paper halo: readable on dark tab bars)
  img/favicon-32.png, img/logo-192.png, img/logo-512.png, img/logo-maskable-512.png
  img/apple-touch-icon.png             180 px on an opaque paper tile
  img/social-card.png                  1200x630 Open Graph / Twitter card
  site.webmanifest                     name, colours and icons
and website/brand/preview.png (the logo in context: navbar, browser tab,
sizes, lockups, app icons, social card, palette).

To change shapes, colours or text, edit build_logo_sources.py and run it first.
"""
import base64
import io
import json
import pathlib
import shutil
import subprocess
import sys

from PIL import Image, ImageFilter

BRAND = pathlib.Path(__file__).resolve().parent
SRC = BRAND / "src"
STATIC = BRAND.parent / "static"
OUT = STATIC / "img"
PAPER = "#F9F8F6"
DARK_BG = "#111110"
BASE_URL = "/inventag-aws/"

COPY_SVGS = [
    "logo.svg", "logo-dark.svg", "logo-on-brand.svg", "logo-small.svg", "logo-small-dark.svg",
    "logo-mono.svg", "logo-mono-black.svg", "logo-mono-white.svg", "logo-wordmark.svg",
    "logo-wordmark-dark.svg", "logo-wordmark-mono.svg", "favicon.svg",
]


def render(svg, width=None, height=None):
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert not found: install librsvg (see the docstring)")
    cmd = ["rsvg-convert"]
    if width:
        cmd += ["-w", str(width)]
    if height:
        cmd += ["-h", str(height)]
    if isinstance(svg, pathlib.Path):
        cmd.append(str(svg))
        data = None
    else:  # SVG markup as a string
        data = svg.encode()
    png = subprocess.run(cmd, input=data, check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")


def save_png(img, path):
    img.save(path, optimize=True)
    print(f"  {path.relative_to(BRAND.parent.parent)}  {img.size[0]}x{img.size[1]}  "
          f"{max(1, path.stat().st_size // 1024)} KB")


def with_halo(img, colour=PAPER, radius=1):
    """Mark plus a 1px paper outline, so the ink tag stays visible on dark tab bars."""
    alpha = img.getchannel("A").filter(ImageFilter.MaxFilter(radius * 2 + 1))
    halo = Image.new("RGBA", img.size, colour)
    halo.putalpha(alpha)
    halo.alpha_composite(img)
    return halo


def tile(size, mark_svg, mark_size, bg=PAPER):
    t = Image.new("RGBA", (size, size), bg)
    m = render(mark_svg, mark_size, mark_size)
    off = (size - mark_size) // 2
    t.alpha_composite(m, (off, off))
    return t


def data_uri(img):
    buf = io.BytesIO(); img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("SVG copies:")
    for name in COPY_SVGS:
        shutil.copyfile(SRC / name, OUT / name)
        print(f"  website/static/img/{name}")

    print("PNG / ICO:")
    small, big = SRC / "logo-small.svg", SRC / "logo.svg"
    save_png(with_halo(render(small, 32, 32)), OUT / "favicon-32.png")
    icons = [with_halo(render(small, s, s)) for s in (16, 32)] + [with_halo(render(big, 48, 48))]
    icons[2].save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=icons[:2])
    print("  website/static/img/favicon.ico  16/32/48")

    # app icons on an opaque paper tile (iOS paints transparency black)
    save_png(tile(180, big, 132).convert("RGB"), OUT / "apple-touch-icon.png")
    save_png(tile(192, big, 140), OUT / "logo-192.png")
    save_png(tile(512, big, 376), OUT / "logo-512.png")
    # maskable: keep the mark inside the central 80% safe zone
    save_png(tile(512, big, 300), OUT / "logo-maskable-512.png")

    card = render(SRC / "social-card.svg", 1200, 630).convert("RGB")
    save_png(card, OUT / "social-card.png")

    manifest = {
        "name": "InvenTag",
        "short_name": "InvenTag",
        "description": "Open-source Python CLI: AWS resource inventory, tag checks, Excel and Word reports.",
        "start_url": BASE_URL,
        "scope": BASE_URL,
        "display": "browser",
        "background_color": PAPER,
        "theme_color": PAPER,
        "icons": [
            {"src": f"{BASE_URL}img/logo-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"{BASE_URL}img/logo-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"{BASE_URL}img/logo-maskable-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
            {"src": f"{BASE_URL}img/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (STATIC / "site.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n")
    print("  website/static/site.webmanifest")

    preview()


def preview():
    """Render src/preview-sheet.svg with the real PNGs embedded."""
    sheet = (SRC / "preview-sheet.svg").read_text()
    fav_svg = (SRC / "favicon.svg").read_text()
    # what a browser shows for favicon.svg in light and dark mode
    dark_variant = fav_svg.replace(".t{fill:#141413}", ".t{fill:#F2F0EC}", 1)
    assert dark_variant != fav_svg, "favicon.svg colours changed: update preview()"
    tokens = {
        "favicon-16-light.png": render(SRC / "favicon.svg", 16, 16),
        "favicon-16-dark.png": render(dark_variant, 16, 16),
        "apple-touch-icon.png": Image.open(OUT / "apple-touch-icon.png"),
        "logo-192.png": Image.open(OUT / "logo-192.png"),
        "social-card.png": Image.open(OUT / "social-card.png"),
    }
    for name, img in tokens.items():
        sheet = sheet.replace("{{" + name + "}}", data_uri(img))
    save_png(render(sheet, 1600).convert("RGB"), BRAND / "preview.png")


if __name__ == "__main__":
    main()
