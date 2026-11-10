# Logo — Awesome-mined chainable tools (logo-awesome-mined)

Slug: `awesome-mined`. Sources: GitHub awesome lists — terkelg/awesome-creative-coding, kosmos/awesome-generative-art, willianjusten/awesome-svg (topics/Libraries, Filters, Patterns, Gradients), goabstract/Awesome-Design-Tools (mirrors LisaDziuba/Awesome-Design-Tools), Jolg42/awesome-typography, brabadu/awesome-fonts, agmmnn/awesome-blender, ishaan95/awesome-procedural-generation, codecreative/awesome-pen-plotter-resources + msurguy/awesome-drawing-robots lineage (fogleman/axi, abey79/vpype). Metadata via `gh api repos/<o>/<r>` (stars, license, pushed_at) and Keenable `search_web_pages` / `fetch_page_content`. Companion structured file: `assignments/research/logo-awesome-mined.jsonl` (39 rows).

Brand context: "Chief of Staff" private AI workspace (remembers meetings; owner reviews next steps). Colors #1E4A7A, #2F6B4F, #B45309, #F2C14E, #F8F6F1, #16232E; Playfair Display + Open Sans. Env: macOS arm64, 48GB, Python+uv, Node+Bun, Homebrew. Overlap with `logo-github-tools.jsonl` / `logo-ai-generation.jsonl` / `logo-concepts.jsonl` was excluded (svgwrite, drawsvg, paper.js, p5.js, two.js, rough.js, D3, vtracer, resvg, SVGO, fonttools, opentype.js, vtracer, etc. are not repeated).

## 1. Procedural / generative vector geometry

- canvas-sketch (mattdesl/canvas-sketch) — MIT, 5324★, pushed 2026-06-02. JS generative framework (params/seed → SVG/PNG). From awesome-creative-coding. Use for randomized layout families around a fixed CS monogram.
- Maker.js (microsoft/maker.js) — Apache-2.0, 2049★, 2026-10-29. Code-defined vector CAD → SVG/DXF. From awesome-svg Libraries. Precise compass/baton geometry.
- Lygia (patriciogonzalezvivo/lygia) — 3483★, 2026-10-24. GLSL/HLSL/WGSL shader library. From awesome-creative-coding. Prototype grain/moiré then rebuild as SVG filter/pattern.
- Konstrukt (MarcelMue/konstrukt) — MIT, 68★, 2024-06-17. CLI scalable pattern SVGs. From awesome-creative-coding. Low-contrast background tiles.
- fogleman/gg — MIT, 4797★, 2023-12-14. Go 2D graphics. Headless generator without browser loop.
- fogleman/primitive — MIT, 13592★, 2024-07-22. Image → geometric primitives (Mop art). Abstract a check/ledger idea into few shapes.

## 2. Hand-drawn / plotter line styles

- vpype (abey79/vpype) — MIT, 983★, 2026-11-01. CLI vector processor (trim/reorder/pin). Strongest chain hub: insert after any generator before final SVG.
- fogleman/axi — MIT, 284★, 2020-02-29. FLAG: no push 6+ years. AxiDraw library; use as API reference, emit SVG only.
- p5-hershey-js (LingDong-/p5-hershey-js) — MIT, 65★, 2020-06-05. FLAG: stale 6y. Single-stroke glyphs for CS variants.
- p5-single-line-font-resources (golanlevin) — 284★, 2026-10-15. 150+ monoline fonts (Keenable-verified authoritative archive). Pair with vpype.
- perfect-freehand (steveruizok) — MIT, 5808★, 2026-04-13. Pressure strokes → outline SVG. Blueprint hand-drawn baton/check.
- linedraw (LingDong-) — MIT, 878★, 2023-07-22. FLAG: 3+ years. Flow-field raster → SVG lines. From awesome-pen-plotter-resources.
- skeleton-tracing — MIT, 607★, 2022-07-21. FLAG: 4y. Centerline SVG. From awesome-pen-plotter-resources.
- fishdraw — MIT, 2535★, 2021-09-08. FLAG: 5y. Procedural strokes reference. From awesome-pen-plotter-resources.
- ZebraTrace (maxim-s-barabash) — GPL-3.0, 158★, 2023-11-20. Woodcut/guilloche/halftone bitmap → vector. Engraved texture for mark.
- guilloche (binarymax) — 47★, 2018-02-12. FLAG: abandoned + license unknown. Rosette fill reference only.
- Snap.svg (adobe-webplatform/Snap.svg) — Apache-2.0, 14001★, 2026-10-22 (Keenable-verified npmsvg). From awesome-svg Libraries. Interactive SVG generation.
- Vivus (maxwellito) — MIT, 15479★, 2022-07-06. Path draw-on sequencing. Logo reveal previews / plotter order.
- Walkway (ConnorAtherton) — MIT, 4336★, 2022-03-13. Underscore/draw timing. Audition monoline passes.

## 3. SVG filters / texture

- textures.js (riccardoscalco/textures) — MIT, 6088★, 2023-01-01. D3 SVG fills. From awesome-svg Patterns. Paper/engraving fills for logo shapes.
- svg-patterns (derhuerst) — ISC, 222★, 2022-05-22. Programmatic <pattern>. From awesome-svg Patterns. Chain before textures.js.
- trianglify (qrohlf/trianglify) — GPL-3.0, 10087★, 2025-05-12. Seed + palette → Delaunay triangle SVG. From awesome-svg Patterns. LOW-CONTRAST background only.
- Lygia (above) doubles as filter/texture prototyping via shaders.

## 4. Shape morphing

- flubber (veltman/flubber) — MIT, 6963★, 2022-11-08 (Keenable-verified). Two SVG paths → interpolator(t) → in-between paths. Morph C↔S, baton↔check; sample t=0.5 frames as explorations. Alternative note: notoriousb1t/polymorph (6kb MIT) if bundle size matters.

## 5. Color palette generation (OKLCH)

- culori (Evercoder/culori) — MIT, 1253★, 2026-11-04 (Keenable-verified). OKLCH/OKLab, interpolation, toGamut, diff. PRIMARY engine for brand ramps from the six hexes.
- chroma.js (gka/chroma.js) — NOASSERTION, 10601★, 2026-10-24. Scales/interpolation. Lightweight companion.
- color.js (color-js/color.js) — MIT, 2319★, 2026-11-09. CSS Color 4 spec converter. Verify sRGB/print gamut.
- Leonardo (adobe/leonardo) — Apache-2.0, 2165★, 2026-07-08. Contrast-driven ramps. From Awesome-Design-Tools/Color. Accessible navy/green steps on #F8F6F1.

## 6. 3D-to-vector / emboss renders

- Blender (blender/blender) — 21827★, 2026-11-10 (GPL code). CLI `blender -b -P` → Freestyle/SVG/EPS. From awesome-blender. Emboss/deboss plates, toon lines.
- three.js SVGRenderer (mrdoob/three.js) — MIT, 117983★, 2026-11-10 (Keenable-verified docs: sharp SVG, no textures/shadows). 3×D scene → SVG projection. Low-poly emboss previews.
- OpenSCAD (openscad/openscad) — 10630★, 2026-11-10. `projection()` → SVG. Parametric extrusions for pill/engraving tests.
- CadQuery (CadQuery/cadquery) — 6083★, 2026-11-09. Python OCCT CAD → SVG. Fillet-quality badge/coin variants.
- build123d (gumyr/build123d) — Apache-2.0, 3677★, 2026-11-09. Builder/algebra CAD → SVG/STEP. Successor pattern to CadQuery.
- trimesh (mikedh/trimesh) — MIT, 3719★, 2026-11-09. Mesh slice/section → Path2D/SVG. OBJ emblem → flat logo contours.
- manifold (elalish/manifold) — Apache-2.0, 2400★, 2026-11-10. Watertight CSG. Baton/check union-subtract emboss prototypes.
- Seen (themadcreator/seen) — NOASSERTION, 876★, 2024-04-26. 3D vector + D3. Hidden-line/contour alternative to SVGRenderer. From awesome-svg Libraries.
- Sverchok (nortikin/sverchok) — GPL-3.0, 2557★, 2026-11-08. Node parametric meshes. From awesome-blender. Vault arch/harbor wave plates.
- Celtic Knot (BorisTheBrave/celtic-knot) — 88★, 2024-03-09. Mesh → Bezier weavings. Memory-loop/staff-knot braid; keep stroke count favicon-safe.

## 7. Pattern / tiling

- d3-delaunay (d3/d3-delaunay) — ISC, 666★, 2026-11-04. Points → Voronoi/Delaunay SVG. Tessellated fills seeded from logo geometry.
- SVGnest (Jack000/SVGnest) — MIT, 2616★, 2024-02-01. Pack parts into sheet. Favicon set / print-proof sheets. From awesome-svg Libraries.
- Konstrukt, trianglify, textures.js, svg-patterns, guilloche (above) complete the tiling chain.

## Strongest chainable stack (recommended order)

seed	params → culori/Leonardo brand ramp → canvas-sketch/Maker.js monogram family → perfect-freehand + Hershey stroke pass → vpype (reorder/simplify/gap-close) → textures.js/svg-patterns fill + flubber morph samples → Blender/CadQuery emboss plate + three.js SVGRenderer preview → SVGnest favicon sheet → SVGO (already found) final. Keep final wordmark vector-set in Playfair Display; raster/3D only for exploration and texture reference.

## Staleness flags (no push 3+ years)

fogleman/axi (2020), p5-hershey-js (2020), fishdraw (2021), skeleton-tracing (2022), guilloche (2018), linedraw (2023-07 borderline flag). All other rows pushed within 3 years of the 2026-11-10 pass.
