# Logo tool research — GitHub topics sweep (`github-topics`)

Primary sources: `gh search repos --topic` (22 topics: logo, logo-generator, logo-design,
monogram, svg-generator, generative-art, lettering, typography, variable-fonts, font-tools,
glyph, vector-graphics, svg-filters, halftone, risograph, hand-drawn, sketchy,
perfect-freehand, shape-morphing, blob, isometric, favicon), `gh search repos` keyword
sweeps (hershey font, fontra, fontforge, fontFeatures, vpype, flubber, favicon generator,
svg blob generator, halftone svg, glyphsLib…), `gh api repos/<o>/<r>` for stars/license/
pushed_at (verified 2026-11-10), Keenable web search for named repos. Names already found
in earlier sweeps were excluded (paper.js, rough.js, fonttools, opentype.js, svgpathtools,
p5.js, two.js, SVGO…).

Filter applied: permissive license, scriptable (CLI/library), active, macOS-compatible.

## Strongest chainable pipeline for a logo mark

```text
brief/seed ──sigilgen──▶ flat SVG monogram candidates ──┬─▶ perfect-freehand ──┐
     │                                                   ├─▶ svg2roughjs ──────┤
     │                                                   └─▶ flubber ─────────┤
text/wordmark ──hershey/shxparser/single-line renderer──▶ stroke polylines ──┤
opentype.js paths (already found) ──glyph outlines────────▶ outline SVG ─────┤
                                                                             ▼
                                   vpype  read→linemerge→linesort→write ──▶ optimized multi-layer SVG
                                                                        ├─▶ halftone / triangula / color-separation (texture + riso layers)
                                                                        ├─▶ fontFeatures + fea-proof (ligatures on a serif variable font)
                                                                        ├─▶ fontforge (batch convert/subset/autotrace)
                                                                        └─▶ favicons + pwa-asset-generator (final packaging)
```

## Headline finds

- **perfect-freehand** (`steveruizok/perfect-freehand`, MIT, 5808★, pushed 2026-04-13) —
  `getStroke(points, {size, thinning})` turns centerlines into pressure-sensitive filled
  SVG strokes. The hand-drawn lettering engine; accepts any point list, so Hershey glyph
  polylines or traced outlines become calligraphic lettering in one call.
  Evidence: https://github.com/steveruizok/perfect-freehand/blob/main/README.md
- **vpype** (`abey79/vpype`, MIT, 983★, 2026-11-01) — pipelined vector CLI
  (`vpype read in.svg linemerge linesort write out.svg`), generative commands, multi-layer
  SVG/HPGL. The chain hub between every effect below.
  Evidence: https://github.com/abey79/vpype/blob/master/README.md
- **flubber** (`veltman/flubber`, MIT, 6963★) — best-guess interpolation between any two
  SVG shapes (morph monogram variants, sample animation frames). ⚠ STALE: last push
  2022-11-08 (3+ years); zero-dep and stable, but pin the version.
  Evidence: https://github.com/veltman/flubber/blob/master/README.md
- **fontra** (`fontra/fontra`, GPL-3.0, 856★, 2026-11-04) — browser-based parametric
  variable-font editor (Python server + JS client). Design bespoke ligature glyphs on
  an axis; outputs are normal font sources. Also `fontra/fontra-compile` (Variable Font
  compiler) for the compile step. Evidence: https://github.com/fontra/fontra/blob/main/README.md
- **fontforge** (`fontforge/fontforge`, BSD-3-Clause — GitHub reports NOASSERTION because
  LICENSE mixes texts, 8069★, 2026-11-09) — `brew install fontforge` (verified arm64
  bottled 20251009). Headless `fontforge -script` for batch convert/subset/autotrace.
  Evidence: https://github.com/fontforge/fontforge
- **fontFeatures** (`simoncozens/fontFeatures`, BSD-3-Clause, 82★) — Python API for
  OpenType feature code (ligatures, calts, stylistic sets) applied to a font;
  **fea-proof** (`typedev/fea-proof`) visually proves features on real words before lockup.
- **Hershey / single-line stack** — `kamalmostafa/hershey-fonts` (⚠ STALE 2018, GPL-2.0
  software), `tatarize/shxparser` (MIT, pure-Python SHX parser), `jvolker/single-line-
  font-renderer` (MIT, text→SVG stroke), `golanlevin/p5-single-line-font-resources`
  (no license file — archive, check provenance). Together: text → monoline glyph paths →
  perfect-freehand/rough/vpype effects.
- **Sketchy stack** — `rough-stuff/rough-notation` (MIT, 9735★), `fskpf/svg2roughjs`
  (MIT, 220★, 2026-06-12): re-draw a clean SVG mark hand-drawn in one call.
- **Deterministic logo generators** — `xianshi3/sigilgen` (MIT, JSON→flat SVG, seedable
  candidate contact sheets), `mcpware/logoloom` (MIT, MCP-native logo→SVG→brand kit),
  `joeseverino/branding-engine` (MIT, monogram+color→favicons/wordmarks kit),
  `bankenichi/Monogram-Logo-Generator` (MIT, client-side monogram layouts).
- **Riso/halftone** — `hafacc/color-separation` (MIT, riso spot-color layers in a custom
  palette), `adambarla/halftone` (MIT, image→halftone dot SVG), `rh12503/triangula`
  (MIT, 3875★, low-poly faceting).
- **Packaging** — `itgalaxy/favicons` (MIT, 1239★) and `elegantapp/pwa-asset-generator`
  (MIT, 3043★): SVG master → full favicon/PWA suite in one command.

- `airyland/logo.surf` — CC BY-NC 4.0 (non-commercial; fails permissive filter).
- `antiboredom/p5.riso` — Anti-Capitalist License (non-permissive); `hafacc/color-separation`
  covers riso separations permissively.
- `googlefonts/fontra` — archived mirror; live repo is `fontra/fontra`.
- AI image/video topic hits (InvokeAI, EasyDiffusion, SD.Next…) — image-gen APIs, out of
  scope.

## Stale repos flagged (no push 3+ years)

- `kamalmostafa/hershey-fonts` (2018-01-01), `poletaevvlad/svg-filter-editor` (2020-07-02),
  `veltman/flubber` (2022-11-08), `luukdv/gooey-react` (2023-02-03),
  `bigbluebutton/perfect-freehand-python` (2023-04-26), `nghiepdev/react-svg-blob` (2023-10-22).
  All still usable as stable/dataset/tooling; pins recommended.
