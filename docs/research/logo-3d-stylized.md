# Stylized / non-photoreal 3D for a logo mark — research

Test subject: a disc with a raised rim and a raised serif letterform (static Black-weight instance of a variable serif font, produced as in `logo-3d.md`); generic palette (blue face, light background, dark ink outline). This file covers **stylized** tools only (toon/cel, line art, postprocessing, HLR 3D→SVG, isometric, paper-cut). Photoreal/CAD/AI-generation families are covered in `logo-3d.md`. Primary sources only; live probes below were run on this Mac (macOS arm64) with no system-wide installs.

## Verdict up front

**Two proven stylized chains (both rendered the letterform on this machine):**
1. **Blender toon + Line Art (best stills):** `bpy` 5.2.3 → FONT letterform (extrude/bevel) → `ShaderNodeBsdfToon` blue + Principled torus rim → Grease Pencil `LINEART` modifier (OBJECT source = letterform curve, camera = render camera) → EEVEE PNG. Line Art added real strokes (1,779 px differ from toon-only, deterministic). **Baked SVG export is the open gap:** `lineart_bake_strokes` + `wm.grease_pencil_export_svg` ran headless but produced 0 strokes / 471 B empty SVG — vector needs a GUI bake, or the `build123d project_to_viewport` / `ln` fallback.
2. **three.js toon + ink outline + SVG (best web/vector):** `opentype.js` glyph → `THREE.Shape` → `ExtrudeGeometry` → `MeshToonMaterial` (blue) + torus rim → `EffectComposer` + `OutlinePass` (dark ink outline) → headless **system Chrome 157** (`--headless --enable-unsafe-swiftshader`, localhost HTTP) screenshot **and** `SVGRenderer` vector export from the same scene. Center pixel `(29,72,118)` = the material's base color, corner pixel = the light background color, 52,842 pure-black outline pixels. No browser download needed.

**Recommended production chain:** Toon BSDF (Blender) for hero stills + Line Art PNG outlines → hand-inked SVG master derived from flat vector (never auto-baked headless); three.js `MeshToonMaterial` + `postprocessing` `OutlineEffect` for interactive web; `fogleman/ln` (or Rust `larnt`) for true hidden-line SVG from the CAD letterform. Paper-cut via `Diastasis` layer separation after the flat master exists.

## 1. Blender stylized (in-wheel, proven)

**Toon BSDF** — `ShaderNodeBsdfToon` (inputs Color/Size/Smooth/Normal/Weight; the classic ShaderToRGB+ColorRamp recipe is superseded). Probe: `/tmp/logo3d-stylized/toon_probe.py` → `/tmp/logo3d-stylized/toon_glyph.png` (900×900 RGBA, ~1 s, EEVEE). Source: [Toon BSDF manual](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/bsdf_toon.html).

**Line Art modifier** — `GreasePencilLineartModifier` (`modifiers.new(name, 'LINEART')` on a Grease Pencil object; Source Type Scene/Collection/Object; Silhouette/Crease/Contour edge types; Line Radius/Opacity; Bake/Clear operators). Manual: [Line Art Modifier](https://docs.blender.org/manual/en/latest/grease_pencil/modifiers/generate/line_art.html). Probe: OBJECT source with `source_object` = letterform curve and `source_camera` = active camera; render diff vs toon-only = **1,779 px** (toon-vs-toon re-render = 0 px, so strokes are real). **Gap:** SCENE source also baked 0 strokes; `lineart_bake_strokes` headless produced an empty drawing, and `wm.grease_pencil_export_svg` (note: *not* `gpencil_export_svg`) wrote a 471 B empty-frame SVG. Fix path: GUI bake → SVG, or accept PNG line art + manual SVG. Freestyle is the legacy alternative but its SVG addon (`render_freestyle_svg`) is missing from the pip wheel (prior probe) — needs standalone Blender.app install (permission step).

## 2. three.js stylized (proven in system Chrome)

- **MeshToonMaterial** + optional `gradientMap` banding — probed (see §6).
- **OutlinePass** (stock) — probed; **pmndrs/postprocessing** `OutlineEffect`/`BloomEffect` merged in one `EffectPass` is the production pick (Zlib, 2,963★) [repo](https://github.com/pmndrs/postprocessing).
- **UnrealBloomPass** / pmndrs `BloomEffect` — rim glow only, high threshold.
- **N8AO** (CC0, 504★) — `N8AOPass` replaces `RenderPass`; subtle `intensity ~2` grounds the badge. Needs `postprocessing` peer + SMAA.
- **MeshPhysicalMaterial transmission** — clearcoat preferred over glass; each transmissive object = extra scene pass.
- **SVGRenderer** — probed: exported `<svg …><path d="M…">` vector from the same extruded letterform (file `/tmp/logo3d-stylized/web/three_glyph.svg`, 2.0 KB, truncated paths viewBox — geometry is triangulated, not type outlines; use for line-art proof, not as the master).
- **drei Text3D / MeshTransmissionMaterial** and **R3F** — declarative web variants (Text3D needs `typeface.json`; our probe skipped it via raw opentype.js). **Babylon.js** `CreateText` + **Babylon.Font** (WASM TTF) + **meshwriter-cudu** — engine fallbacks; latter two are 49★/1★ with unverified traction — avoid. **PlayCanvas** TextElement is MSDF quads (not extruded type) — wrong tool. **Filament Web** (WASM PBR) — photoreal-first, no toon story — avoid.

## 3. Headless WebGL on macOS without downloading browsers

System state: `/Applications/Google Chrome.app` (**157.0.8103.40**) and `Safari.app` present; Blender.app also present. Proven recipe (probe §6): serve the scene over `http://127.0.0.1` (file:// module CORS blocks imports) and run `Google Chrome --headless --no-sandbox --enable-unsafe-swiftshader --virtual-time-budget=12000 --screenshot=…`. Gotchas observed: `--disable-gpu` **blanks WebGL entirely** (4,632 B blank PNG); camera `far` (100) clipped a 460-unit-distant scene — set `far 2000`; opentype.js must load as a classic script (`dist/opentype.min.js`) not a bare ESM import. **Puppeteer Core** (`executablePath` → system Chrome, no download) or **Playwright Core** (`channel:'chrome'`) add deterministic `waitForSelector` capture — install the *core* packages only; full `puppeteer`/`playwright` would download browsers. **headless-gl** (pure Node) is fragile on arm64 — not probed, avoid. **Safari/safaridriver** — WebKit parity checks only.

## 4. 3D → SVG / hidden-line removal

- **fogleman/ln** (Go, MIT, 3,510★, stale 2019 but stable): vector renderer, OBJ/STL in, SVG/PNG out, ray-tested HLR. Feed `build123d` C STL → true line-art SVG. Needs Go toolchain (permission).
- **HellOwhatAs/larnt** (Rust, MIT, 38★): ln rewrite; this repo is Rust, so `cargo install` may be cheapest — verify HLR quality first.
- **aweary/ln.js** + **mariuswatz/stl-to-svg** (browser HLR UI): license unverified, GUI-only — reference only.
- **three SVGRenderer** — probed (triangulated paths; proof-of-concept vector, not a type master).
- **Blender Line Art → SVG** — headless bake gap (§1); GUI bake unprobed.
- **build123d `project_to_viewport`** (covered set) remains the most reliable scriptable HLR SVG — pair with any toon material render.

## 5. Isometric & paper-cut

Isometric SVG (programmatic): **elchininet/isometric** (TS, Apache-2.0, 244★, active) — face primitives for a disc underlay; **iso-topology** (Go binary, Apache-2.0, 73★) for architecture/system diagrams; GUI tools (isometric-compiler-ui, isometricks GPL, isometric-voxel 1★) — skip for the pipeline. Paper-cut: **Diastasis** (Python CLI, MIT, 5★) — separate the flat SVG master into registered cut layers headlessly; **topo-layers** (browser, license unverified) is technique reference for layer slicing + 3D stack preview. Workflow: flat SVG master → Diastasis layers → stacked paper-cut letterform with a base-color face layer + an accent rim layer.

## 6. Probe log (observed on this Mac, `/tmp/logo3d-stylized/`)

| Probe | Command | Observed result |
|---|---|---|
| Blender toon | `/tmp/logo3d/venv-bpy/bin/python toon_probe.py` (BsdfToon + accent torus + Sun, EEVEE) | `toon_glyph.png` 900×900 RGBA 274 KB, ~0.8 s; deterministic (toon-vs-toon diff 0 px) |
| Blender Line Art | `lineart2.py` (GP `LINEART`, OBJECT source) | `lineart_glyph.png` differs from toon-only by **1,779 px** (strokes confirmed) |
| Line Art SVG | `lineart3.py`/`lineart4.py` (`lineart_bake_strokes` + `wm.grease_pencil_export_svg`) | **0 strokes** baked headless; SVG 471 B empty — documented limitation, not success |
| three toon+outline | Chrome headless + `web/scene.html` (MeshToonMaterial + OutlinePass + SVGRenderer) | `toon_three.png` 900×900 35 KB; center `(29,72,118)` = material base color, corner `(248,246,241)` = light background, 52,842 black outline px; `three_glyph.svg` 2.0 KB with `<path>` data |
| Browser inventory | `ls /Applications`, `Google Chrome --version` | Chrome 157.0.8103.40 + Safari.app + Blender.app present; no downloads made |

**Files:** `/tmp/logo3d-stylized/toon_glyph.png`, `lineart_glyph.png`, `lineart_glyph.svg` (empty shell — see above), `three_toon_glyph.png`, `web/three_glyph.svg`, `web/toon_three.png`, scripts `toon_probe.py`, `lineart{2,3,4}.py`, `web/scene.html`, `web/mini.html`.

## 7. Recommendation + permissions

**Ship chain:** flat SVG master (source of truth) → Blender Toon BSDF + Line Art PNG for hero/social → three.js MeshToonMaterial+OutlineEffect via Puppeteer Core (system Chrome) for web moments → `ln`/`larnt` or `build123d` projection for HLR SVG → Diastasis for paper-cut. **Needs user permission (not done):** (a) standalone Blender.app for Freestyle/Line-Art GUI bake SVG (pip wheel gap); (b) Go or Rust toolchain for `ln`/`larnt` if HLR SVG is wanted scriptably; (c) any AI generation — out of scope and wrong for a type-driven mark.
