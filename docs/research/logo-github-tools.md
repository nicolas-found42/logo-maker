# GitHub / Awesome-list tools for a creative local logo workflow

Scope: open-source, locally runnable (macOS arm64, Python 3 + uv / Node + Bun / Homebrew,
no API keys assumed) tools that help produce a more creative logo: programmatic
SVG, glyph-outline work, boolean path ops, raster→vector, SVG raster/optimize, and permissive
icon/font assets. Output must be PNG (SVG master preferred), commercially usable.
Metadata (stars / pushed_at / license) via `gh api repos/<owner>/<repo>` and `gh search repos`
on 2026-11-09/10; where GitHub reports `NOASSERTION` the LICENSE file text was read directly.

Note on "abandoned": flagged when `pushed_at` is 3+ years before 2026-11 (i.e. before
2023-11). GitHub mirror staleness (Inkscape, Potrace) is noted separately from the upstream project.

## 1. Programmatic SVG generation (Python / JS)

- **svgwrite** (`mozman/svgwrite`, https://github.com/mozman/svgwrite) — Python SVG authoring
  library (paths, gradients, text). Stars 577, pushed 2024-02-24. LICENSE.TXT is MIT text
  (https://github.com/mozman/svgwrite/blob/master/LICENSE.TXT). `uv pip install svgwrite`.
  Maintenance is intermittent ([INFERENCE] from push gap) but the API is stable for logo work.
- **drawsvg** (`cduck/drawsvg`, https://github.com/cduck/drawsvg) — modern Python SVG builder,
  MIT, stars 696, pushed 2026-10-29. `uv pip install drawsvg`. Good for parameterized marks.
- **svgpathtools** (`mathandy/svgpathtools`, https://github.com/mathandy/svgpathtools) — parse /
  manipulate SVG paths (Bezier sampling, splitting, bounding boxes), MIT, stars 641, pushed
  2026-10-07. `uv pip install svgpathtools`. Pairs with fonttools output.
- **svglib** (`deeplook/svglib`, https://github.com/deeplook/svglib) — read SVG into Python
  objects, LGPL-3.0, stars 371, pushed 2026-11-09. `uv pip install svglib`. Note LGPL (weaker
  for closed commercial bundling than MIT; output SVGs are unaffected, the library is).
- **paper.js** (`paperjs/paper.js`, https://github.com/paperjs/paper.js) — vector scripting
  (paths, boolean ops, gradients, SVG import/export). Stars 15,192, pushed 2026-11-06.
  GitHub says `NOASSERTION` but LICENSE.txt is the MIT License
  (https://github.com/paperjs/paper.js/blob/develop/LICENSE.txt). `npm i paper`.
- **p5.js** (`processing/p5.js`, https://github.com/processing/p5.js) — creative-coding sketches
  with SVG export add-on. LGPL-2.1, stars 24,327, pushed 2026-11-09. `npm i p5`.
- **two.js** (`jonobr1/two.js`, https://github.com/jonobr1/two.js) — renderer-agnostic 2D canvas/
  SVG API. MIT, stars 8,703, pushed 2026-11-10. `npm i two.js`.
- **rough.js** (`rough-stuff/rough`, https://github.com/rough-stuff/rough) — hand-drawn/sketchy
  SVG style on top of generated shapes. MIT, stars 21,370, pushed 2024-07-28. `npm i roughjs`.
  Useful contrast to overly plain geometric marks; pair with a serif wordmark.
- **svg.js** (`svgdotjs/svg.js`, https://github.com/svgdotjs/svg.js) — DOM SVG library.
  `NOASSERTION` on GitHub, but LICENSE.txt is MIT
  (https://github.com/svgdotjs/svg.js/blob/master/LICENSE.txt). Stars 11,911, pushed
  2026-08-04. `npm i @svgdotjs/svg.js`.
- **D3** (`d3/d3`, https://github.com/d3/d3) — data-driven documents; its line/curve generators
  are handy for generative marks. ISC, stars 113,892, pushed 2026-11-03. `npm i d3`.
- **SVG Path Editor** (`Yqnn/svg-path-editor`, https://github.com/Yqnn/svg-path-editor) —
  browser SVG path editor (Apache-2.0, stars 5,347, pushed 2026-11-03). Runs locally via a
  static server; install is `git clone` + open `index.html` (no build). Good for hand-tuning
  Bezier marks produced by code.

## 2. Font glyph outline extraction & text-to-path

- **fonttools** (`fonttools/fonttools`, https://github.com/fonttools/fonttools) — the standard
  for TTF/OTF/WOFF manipulation: glyph outlines (Pen / GlyphRecorder), subsetting, merging.
  MIT, stars 5,314, pushed 2026-11-05. `uv pip install fonttools`. The right tool to turn
  serif / sans-serif font letters into outlined paths so the logo does not depend on font
  availability. Fetch the fonts from https://github.com/google/fonts (OFL-1.1 fonts; repo
  pushed 2026-11-10) or Fontsource (`fontsource/fontsource`, MIT, pushed 2026-11-09).
- **opentype.js** (`opentypejs/opentype.js`, https://github.com/opentypejs/opentype.js) — JS
  equivalent: read fonts, get glyph paths as SVG path data. MIT, stars 5,045, pushed
  2026-08-08. `npm i opentype.js`.
- **google-font-to-svg-path** (`danmarshall/google-font-to-svg-path`,
  https://github.com/danmarshall/google-font-to-svg-path) — ready-made font → SVG path tool.
  MIT, stars 910, pushed 2026-11-02. `git clone` + run its Node script (no npm install needed
  beyond its deps).
- **text-to-svg** (`shrhdk/text-to-svg`, https://github.com/shrhdk/text-to-svg) — text → SVG
  paths in Node. LICENSE is MIT text (verified at `LICENSE` in repo root), stars 1,011,
  pushed 2023-09-26. `npm i text-to-svg`. Slightly stale push but stable.
- **svg-text-to-path** (`paulzi/svg-text-to-path`, https://github.com/paulzi/svg-text-to-path)
  — small text-to-path helper, no SPDX license in repo (license field: unknown), stars 144,
  pushed 2025-11-16. `npm i svg-text-to-path` [INFERENCE on package name from repo]. Treat
  license as unverified — prefer text-to-svg / opentype.js above.

## 3. Boolean path operations

- **skia-pathops** (`fonttools/skia-pathops`, https://github.com/fonttools/skia-pathops) —
  Skia path boolean ops (union/intersect/difference) as a Python package, BSD-3-Clause,
  stars 60, pushed 2026-02-16. `uv pip install skia-pathops`. Ideal for merging glyph
  outlines with custom shapes (e.g. a wave cut into a letterform).
- **Clipper2** (`AngusJohnson/Clipper2`, https://github.com/AngusJohnson/Clipper2) — mature
  polygon clipping/offsetting (C++), Boost Software License 1.0, stars 2,517, pushed
  2026-10-28. Install via `git clone` + CMake build (or use its Python bindings if present).
  Stronger than paper.js booleans for crisp logo geometry.
- **paper.js booleans** (above) — easiest boolean API if already in JS.

## 4. Raster → vector

- **vtracer** (`visioncortex/vtracer`, https://github.com/visioncortex/vtracer) — Rust raster→SVG
  converter, MIT, stars 7,495, pushed 2026-11-10. `brew install vtracer`. Best local option
  for tracing a hand sketch / photo of a mark into a clean SVG.
- **Potrace** — classic bitmap→EPS/SVG tracer, GPL-2.0-or-later (see
  https://en.wikipedia.org/wiki/Potrace and http://potrace.sourceforge.net). `brew install
  potrace`. No maintained GitHub repo (mirrors are stale/abandoned flag); install via
  Homebrew from upstream. GPL applies to the tool, not to traced output [INFERENCE — check
  with a lawyer if unsure; typically output is not encumbered].

## 5. SVG rasterizers / converters and optimizers

- **resvg** (`linebender/resvg`, https://github.com/linebender/resvg) — Rust SVG renderer
  (note: moved from RazrFalcon/resvg to linebender/resvg). Apache-2.0, stars 4,179, pushed
  2026-11-09. `cargo install resvg` or `brew install resvg`. Fast, headless PNG export.
- **CairoSVG** (`Kozea/CairoSVG`, https://github.com/Kozea/CairoSVG) — Python SVG→PNG/PDF,
  LGPL-3.0, stars 957, pushed 2026-09-07. `uv pip install cairosvg`.
- **librsvg** (`GNOME/librsvg`, https://github.com/GNOME/librsvg) — C SVG render library,
  LGPL-2.1, stars 411, pushed 2026-11-06. `brew install librsvg` (provides `rsvg-convert`).
- **SVGO** (`svg/svgo`, https://github.com/svg/svgo) — SVG optimizer (shrinks paths, removes
  editor cruft). MIT, stars 22,803, pushed 2026-11-08. `npm i -g svgo`. Always run before
  finalizing the master SVG.
- **Pillow** (`python-pillow/Pillow`, https://github.com/python-pillow/Pillow) — raster
  imaging (resize, pad, export PNG variants). License is the HPND-style Pillow license
  (LICENSE file text; GitHub `NOASSERTION`). Stars 13,975, pushed 2026-11-10.
  `uv pip install Pillow`.
- **ImageMagick** (`ImageMagick/ImageMagick`, https://github.com/ImageMagick/ImageMagick) —
  general raster conversion. GitHub `NOASSERTION`; LICENSE is the ImageMagick License
  (Apache-2.0-derived). Stars 17,828, pushed 2026-11-10. `brew install imagemagick`.
- **Inkscape** (`inkscape/inkscape`, https://github.com/inkscape/inkscape) — full SVG editor,
  GPL-2.0-or-later. Stars 4,108; the GitHub mirror's last push is 2022-03-03 (abandoned-flag
  applies to the *mirror*, upstream is at inkscape.org). `brew install inkscape`. Only
  needed if hand-editing beats code generation.

## 6. Permissive icon sets usable inside a logo

All below are icon *assets* (SVG files) — embedding and recoloring them in a commercial logo
is allowed by their licenses (verify trademark/attribution practice for the final mark).

- **Lucide** (`lucide-icons/lucide`, https://github.com/lucide-icons/lucide) — 2,000+ icons.
  GitHub `NOASSERTION`; LICENSE file is ISC (https://github.com/lucide-icons/lucide/blob/main/LICENSE).
  Stars 25,671, pushed 2026-11-09. `npm i lucide-static` (or clone for raw SVGs).
- **Tabler Icons** (`tabler/tabler-icons`, https://github.com/tabler/tabler-icons) — 6,200+
  MIT icons. Stars 22,594, pushed 2026-11-08. `git clone` the repo for SVGs.
- **Phosphor** (`phosphor-icons/core`, https://github.com/phosphor-icons/core) — MIT icon
  system (web repo: `phosphor-icons/web`, MIT). Core stars 399, pushed 2026-01-06.
- **Heroicons** (`tailwindlabs/heroicons`, https://github.com/tailwindlabs/heroicons) — MIT,
  stars 23,905, pushed 2026-05-12. MIT text in repo root.
- **Iconoir** (`iconoir-icons/iconoir`, https://github.com/iconoir-icons/iconoir) — MIT,
  stars 4,631, pushed 2026-11-04.
- **Material Symbols** (`google/material-design-icons`, https://github.com/google/material-design-icons)
  — Apache-2.0, stars 54,262, pushed 2026-10-23.

## 7. Awesome lists (discovery, not tools)

- **Awesome SVG** (`willianjusten/awesome-svg`, https://github.com/willianjusten/awesome-svg)
  — curated SVG list, stars 4,663, pushed 2026-07-16, no SPDX license in repo.
- **Awesome Design Tools** (`goabstract/Awesome-Design-Tools`,
  https://github.com/goabstract/Awesome-Design-Tools) — MIT, stars 41,822, pushed
  2024-07-28. Broad tool directory; cross-check staleness per entry.
- **Awesome Creative Coding** (`terkelg/awesome-creative-coding`,
  https://github.com/terkelg/awesome-creative-coding) — stars 15,570, pushed 2026-07-21,
  no SPDX license. Generative-art libraries (p5, two.js, paper.js all listed).
- **Awesome Fonts** (`brabadu/awesome-fonts`, https://github.com/brabadu/awesome-fonts) —
  stars 2,102, pushed 2026-10-31, no SPDX license.
- **Awesome Generative Art** (`kosmos/awesome-generative-art`,
  https://github.com/kosmos/awesome-generative-art) — stars 1,855, pushed 2024-06-04,
  no SPDX license.
- Keenable search also surfaced **Lumo** (`Rajpolu/Lumo`,
  https://github.com/Rajpolu/Lumo) — a Next.js/React logo-creation app using Lucide icons,
  30+ fonts, multi-format export. No license file in repo (license: unknown), stars 0-11
  range, pushed 2025-08-30. Treat as inspiration, not a dependency, and do not copy its
  code without a license.

## 8. Recommended local pipeline

1. Generate mark variants with **drawsvg** or **paper.js** (or p5/two.js for generative
   exploration); convert serif / sans-serif font glyphs with **fonttools** (Python) or
   **opentype.js** (Node) so text becomes paths.
2. Merge/cut shapes with **skia-pathops** (Python) or **Clipper2**; borrow a base motif from
   **Lucide / Tabler / Phosphor** (MIT/ISC) and redraw it rather than using it verbatim.
3. Trace any hand sketch with **vtracer**; optimize with **svgo**.
4. Export the PNG with **resvg** (or CairoSVG/librsvg); make favicon/PNG sizes with Pillow.

Strongest, lowest-friction picks: drawsvg + fonttools + skia-pathops (all `uv pip install`)
for the master SVG, svgo to clean it, resvg for PNG — everything MIT/BSD/Apache and active in
2026. Avoid Potrace/Inkscape GPL where a MIT alternative exists, unless you specifically want
their features.
