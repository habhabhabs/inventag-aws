# InvenTag brand assets

![The logo in context: navbar, browser tab, sizes, lockups, app icons, social card, palette](preview.png)

## The mark

A luggage tag (the **Tag**) whose body carries three inventory lines (the
**Inven**tory). The last line ends in a terminal block cursor, because
InvenTag is a CLI. The eyelet sits at the tag's point. Lines, cursor and
eyelet are cut-outs, so the mark works in one colour on any background; the
full-colour version fills the cursor with vermilion. That cursor is the only
accent in any lockup.

Below about 40px use `logo-small.svg`: two lines and the cursor, every edge on
the 16px pixel grid. The favicons use it.

The identity shares the site's system:

- **Colour:** ink and paper, with International Vermilion used once.
- **Radius:** at the 28px navbar size the tag's corners are 4px, the same
  radius as the site's buttons, inputs and code blocks.
- **Type:** the wordmark is Instrument Sans SemiBold at -0.03em tracking, the
  site's display face and heading tracking, outlined to paths. The social card
  uses Instrument Sans and JetBrains Mono, the site's body and code faces.
- **Grid:** the social card uses the same 1px hairline grid as the homepage.

## Palette and contrast

Contrast is WCAG 2.x relative luminance, computed for every pair the site uses
(the same values are in `src/css/custom.css`).

| Token | Light | Dark |
|---|---|---|
| Background | `#F9F8F6` | `#111110` |
| Surface | `#FFFFFF` | `#1A1A18` |
| Code background | `#F3F1EC` | `#161615` |
| Text (ink) | `#141413` | `#F2F0EC` |
| Secondary text | `#575652` | `#A8A59E` |
| Hairline (decorative) | `#E4E2DD` | `#2A2A27` |
| Control border | `#8A8780` | `#77756E` |
| Vermilion (fills, focus ring) | `#E04F33` | `#E04F33` |
| Accent text | `#B83A21` | `#F07A5F` |

| Pair | Ratio | Needs | Result |
|---|---|---|---|
| Ink `#141413` on background `#F9F8F6` / surface `#FFFFFF` | 17.37 / 18.43 | 4.5 | pass |
| Secondary `#575652` on background / surface / code `#F3F1EC` | 6.92 / 7.35 / 6.51 | 4.5 | pass |
| Accent text `#B83A21` on background / surface / active tint `#FBEDE9` | 5.40 / 5.73 / 5.02 | 4.5 | pass |
| **Ink `#141413` on vermilion `#E04F33`** (primary button) | 4.68 | 4.5 | pass |
| White `#FFFFFF` on vermilion (not used) | 3.94 | 4.5 | **fail, rejected** |
| Vermilion focus ring on background / surface | 3.71 / 3.94 | 3 (non-text) | pass |
| Control border `#8A8780` on background / surface | 3.38 / 3.58 | 3 (non-text) | pass |
| Dark text `#F2F0EC` on `#111110` / `#1A1A18` | 16.60 / 15.31 | 4.5 | pass |
| Dark secondary `#A8A59E` on `#111110` / `#1A1A18` / code `#161615` | 7.68 / 7.09 / 7.36 | 4.5 | pass |
| Dark accent text `#F07A5F` on `#111110` / `#1A1A18` / tint `#2A1C17` | 6.89 / 6.35 / 5.99 | 4.5 | pass |
| Vermilion focus ring on `#111110` / `#1A1A18` | 4.80 / 4.43 | 3 (non-text) | pass |
| Dark control border `#77756E` on `#111110` / `#1A1A18` | 4.10 / 3.78 | 3 (non-text) | pass |
| Admonition labels, light (on `#FFFFFF`): tip `#2F6B3A`, info `#1F4E8C`, warning `#8A4B00` | 6.39 / 8.31 / 6.80 | 4.5 | pass |
| Admonition labels, dark (on `#1A1A18`): tip `#A9C98F`, info `#8DB4E2`, warning `#E0B070` | 9.49 / 8.10 / 8.81 | 4.5 | pass |

Syntax colours (`src/theme-config/prism.ts`), against the code background and
against the highlighted-line background (`#F7E4DD` light, `#2B1F1A` dark):

| Token | Light | on `#F3F1EC` | on highlight | Dark | on `#161615` | on highlight |
|---|---|---|---|---|---|---|
| plain | `#141413` | 16.33 | | `#F2F0EC` | 15.91 | |
| comment | `#66645E` | 5.24 | 4.82 | `#9C998F` | 6.35 | 5.61 |
| keyword | `#B83A21` | 5.08 | 4.66 | `#F07A5F` | 6.60 | 5.83 |
| string | `#2F6B3A` | 5.66 | 5.20 | `#A9C98F` | 9.86 | |
| function | `#1F4E8C` | 7.36 | | `#8DB4E2` | 8.42 | |
| number | `#8A4B00` | 6.03 | | `#E0B070` | 9.15 | |
| punctuation | `#575652` | 6.51 | | `#B5B2AA` | 8.55 | |
| property | `#6B3F8C` | 6.85 | | `#C9A6E0` | 8.64 | |
| variable | `#2F5D7C` | 6.25 | | `#8FC1D9` | 9.31 | |

`npm run check:a11y` measures the rendered pages as well, so a new colour that
breaks these ratios fails the check.

## Files

| Source (`src/`) | Published as (`../static/`) | Notes |
|---|---|---|
| `logo.svg` | `img/logo.svg` | ink tag, vermilion cursor: light backgrounds, light navbar |
| `logo-dark.svg` | `img/logo-dark.svg` | paper tag, vermilion cursor: dark backgrounds, dark navbar |
| `logo-on-brand.svg` | `img/logo-on-brand.svg` | one-colour ink mark for a vermilion field |
| `logo-mono*.svg` | same names | one colour: `currentColor`, black, white |
| `logo-small.svg`, `logo-small-dark.svg` | same names, `img/favicon-32.png`, `img/favicon.ico` (16/32/48) | pixel-aligned small mark; PNG/ICO get a 1px paper halo so they stay visible on dark tab bars |
| `favicon.svg` | `img/favicon.svg` | small mark; ink in light browsers, paper in dark ones (`prefers-color-scheme`) |
| `logo-wordmark*.svg` | same names | horizontal lockups: light, dark, one-colour |
| `social-card.svg` | `img/social-card.png` (1200x630) | Open Graph / Twitter card, all text outlined |
| | `img/apple-touch-icon.png` (180) | mark on an opaque paper tile |
| | `img/logo-192.png`, `img/logo-512.png`, `img/logo-maskable-512.png` | web-manifest icons (maskable keeps the mark in the safe zone) |
| | `site.webmanifest` | name, colours, icons (paths include `/inventag-aws/`) |
| `preview-sheet.svg` | `preview.png` (here) | the logo in context, with the real PNGs embedded |

## Regenerating the PNGs, favicons and social card

```bash
# needs rsvg-convert (brew install librsvg / apt install librsvg2-bin) and Pillow
python3 website/brand/generate_brand_assets.py
# or: cd website && npm run brand
```

This rasterises the SVGs in `src/`, writes everything listed above, and
re-renders `preview.png`. Look at the preview (the browser-tab favicon
especially) before committing.

## Changing the design

Shapes, colours, the wordmark, the social card and the preview sheet are
generated by `build_logo_sources.py`. It uses the site's own font files in
`website/static/fonts`, so no other fonts are needed:

```bash
pip install fonttools brotli uharfbuzz
python3 website/brand/build_logo_sources.py
python3 website/brand/generate_brand_assets.py
```

Keep the social card's claims to things the code does, and keep the "not
affiliated with or endorsed by Amazon Web Services" line. The card has no
version number on purpose, so it does not go stale at each release.

## Rules of thumb

- Don't put the mark on a busy photo; it needs a flat background.
- One vermilion element per lockup: the cursor. Don't colour the wordmark.
- Don't recolour the cursor in the one-colour version: it is a cut-out.
- Don't add AWS logos, the AWS smile/arrow, or AWS service icons to any lockup.
