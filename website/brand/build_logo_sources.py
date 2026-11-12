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

Concept: a luggage tag (the "Tag") whose body carries three inventory lines
(the "Inven"tory). The last line ends in a terminal block cursor, because
InvenTag is a CLI. Lines, cursor and eyelet are true cut-outs, so the mark
works in one colour on any background; the full-colour version fills the
cursor with vermilion. Below ~40px use the simplified `logo-small.svg`
(two lines and the cursor, every edge on the 16px pixel grid).

Identity rules shared with the site (src/css/custom.css):
  ink #141413 / paper #F9F8F6 / dark paper #111110 / text-on-dark #F2F0EC,
  one accent: International Vermilion #E04F33, used once per lockup.
  Corner radius 4px on a 28px mark = the 4px UI radius on 28-44px controls.
  Instrument Sans SemiBold, tracking -0.03em, like the site's display headings.
"""
import io
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE.parent / "static" / "fonts"
SANS = FONTS / "instrument-sans-latin-wght-normal.woff2"
MONO = FONTS / "jetbrains-mono-latin-wght-normal.woff2"

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
ACCENT_INK = "#B83A21"


def rounded_polygon(points, radii):
    """SVG path for a polygon with a circular fillet of radius r at each vertex."""
    n = len(points)
    segs = []
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        r = radii[i]
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
# Tag body 36 units tall; at the 28px navbar size a 9-unit corner = 4px,
# the same radius as the site's buttons and inputs.
TAG = [(5, 14), (39, 14), (59, 32), (39, 50), (5, 50)]
TAG_R = [8, 7, 3.5, 7, 8]
ROWS = [rect(13, 21.5, 22, 4, 1), rect(13, 29.5, 14, 4, 1), rect(13, 37.5, 7, 4, 1)]
CURSOR = rect(23, 36, 5, 7, 0.75)          # block cursor after the last line
EYELET = circle(46, 32, 3.75)

# small-size variant: every edge on the 16px pixel grid (multiples of 4)
TAG_SMALL = [(4, 12), (40, 12), (60, 32), (40, 52), (4, 52)]
TAG_SMALL_R = [4, 4, 2, 4, 4]
ROWS_SMALL = [rect(12, 20, 24, 8, 1), rect(12, 36, 12, 8, 1)]
CURSOR_SMALL = rect(28, 36, 8, 8, 1)
EYELET_SMALL = rect(40, 28, 8, 8, 1)


def mark_path(small=False):
    if small:
        return rounded_polygon(TAG_SMALL, TAG_SMALL_R) + "".join(ROWS_SMALL) + CURSOR_SMALL + EYELET_SMALL
    return rounded_polygon(TAG, TAG_R) + "".join(ROWS) + CURSOR + EYELET


def cursor_path(small=False):
    return CURSOR_SMALL if small else CURSOR


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
WORD_TRACK = -0.03


def wordmark():
    """'InvenTag' outlined, cap height centred on the tag body (y=32)."""
    cap = cap_height(SANS, WORD_WGHT) * WORD_SIZE
    baseline = 32 + cap / 2
    glyphs, adv = shape(SANS, WORD_WGHT, "InvenTag", WORD_SIZE, 76, baseline, WORD_TRACK)
    return "".join(glyphs), adv


def mark_group(fill, cursor_fill=None, small=False):
    extra = f'<path fill="{cursor_fill}" d="{cursor_path(small)}"/>' if cursor_fill else ""
    return f'<path fill="{fill}" fill-rule="evenodd" d="{mark_path(small)}"/>{extra}'


# ---------------------------------------------------------------- social card
def social_card(word_d, word_adv):
    """1200x630 Open Graph card. Paper, hairline grid, one vermilion accent.
    All text is outlined, so the PNG renders the same everywhere."""
    W, H = 1200, 630
    M = 56                     # outer margin
    TOP, BOTTOM = 112, 470     # hairline bands
    SPLIT = 812                # vertical hairline
    p = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    # architectural grid lines (1px at 1x)
    p.append(f'<path stroke="{LINE}" stroke-width="2" fill="none" '
             f'd="M0 {TOP}H{W}M0 {BOTTOM}H{W}M{SPLIT} {TOP}V{BOTTOM}"/>')
    # header band: lockup left, label right
    s = 0.75
    p.append(f'<g transform="translate({M - 4} {TOP / 2 - 32 * s}) scale({s})">'
             f'{mark_group(INK, VERMILION)}<path fill="{INK}" d="{word_d}"/></g>')
    t, _ = text_path(MONO, 500, "OPEN-SOURCE CLI  ·  MIT", 18, W - M, TOP / 2 + 6, INK_2, 0.04, "end")
    p.append(t)
    # headline
    y = TOP + 112
    t, _ = text_path(SANS, 600, "See what runs in your", 66, M, y, INK, -0.03); p.append(t)
    t, _ = text_path(SANS, 600, "AWS accounts.", 66, M, y + 76, INK, -0.03); p.append(t)
    t, _ = text_path(SANS, 500, "Check the tags. Hand over the report.", 32, M, y + 150, INK_2, -0.01); p.append(t)
    # right panel: the mark, large and quiet
    ms = 3.6
    cx = SPLIT + (W - SPLIT) / 2; cy = TOP + (BOTTOM - TOP) / 2
    p.append(f'<g transform="translate({cx - 32 * ms} {cy - 32 * ms}) scale({ms})">'
             f'{mark_group(INK, VERMILION)}</g>')
    # bottom band: command and URL
    yb = BOTTOM + 66
    p.append(f'<rect x="{M}" y="{yb - 36}" width="{560}" height="56" rx="4" fill="{SURFACE}" '
             f'stroke="{LINE}" stroke-width="2"/>')
    t, w = text_path(MONO, 600, "$", 22, M + 20, yb, ACCENT_INK); p.append(t)
    t, _ = text_path(MONO, 500, "./inventag.sh --create-excel", 22, M + 20 + w + 14, yb, INK); p.append(t)
    t, _ = text_path(MONO, 500, "habhabhabs.github.io/inventag-aws", 20, W - M, yb, INK, 0, "end"); p.append(t)
    t, _ = text_path(SANS, 500, "Independent open-source project. Not affiliated with or endorsed by "
                     "Amazon Web Services.", 17, M, H - 30, INK_2); p.append(t)
    return svg(W, H, "".join(p), title="InvenTag: see what runs in your AWS accounts. "
               "Check the tags. Hand over the report.")


# ---------------------------------------------------------------- preview sheet
def preview_sheet(word_d, word_adv, lock_w):
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
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="60" fill="{bg}"/>'
                 f'<path d="M{x} {y + 59.5}H{x + w}" stroke="{line}"/>')
        s = 28 / 64
        p.append(f'<g transform="translate({x + 24} {y + 16}) scale({s})">'
                 f'{mark_group(ink, VERMILION)}</g>')
        t, adv = text_path(SANS, 650, "InvenTag", 18, x + 24 + 28 + 9, y + 36, ink, -0.03); p.append(t)
        nx = x + 24 + 28 + 9 + adv + 34
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

    # browser tab mock with the favicon (light and dark browser chrome)
    def tab(x, y, dark, fav):
        chrome, tabbg, ink = (("#202124", "#35363A", "#E8EAED") if dark else ("#DEE1E6", "#FFFFFF", "#202124"))
        p.append(f'<rect x="{x}" y="{y}" width="700" height="56" fill="{chrome}"/>'
                 f'<path d="M{x + 16} {y + 56}V{y + 18}a8 8 0 0 1 8-8H{x + 284}a8 8 0 0 1 8 8V{y + 56}Z" fill="{tabbg}"/>'
                 f'<image x="{x + 30}" y="{y + 25}" width="16" height="16" href="{{{{{fav}}}}}"/>')
        t, _ = text_path(SANS, 400, "Quick start | InvenTag", 13, x + 56, y + 38, ink); p.append(t)
    label("Browser tab, favicon at 16px", 60, 330)
    tab(60, 344, False, "favicon-16-light.png")
    tab(840, 344, True, "favicon-16-dark.png")

    # sizes and versions
    label("Mark sizes", 60, 470)
    x = 60
    for size in (16, 24, 32, 48, 64, 128):
        small = size <= 32
        s = size / 64
        p.append(f'<g transform="translate({x} {490 + (128 - size)})  scale({s})">{mark_group(INK, VERMILION, small)}</g>')
        label(f"{size}", x, 640)
        x += max(size, 40) + 40
    label("Lockups", 700, 470)
    p.append(f'<g transform="translate(700 500)">{mark_group(INK, VERMILION)}<path fill="{INK}" d="{word_d}"/></g>')
    p.append(f'<rect x="1080" y="490" width="{lock_w + 40}" height="84" fill="{DARK_BG}"/>'
             f'<g transform="translate(1100 500)">{mark_group(DARK_TEXT, VERMILION)}'
             f'<path fill="{DARK_TEXT}" d="{word_d}"/></g>')
    p.append(f'<g transform="translate(700 590) scale(0.75)">{mark_group(INK)}<path fill="{INK}" d="{word_d}"/></g>')
    p.append(f'<rect x="1080" y="584" width="64" height="64" fill="{VERMILION}"/>'
             f'<g transform="translate(1080 584)">{mark_group(INK)}</g>')
    p.append(f'<rect x="1160" y="584" width="64" height="64" fill="{INK}"/>'
             f'<g transform="translate(1160 584)">{mark_group(PAPER)}</g>')
    label("one colour", 1240, 622)

    # app icons + social card
    label("Touch icon 180, manifest icon 192", 60, 700)
    p.append('<image x="60" y="716" width="180" height="180" href="{{apple-touch-icon.png}}"/>')
    p.append(f'<rect x="60" y="716" width="180" height="180" fill="none" stroke="{LINE}"/>')
    p.append('<image x="260" y="716" width="192" height="192" href="{{logo-192.png}}"/>')
    label("Social card, 1200 x 630 (shown at 50%)", 700, 700)
    p.append('<image x="700" y="716" width="600" height="315" href="{{social-card.png}}"/>')
    p.append(f'<rect x="700" y="716" width="600" height="315" fill="none" stroke="{LINE}"/>')

    # palette strip
    label("Palette", 60, 1100)
    sw = [("Ink", INK), ("Paper", PAPER), ("Surface", SURFACE), ("Hairline", LINE),
          ("Vermilion", VERMILION), ("Accent ink", ACCENT_INK), ("Dark", DARK_BG), ("Text on dark", DARK_TEXT)]
    for i, (name, hexv) in enumerate(sw):
        x = 60 + i * 185
        p.append(f'<rect x="{x}" y="1116" width="165" height="96" fill="{hexv}" stroke="{LINE}"/>')
        label(name, x, 1236, INK)
        label(hexv, x, 1256)
    t, _ = text_path(SANS, 500, "Regenerate: python3 website/brand/build_logo_sources.py && "
                     "python3 website/brand/generate_brand_assets.py", 15, 60, 1300, INK_2)
    p.append(t)
    return svg(W, H, "".join(p), title="InvenTag brand preview")


def main():
    big, small = mark_path(False), mark_path(True)
    word_d, word_adv = wordmark()
    lock_w = math.ceil(76 + word_adv + 2)

    def mark_svg(fill, cursor=None, is_small=False, size=64):
        return svg(64, 64, mark_group(fill, cursor, is_small), size, size)

    files = {
        "logo.svg": mark_svg(INK, VERMILION),                 # light backgrounds
        "logo-dark.svg": mark_svg(DARK_TEXT, VERMILION),      # dark backgrounds
        "logo-on-brand.svg": mark_svg(INK),                   # one colour on a vermilion field
        "logo-mono.svg": mark_svg("currentColor"),
        "logo-mono-black.svg": mark_svg("#000"),
        "logo-mono-white.svg": mark_svg("#fff"),
        "logo-small.svg": mark_svg(INK, VERMILION, True),
        "logo-small-dark.svg": mark_svg(DARK_TEXT, VERMILION, True),
    }
    # favicon.svg: small geometry; ink tag in light browsers, paper tag in dark ones
    files["favicon.svg"] = svg(64, 64,
        '<style>.t{fill:%s}@media (prefers-color-scheme:dark){.t{fill:%s}}</style>'
        '<path class="t" fill-rule="evenodd" d="%s"/><path fill="%s" d="%s"/>'
        % (INK, DARK_TEXT, small, VERMILION, CURSOR_SMALL), 64, 64)

    def lockup(mark_fill, word_fill, cursor=None):
        return svg(lock_w, 64, mark_group(mark_fill, cursor) + f'<path fill="{word_fill}" d="{word_d}"/>')
    files["logo-wordmark.svg"] = lockup(INK, INK, VERMILION)
    files["logo-wordmark-dark.svg"] = lockup(DARK_TEXT, DARK_TEXT, VERMILION)
    files["logo-wordmark-mono.svg"] = lockup("currentColor", "currentColor")
    files["social-card.svg"] = social_card(word_d, word_adv)
    files["preview-sheet.svg"] = preview_sheet(word_d, word_adv, lock_w)

    src = HERE / "src"; src.mkdir(exist_ok=True)
    for name, body in files.items():
        (src / name).write_text(body)
        print("wrote", (src / name).relative_to(HERE.parent.parent))


if __name__ == "__main__":
    main()
