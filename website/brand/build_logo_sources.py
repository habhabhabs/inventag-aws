#!/usr/bin/env python3
"""Build the InvenTag logo SVG sources: mark, small-size mark, wordmark
lockups, social card and the preview sheet.

This is the *design* step. Run it only when you change geometry, colours or
text. Day-to-day, run `generate_brand_assets.py`, which rasterises the
committed SVGs.

Requirements (design step only):
  pip install fonttools brotli uharfbuzz
Fonts: the site's own self-hosted files in website/static/fonts (SIL OFL 1.1),
so the logo, the social card and the website use exactly the same type.

Concept ("refined classic"): a luggage tag (the "Tag") whose body carries
three inventory lines (the "Inven"tory). A small accent square ends the third
line, and the eyelet sits at the tag's point. Lines, eyelet and accent are
true cut-outs in the one-colour versions, so the mark works in one colour on
any background; the full-colour version fills the accent with vermilion.
Up to 48px use the simplified `logo-small.svg` (every edge on the 16px pixel
grid; the favicons use it).

Identity rules shared with the site (src/css/custom.css):
  ink #141413 / paper #F9F8F6 / dark paper #111110,
  one accent: International Vermilion #E04F33 (#F0623F on dark),
  used twice per lockup at most: the accent square and the "Tag" half of the word.
  Wordmark: Outfit SemiBold (600), "Inven" in ink, "Tag" in vermilion, outlined.
"""
import io
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE.parent / "static" / "fonts"
SANS = FONTS / "instrument-sans-latin-wght-normal.woff2"
MONO = FONTS / "jetbrains-mono-latin-wght-normal.woff2"
OUTFIT = HERE / "fonts" / "outfit-latin-600-normal.woff2"   # wordmark face (OFL, see fonts/OFL-Outfit.txt)

# ---------------------------------------------------------------- palette
INK = "#141413"
INK_2 = "#575652"
PAPER = "#F9F8F6"
SURFACE = "#FFFFFF"
LINE = "#E4E2DD"
CODE_BG = "#F3F1EC"
DARK_BG = "#111110"
DARK_SURFACE = "#1A1A18"
DARK_LINE = "#2A2A27"
DARK_TEXT = "#F2F0EC"
DARK_TEXT_2 = "#A8A59E"
VERMILION = "#E04F33"
VERMILION_DARK = "#F0623F"   # accent on dark backgrounds
ACCENT_INK = "#B83A21"


def rounded_polygon(points, radii):
    """SVG path for a polygon with a circular fillet of radius r at each vertex."""
    n = len(points)
    segs = []
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        r = radii[i]
        if r == 0:
            r = 1e-6
        v1 = (p0[0] - p1[0], p0[1] - p1[1]); v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = math.hypot(*v1); l2 = math.hypot(*v2)
        u1 = (v1[0] / l1, v1[1] / l1); u2 = (v2[0] / l2, v2[1] / l2)
        ang = math.acos(max(-1, min(1, u1[0] * u2[0] + u1[1] * u2[1])))
        d = r / math.tan(ang / 2)
        a = (p1[0] + u1[0] * d, p1[1] + u1[1] * d)
        b = (p1[0] + u2[0] * d, p1[1] + u2[1] * d)
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        sweep = 1 if cross < 0 else 0
        segs.append((a, b, r, sweep))
    out = [f"M{f(segs[0][1][0])} {f(segs[0][1][1])}"]
    for i in range(1, n + 1):
        a, b, r, sw = segs[i % n]
        out.append(f"L{f(a[0])} {f(a[1])}A{f(r)} {f(r)} 0 0 {sw} {f(b[0])} {f(b[1])}")
    return "".join(out) + "Z"


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def rect(x, y, w, h, r):
    return rounded_polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [r] * 4)


def circle(cx, cy, r):
    return f"M{cx + r} {cy}A{r} {r} 0 1 0 {cx - r} {cy}A{r} {r} 0 1 0 {cx + r} {cy}Z"


# ---------------------------------------------------------------- geometry (64 grid)
# Tag silhouette: 40 units tall (y 12..52), left corners r8, point rounded r4.
TAG = "M14 12H36.5A8 8 0 0 1 42 14.2L58.6 29.4A4 4 0 0 1 58.6 34.6L42 49.8A8 8 0 0 1 36.5 52H14A8 8 0 0 1 6 44V20A8 8 0 0 1 14 12Z"
ROWS = [rect(14, 20, 22, 4, 2), rect(14, 30, 15, 4, 2), rect(14, 40, 8, 4, 2)]
EYELET = circle(48, 32, 3.6)
ACCENT = rect(26, 40, 4, 4, 2)             # ends the third line (a 4x4 unit with r2)

# small-size variant: every edge on the 16px pixel grid (1px = 4 units at 16px)
TAG_SMALL = [(4, 12), (40, 12), (60, 32), (40, 52), (4, 52)]
TAG_SMALL_R = [4, 4, 2, 4, 4]
ROWS_SMALL = [rect(12, 24, 24, 4, 0), rect(12, 32, 16, 4, 0), rect(12, 40, 8, 4, 0)]
ACCENT_SMALL = rect(24, 40, 4, 4, 0)
EYELET_SMALL = rect(44, 28, 8, 8, 2)


def mark_path(small=False, accent_cutout=False):
    """Tag with lines and eyelet cut out (fill-rule evenodd). In one-colour
    versions the accent square is a cut-out too (accent_cutout=True)."""
    if small:
        d = rounded_polygon(TAG_SMALL, TAG_SMALL_R) + "".join(ROWS_SMALL) + EYELET_SMALL
        return d + (ACCENT_SMALL if accent_cutout else "")
    d = TAG + "".join(ROWS) + EYELET
    return d + (ACCENT if accent_cutout else "")


def accent_path(small=False):
    return ACCENT_SMALL if small else ACCENT


def svg(view_w, view_h, body, w=None, h=None, title="InvenTag"):
    w = w or view_w; h = h or view_h
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" '
            f'width="{w}" height="{h}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{body}</svg>\n')


# ---------------------------------------------------------------- type
_font_cache = {}


def load_font(path, wght):
    """Static instance (TTF bytes + TTFont) of a variable woff2 at weight `wght`."""
    key = (str(path), wght)
    if key not in _font_cache:
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        tt = TTFont(str(path))
        if "fvar" in tt:
            tt = instancer.instantiateVariableFont(tt, {"wght": wght})
        tt.flavor = None
        buf = io.BytesIO(); tt.save(buf)
        data = buf.getvalue()
        _font_cache[key] = (data, TTFont(io.BytesIO(data)))
    return _font_cache[key]


def shape(path, wght, text, size, x0, baseline, tracking=0.0):
    """Outline `text` as SVG path data. tracking is in em (e.g. -0.03)."""
    import uharfbuzz as hb
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    data, tt = load_font(path, wght)
    face = hb.Face(data); font = hb.Font(face)
    upem = face.upem
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    s = size / upem
    x = 0.0; per_glyph = []
    infos = list(zip(buf.glyph_infos, buf.glyph_positions))
    for i, (info, pos) in enumerate(infos):
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        tp = TransformPen(pen, (s, 0, 0, -s, x0 + (x + pos.x_offset) * s, baseline - pos.y_offset * s))
        gs[order[info.codepoint]].draw(tp)
        per_glyph.append(pen.getCommands())
        x += pos.x_advance
        if i < len(infos) - 1:
            x += tracking * upem
    return per_glyph, x * s


def cap_height(path, wght):
    _, tt = load_font(path, wght)
    return tt["OS/2"].sCapHeight / tt["head"].unitsPerEm


def text_path(path, wght, text, size, x, baseline, fill, tracking=0.0, anchor="start"):
    glyphs, adv = shape(path, wght, text, size, 0, 0, tracking)
    if anchor == "end":
        x -= adv
    glyphs, adv = shape(path, wght, text, size, x, baseline, tracking)
    return f'<path fill="{fill}" d="{"".join(glyphs)}"/>', adv


# ---------------------------------------------------------------- lockups
WORD_SIZE = 34
WORD_WGHT = 600
WORD_TRACK = -0.01          # em


def wordmark():
    """'InvenTag' outlined in Outfit SemiBold, cap height centred on the tag body
    (y=32). Returns (ink_path_d for 'Inven', accent_path_d for 'Tag', advance)."""
    cap = cap_height(OUTFIT, WORD_WGHT) * WORD_SIZE
    baseline = 32 + cap / 2
    glyphs, adv = shape(OUTFIT, WORD_WGHT, "InvenTag", WORD_SIZE, 76, baseline, WORD_TRACK)
    return "".join(glyphs[:5]), "".join(glyphs[5:]), adv


def mark_group(fill, accent=None, small=False):
    """Full-colour mark if `accent` is a colour, otherwise one-colour (accent is a cut-out)."""
    d = mark_path(small, accent_cutout=accent is None)
    extra = f'<path fill="{accent}" d="{accent_path(small)}"/>' if accent else ""
    return f'<path fill="{fill}" fill-rule="evenodd" d="{d}"/>{extra}'


def lockup_group(ink, accent):
    """Mark plus wordmark. accent=None gives the one-colour lockup."""
    ink_d, tag_d, _ = wordmark()
    return (mark_group(ink, accent) + f'<path fill="{ink}" d="{ink_d}"/>'
            f'<path fill="{accent or ink}" d="{tag_d}"/>')


# ---------------------------------------------------------------- social card
def social_card():
    """1200x630 Open Graph card. Flat paper background, no gradients, glow or
    shadows. All text is outlined, so the PNG renders the same everywhere."""
    W, H = 1200, 630
    M = 72
    p = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    s = 1.5
    p.append(f'<g transform="translate({M - 6 * s} {64 - 12 * s}) scale({s})">{lockup_group(INK, VERMILION)}</g>')
    t, _ = text_path(MONO, 500, "OPEN-SOURCE CLI  ·  MIT", 18, W - M, 112, INK_2, 0.04, "end")
    p.append(t)
    y = 292
    t, _ = text_path(SANS, 600, "See what runs in your", 72, M, y, INK, -0.03); p.append(t)
    t, _ = text_path(SANS, 600, "AWS accounts.", 72, M, y + 82, INK, -0.03); p.append(t)
    t, _ = text_path(SANS, 500, "Check the tags. Hand over the report.", 32, M, y + 158, INK_2, -0.01); p.append(t)
    yb = 520
    p.append(f'<rect x="{M}" y="{yb - 36}" width="{560}" height="56" rx="4" fill="{SURFACE}" '
             f'stroke="{LINE}" stroke-width="2"/>')
    t, w = text_path(MONO, 600, "$", 22, M + 20, yb, ACCENT_INK); p.append(t)
    t, _ = text_path(MONO, 500, "./inventag.sh --create-excel", 22, M + 20 + w + 14, yb, INK); p.append(t)
    t, _ = text_path(MONO, 500, "habhabhabs.github.io/inventag-aws", 20, W - M, yb, INK, 0, "end"); p.append(t)
    t, _ = text_path(SANS, 500, "Independent open-source project. Not affiliated with or endorsed by "
                     "Amazon Web Services.", 17, M, H - 36, INK_2); p.append(t)
    return svg(W, H, "".join(p), title="InvenTag: see what runs in your AWS accounts. "
               "Check the tags. Hand over the report.")


# ---------------------------------------------------------------- preview sheet
def preview_sheet(lock_w):
    """Logo in context: navbar (light/dark), browser tab with the favicon,
    sizes, one-colour versions and the social card. {{name}} tokens are
    replaced with data URIs of the rendered PNGs by generate_brand_assets.py."""
    W, H = 1600, 1330
    p = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']

    def label(text, x, y, fill=INK_2):
        t, _ = text_path(MONO, 500, text.upper(), 13, x, y, fill, 0.06)
        p.append(t)

    def navbar(x, y, w, dark):
        bg, line, ink, ink2 = ((DARK_BG, DARK_LINE, DARK_TEXT, DARK_TEXT_2) if dark
                               else (PAPER, LINE, INK, INK_2))
        acc = VERMILION_DARK if dark else VERMILION
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="60" fill="{bg}"/>'
                 f'<path d="M{x} {y + 59.5}H{x + w}" stroke="{line}"/>')
        s = NAV_H / 64
        p.append(f'<g transform="translate({x + 21} {y + (60 - NAV_H) / 2}) scale({s})">'
                 f'{lockup_group(PAPER if dark else INK, acc)}</g>')
        nx = x + 24 + lock_w * s + 28
        for i, item in enumerate(["Docs", "Quick start", "CLI reference"]):
            t, a = text_path(SANS, 500, item, 15, nx, y + 35, ink if i == 0 else ink2); p.append(t)
            if i == 0:
                p.append(f'<rect x="{nx}" y="{y + 58}" width="{a}" height="2" fill="{VERMILION}"/>')
            nx += a + 28
        p.append(f'<rect x="{x + w - 200}" y="{y + 15}" width="170" height="30" rx="4" '
                 f'fill="{DARK_SURFACE if dark else SURFACE}" stroke="{DARK_TEXT_2 if dark else "#8A8780"}"/>')
        t, _ = text_path(SANS, 400, "Search", 14, x + w - 186, y + 35, ink2); p.append(t)

    label("Navbar, light", 60, 70)
    navbar(60, 84, 1480, False)
    p.append(f'<rect x="60" y="84" width="1480" height="60" fill="none" stroke="{LINE}"/>')
    label("Navbar, dark", 60, 194)
    navbar(60, 208, 1480, True)

    def tab(x, y, dark, fav):
        chrome, tabbg, ink = (("#202124", "#35363A", "#E8EAED") if dark else ("#DEE1E6", "#FFFFFF", "#202124"))
        p.append(f'<rect x="{x}" y="{y}" width="700" height="56" fill="{chrome}"/>'
                 f'<path d="M{x + 16} {y + 56}V{y + 18}a8 8 0 0 1 8-8H{x + 284}a8 8 0 0 1 8 8V{y + 56}Z" fill="{tabbg}"/>'
                 f'<image x="{x + 30}" y="{y + 25}" width="16" height="16" href="{{{{{fav}}}}}"/>')
        t, _ = text_path(SANS, 400, "Quick start | InvenTag", 13, x + 56, y + 38, ink); p.append(t)
    label("Browser tab, favicon at 16px", 60, 330)
    tab(60, 344, False, "favicon-16-light.png")
    tab(840, 344, True, "favicon-16-dark.png")

    label("Mark sizes", 60, 470)
    x = 60
    for size in (16, 24, 32, 48, 64, 128):
        small = size <= 48
        s = size / 64
        p.append(f'<g transform="translate({x} {490 + (128 - size)})  scale({s})">{mark_group(INK, VERMILION, small)}</g>')
        label(f"{size}", x, 640)
        x += max(size, 40) + 40
    label("Lockups", 700, 470)
    p.append(f'<g transform="translate(700 500)">{lockup_group(INK, VERMILION)}</g>')
    p.append(f'<rect x="1080" y="490" width="{lock_w + 40}" height="84" fill="{DARK_BG}"/>'
             f'<g transform="translate(1100 500)">{lockup_group(PAPER, VERMILION_DARK)}</g>')
    p.append(f'<g transform="translate(700 590) scale(0.75)">{lockup_group(INK, None)}</g>')
    p.append(f'<rect x="1080" y="584" width="64" height="64" fill="{VERMILION}"/>'
             f'<g transform="translate(1080 584)">{mark_group(INK)}</g>')
    p.append(f'<rect x="1160" y="584" width="64" height="64" fill="{INK}"/>'
             f'<g transform="translate(1160 584)">{mark_group(PAPER)}</g>')
    label("one colour", 1240, 622)

    label("Touch icon 180, manifest icon 192", 60, 700)
    p.append('<image x="60" y="716" width="180" height="180" href="{{apple-touch-icon.png}}"/>')
    p.append(f'<rect x="60" y="716" width="180" height="180" fill="none" stroke="{LINE}"/>')
    p.append('<image x="260" y="716" width="192" height="192" href="{{logo-192.png}}"/>')
    label("Social card, 1200 x 630 (shown at 50%)", 700, 700)
    p.append('<image x="700" y="716" width="600" height="315" href="{{social-card.png}}"/>')
    p.append(f'<rect x="700" y="716" width="600" height="315" fill="none" stroke="{LINE}"/>')

    label("Palette", 60, 1100)
    sw = [("Ink", INK), ("Paper", PAPER), ("Surface", SURFACE), ("Hairline", LINE),
          ("Vermilion", VERMILION), ("Vermilion dark", VERMILION_DARK), ("Dark", DARK_BG), ("Accent ink", ACCENT_INK)]
    for i, (name, hexv) in enumerate(sw):
        x = 60 + i * 185
        p.append(f'<rect x="{x}" y="1116" width="165" height="96" fill="{hexv}" stroke="{LINE}"/>')
        label(name, x, 1236, INK)
        label(hexv, x, 1256)
    t, _ = text_path(SANS, 500, "Regenerate: python3 website/brand/build_logo_sources.py && "
                     "python3 website/brand/generate_brand_assets.py", 15, 60, 1300, INK_2)
    p.append(t)
    return svg(W, H, "".join(p), title="InvenTag brand preview")


NAV_H = 40   # navbar lockup height in px (docusaurus.config.ts / custom.css use the same)


def main():
    _, _, word_adv = wordmark()
    lock_w = math.ceil(76 + word_adv + 6)

    def mark_svg(fill, accent=None, is_small=False, size=64):
        return svg(64, 64, mark_group(fill, accent, is_small), size, size)

    files = {
        "logo.svg": mark_svg(INK, VERMILION),                  # light backgrounds
        "logo-dark.svg": mark_svg(PAPER, VERMILION_DARK),      # dark backgrounds
        "logo-on-brand.svg": mark_svg(INK),                    # one colour on a vermilion field
        "logo-mono.svg": mark_svg("currentColor"),
        "logo-mono-black.svg": mark_svg("#000"),
        "logo-mono-white.svg": mark_svg("#fff"),
        "logo-small.svg": mark_svg(INK, VERMILION, True),
        "logo-small-dark.svg": mark_svg(PAPER, VERMILION_DARK, True),
    }
    # favicon.svg: small geometry; ink in light browsers, paper in dark ones
    files["favicon.svg"] = svg(64, 64,
        '<style>.t{fill:%s}.a{fill:%s}@media (prefers-color-scheme:dark){.t{fill:%s}.a{fill:%s}}</style>'
        '<path class="t" fill-rule="evenodd" d="%s"/><path class="a" d="%s"/>'
        % (INK, VERMILION, PAPER, VERMILION_DARK, mark_path(True), accent_path(True)), 64, 64)

    def lockup(ink, accent):
        return svg(lock_w, 64, lockup_group(ink, accent))
    files["logo-wordmark.svg"] = lockup(INK, VERMILION)
    files["logo-wordmark-dark.svg"] = lockup(PAPER, VERMILION_DARK)
    files["logo-wordmark-mono.svg"] = lockup("currentColor", None)
    files["social-card.svg"] = social_card()
    files["preview-sheet.svg"] = preview_sheet(lock_w)

    src = HERE / "src"; src.mkdir(exist_ok=True)
    for name, body in files.items():
        (src / name).write_text(body)
        print("wrote", (src / name).relative_to(HERE.parent.parent))


if __name__ == "__main__":
    main()
