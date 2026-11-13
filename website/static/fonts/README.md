# Self-hosted fonts

The site loads no fonts from Google or any other third party. These WOFF2
files are served from this folder (via `@font-face` in `src/css/custom.css`)
with `font-display: swap`. The two faces every page uses are preloaded in
`docusaurus.config.ts`.

| File | Family, axis | Used for | Size |
|---|---|---|---|
| `instrument-sans-latin-wght-normal.woff2` | Instrument Sans, weight 400-700 | headings and body text (preloaded) | 30 KB |
| `instrument-sans-latin-wght-italic.woff2` | Instrument Sans Italic, weight 400-700 | italic body text | 32 KB |
| `jetbrains-mono-latin-wght-normal.woff2` | JetBrains Mono, weight 100-800 | code, labels, metadata (preloaded) | 40 KB |
| `newsreader-latin-wght-italic.woff2` | Newsreader Italic, weight 200-800 | a few editorial accents (homepage) | 64 KB |

All four are variable fonts, subset to Latin (U+0000-00FF plus common
punctuation; the exact `unicode-range` is in `custom.css`). Characters outside
the subset (box drawing, arrows such as U+2192) fall back to the system font.

## Source and licence

| Font | Source | Version | Licence |
|---|---|---|---|
| Instrument Sans | npm `@fontsource-variable/instrument-sans@5.3.0` (files from [google/fonts](https://github.com/google/fonts), upstream [Instrument/instrument-sans](https://github.com/Instrument/instrument-sans), font version v4, 2025-09-05) | 5.3.0 | SIL OFL 1.1, `OFL-InstrumentSans.txt` |
| JetBrains Mono | npm `@fontsource-variable/jetbrains-mono@5.3.0` (upstream [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono), font version v24, 2025-09-11) | 5.3.0 | SIL OFL 1.1, `OFL-JetBrainsMono.txt` |
| Newsreader | npm `@fontsource-variable/newsreader@5.3.0` (upstream [productiontype/Newsreader](https://github.com/productiontype/Newsreader), font version v26, 2025-09-08) | 5.3.0 | SIL OFL 1.1, `OFL-Newsreader.txt` |

The files were copied unchanged from the packages' `files/` folders
(`npm pack <package>`). SHA-256:

```text
2ee17598a98d8a59e4df8152d015bec9ab8e4d5672cc0ab42bef806b568e3971  instrument-sans-latin-wght-normal.woff2
77210cdde0281b5ecb0d592e063a98656f1bc36993a3b98f506eb91ff4a433a5  instrument-sans-latin-wght-italic.woff2
18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e  jetbrains-mono-latin-wght-normal.woff2
48bc8861b9b2ca9300747cad4fd6a3b4ac3028d364df00bd1b72097baa75e509  newsreader-latin-wght-italic.woff2
```

The social card text is outlined from the same Instrument Sans and
JetBrains Mono files (`website/brand/build_logo_sources.py`). The logo wordmark
is outlined from Outfit SemiBold, which is not served by the site: its file and
licence live in `website/brand/fonts/`.

## No layout shift while fonts load

`custom.css` defines metric-matched fallback faces (`Instrument Sans Fallback`,
`JetBrains Mono Fallback`, `Newsreader Fallback`) from local system fonts with
`size-adjust`, `ascent-override`, `descent-override` and `line-gap-override`
computed from these files:

| Fallback for | Local font | size-adjust | ascent | descent |
|---|---|---|---|---|
| Instrument Sans (avg. width 0.484 em, asc. 970, desc. 250 / 1000) | Arial / Helvetica / Liberation Sans (0.475 em) | 101.9% | 95.2% | 24.5% |
| JetBrains Mono (0.600 em, 1020 / 300) | Courier New / Liberation Mono (0.600 em) | 100% | 102% | 30% |
| Newsreader Italic (0.424 em, 1470 / 530 per 2000) | Times New Roman Italic (0.430 em) | 98.5% | 74.6% | 26.9% |

Arial and Times appear only as invisible metric fallbacks; they are never the
design face.

## Updating

```bash
npm pack @fontsource-variable/instrument-sans   # etc.
tar xzf fontsource-variable-instrument-sans-*.tgz
cp package/files/instrument-sans-latin-wght-normal.woff2 website/static/fonts/
```

Then update the versions and hashes above, check the fallback metrics still
match (`fontTools`: `hhea.ascent/descent`, average advance width), and rebuild
the logo sources if the wordmark should follow.
