#!/usr/bin/env python3
"""Build the InvenTag logo SVG sources (mark, small-size mark, wordmark lockups).

This is the *design* step. You only need it if you change the geometry or the
wordmark text. Day-to-day, edit nothing here and just run
`generate_brand_assets.py`, which rasterises the committed SVGs.

Requirements (design step only):
  pip install fonttools uharfbuzz
  Inter Display Bold (SIL OFL 1.1, https://rsms.me/inter/), path via --font.

Concept: a luggage-style tag (the "Tag") whose body carries inventory rows
(the "Inven"tory), with a terminal block cursor at the end of the last row
(it is a CLI tool). Rows, cursor and eyelet are true cut-outs, so the mark
works in one colour on any background; the full-colour version fills the
cursor with amber. Below ~40px use the simplified `logo-small.svg` (two rows,
no cursor), whose edges land on whole pixels at 16px.
"""
import argparse, math, pathlib

HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------- palette
INK = "#0f172a"        # wordmark text on light backgrounds
PAPER = "#f8fafc"      # wordmark text on dark backgrounds
BLUE = "#1d4ed8"       # mark on light backgrounds (7.1:1 on white)
BLUE_DARK_BG = "#60a5fa"  # mark on dark backgrounds (7.0:1 on #0f172a)
AMBER = "#fbbf24"      # cursor accent (full-colour version only, decorative)


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
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    out = [f"M{f(segs[0][1][0])} {f(segs[0][1][1])}"]
    for i in range(1, n + 1):
        a, b, r, sw = segs[i % n]
        out.append(f"L{f(a[0])} {f(a[1])}A{f(r)} {f(r)} 0 0 {sw} {f(b[0])} {f(b[1])}")
    return "".join(out) + "Z"


def rect(x, y, w, h, r):
    return rounded_polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [r] * 4)


def circle(cx, cy, r):
    # two arcs, drawn counter-clockwise so evenodd and nonzero both cut it out
    return (f"M{cx + r} {cy}A{r} {r} 0 1 0 {cx - r} {cy}A{r} {r} 0 1 0 {cx + r} {cy}Z")


# ---------------------------------------------------------------- geometry (64 grid)
TAG = [(4, 12), (40, 12), (60, 32), (40, 52), (4, 52)]
TAG_R = [7, 6, 4.5, 6, 7]
# small-size variant: every edge lands on the 16px pixel grid (multiples of 4)
TAG_SMALL_R = [4, 4, 2, 4, 4]


CURSOR = rect(25, 38, 6, 7, 1)


def mark_path(small=False):
    if small:
        # 16-32px variant: two 2px rows and a 2px eyelet on whole pixels at 16px
        body = rounded_polygon(TAG, TAG_SMALL_R)
        rows = [rect(12, 20, 24, 8, 1), rect(12, 36, 16, 8, 1)]
        hole = rect(40, 28, 8, 8, 1)  # 2x2 px at 16px; a circle this small blurs
    else:
        # three inventory lines of different length (reads as a list, not a letter)
        body = rounded_polygon(TAG, TAG_R)
        rows = [rect(12, 20, 23, 5, 2.5), rect(12, 29.5, 14, 5, 2.5), rect(12, 39, 10, 5, 2.5),
                CURSOR]
        hole = circle(46, 32, 4.5)
    return body + "".join(rows) + hole


def svg(view_w, view_h, body, w=None, h=None, title="InvenTag"):
    w = w or view_w; h = h or view_h
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" '
            f'width="{w}" height="{h}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{body}</svg>\n')


def wordmark_paths(font_path, text, size, x0, baseline):
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob); font = hb.Font(face)
    upem = face.upem
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    tt = TTFont(font_path); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    s = size / upem
    x = 0; per_char = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        tp = TransformPen(pen, (s, 0, 0, -s, x0 + (x + pos.x_offset) * s, baseline))
        gs[name].draw(tp)
        per_char.append(pen.getCommands())
        x += pos.x_advance
    return per_char, x * s


MONO_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
TEXT_FONT = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def text_path(font, text, size, x, baseline, fill):
    glyphs, adv = wordmark_paths(font, text, size, x, baseline)
    return f'<path fill="{fill}" d="{"".join(glyphs)}"/>', adv


def social_card(a, big, inven, tag, adv):
    """1200x630 Open Graph card. All text is outlined, so the PNG renders the
    same everywhere (no emoji, no font fallback boxes)."""
    W, H = 1200, 630
    BG, MUTED, CMD, RULE = "#0f172a", "#cbd5e1", "#93c5fd", "#1e293b"
    parts = [f'<rect width="{W}" height="{H}" fill="{BG}"/>']
    # oversized mark, bottom-right, as a quiet backdrop
    parts.append(f'<g transform="translate(790 230) scale(7.2)" opacity="0.10">'
                 f'<path fill="{BLUE_DARK_BG}" fill-rule="evenodd" d="{big}"/></g>')
    # lockup at 2x (mark 128px tall)
    parts.append(f'<g transform="translate(72 64) scale(2)">'
                 f'<path fill="{BLUE_DARK_BG}" fill-rule="evenodd" d="{big}"/>'
                 f'<path fill="{AMBER}" d="{CURSOR}"/>'
                 f'<path fill="{PAPER}" d="{inven}"/><path fill="{BLUE_DARK_BG}" d="{tag}"/></g>')
    y = 280
    t, _ = text_path(TEXT_FONT, "AWS resource inventory, tag compliance", 40, 80, y, PAPER); parts.append(t)
    t, _ = text_path(TEXT_FONT, "checks and Excel/Word BOM reports.", 40, 80, y + 52, PAPER); parts.append(t)
    # terminal line
    parts.append(f'<rect x="72" y="{y + 92}" width="640" height="64" rx="12" fill="{RULE}"/>')
    t, w = text_path(MONO_FONT, "$", 26, 96, y + 133, AMBER); parts.append(t)
    t, _ = text_path(MONO_FONT, "./inventag.sh --create-excel", 26, 96 + w + 16, y + 133, CMD); parts.append(t)
    # facts (all backed by the code), separated by small squares
    facts = ["Multi-account", "Change tracking", "Open source (MIT)"]
    x = 80
    for i, f_ in enumerate(facts):
        if i:
            parts.append(f'<rect x="{x + 14}" y="{y + 214}" width="8" height="8" rx="1.5" fill="{BLUE_DARK_BG}"/>')
            x += 36
        t, w = text_path(TEXT_FONT, f_, 26, x, y + 226, MUTED); parts.append(t); x += w
    t, _ = text_path(TEXT_FONT, "habhabhabs.github.io/inventag-aws", 22, 80, 566, MUTED); parts.append(t)
    t, _ = text_path(TEXT_FONT, "Independent open-source project. Not affiliated with Amazon Web Services.", 17, 80, 598, "#94a3b8")
    parts.append(t)
    return svg(W, H, "".join(parts), title="InvenTag: AWS inventory, tag compliance and BOM reports")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf")
    a = ap.parse_args()
    big, small = mark_path(False), mark_path(True)

    def mark_svg(path, fill, size=64, cursor=None):
        extra = f'<path fill="{cursor}" d="{CURSOR}"/>' if cursor else ""
        return svg(64, 64, f'<path fill="{fill}" fill-rule="evenodd" d="{path}"/>{extra}', size, size)

    files = {
        "logo.svg": mark_svg(big, BLUE, cursor=AMBER),
        "logo-dark.svg": mark_svg(big, BLUE_DARK_BG, cursor=AMBER),
        # white tag for the blue navbar/hero (light theme); cut-outs show the blue
        "logo-on-brand.svg": mark_svg(big, "#ffffff", cursor=AMBER),
        "logo-mono.svg": mark_svg(big, "currentColor"),
        "logo-mono-black.svg": mark_svg(big, "#000"),
        "logo-mono-white.svg": mark_svg(big, "#fff"),
        "logo-small.svg": mark_svg(small, BLUE),
    }
    # favicon.svg: small-size geometry, adapts to the browser's colour scheme
    files["favicon.svg"] = svg(64, 64,
        '<style>path{fill:%s}@media (prefers-color-scheme:dark){path{fill:%s}}</style>'
        '<path fill-rule="evenodd" d="%s"/>' % (BLUE, BLUE_DARK_BG, small), 64, 64)

    # wordmark lockup: mark (64 grid) + "InvenTag" set in Inter Display Bold
    glyphs, adv = wordmark_paths(a.font, "InvenTag", 40, 76, 46)
    inven, tag = "".join(glyphs[:5]), "".join(glyphs[5:])
    W = math.ceil(76 + adv + 4); H = 64
    def lockup(mark_fill, inven_fill, tag_fill, cursor=None):
        extra = f'<path fill="{cursor}" d="{CURSOR}"/>' if cursor else ""
        return svg(W, H,
            f'<path fill="{mark_fill}" fill-rule="evenodd" d="{big}"/>{extra}'
            f'<path fill="{inven_fill}" d="{inven}"/><path fill="{tag_fill}" d="{tag}"/>')
    files["logo-wordmark.svg"] = lockup(BLUE, INK, BLUE, AMBER)
    files["logo-wordmark-dark.svg"] = lockup(BLUE_DARK_BG, PAPER, BLUE_DARK_BG, AMBER)
    files["logo-wordmark-mono.svg"] = lockup("currentColor", "currentColor", "currentColor")
    files["social-card.svg"] = social_card(a, big, inven, tag, adv)

    src = HERE / "src"; src.mkdir(exist_ok=True)
    for name, body in files.items():
        (src / name).write_text(body)
        print("wrote", src / name)


if __name__ == "__main__":
    main()
