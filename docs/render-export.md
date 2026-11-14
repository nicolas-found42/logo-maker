# Rendering and export

Alternate renderers (mitsuba, luxcore, three.js), pixel QA (`checks.py`),
pixel post-ops (`imageops.py`), the export set (`export.py`), and tool notes the
generated [adapter registry](adapters.md) has no room for.

## Alternate renderers (`logo_maker/renderers/`)

The pipeline renders only Cycles: `render.render` refuses a scene whose `[render].renderer` is
mitsuba, luxcore or three (GPU-only policy). These modules are development tools called directly.

Each renderer implements `render(export_json, out_png, *, quality, resolution)`:
`quality` maps to alternate-renderer sample counts (`test` 64, `preview` 256, `final` 1024+),
`resolution` is the long edge in px, output is RGBA PNG, transparent when
`world.transparent`. `renderers.render(name, ...)` dispatches. Shared helpers
(`load_export`, `resolve`, `scaled_size`, `spp_for`) live in `__init__.py`.

- **mitsuba** (`mitsuba.py`): variant `metal_ad_rgb` → `llvm_ad_rgb` →
  `scalar_rgb`. Export materials → `principled` (`coat`/`coat_roughness` map
  to `clearcoat`/`clearcoat_gloss`; transmission → `spec_trans`/`eta`;
  subsurface folds into `sheen`; emission becomes a shape emitter). Area
  lights are emissive rectangles facing the target
  (radiance = power/area), point/sun are native. The sensor uses Mitsuba's
  own `look_at`. A background emitter forces opaque film alpha, so
  transparent renders **omit** the env emitter (HDRI applies to opaque
  renders only); direct lights still illuminate. Film `hdrfilm` rgba float32,
  converted to uint8 sRGB for PNG (alpha stays linear).
- **luxcore** (`luxcore.py`): renders in-process (`pyluxcore.Init()` per
  render; repeat renders in one interpreter work). Materials →
  `disney` (`clearcoatgloss` = 1 − coat_roughness; transmission/subsurface not
  mapped). Area/point lights
  become emissive world-space meshes (quad facing the target, icosphere
  ball); sun is a native `sun` source. Engine PATHCPU (set
  `LOGO_MAKER_LUXCORE_ENGINE=PATHOCL` to try OpenCL). Film
  `RGBA_IMAGEPIPELINE` (index 0) through `TONEMAP_LINEAR` + `GAMMA_CORRECTION
  2.2`, halted by `batch.haltspp` (`batch.halttime` 1200 s cap). LuxCore tests
  halt conditions only inside `RenderSession.UpdateStats()` (`Film::RunTests`),
  so the renderer polls `HasDone()` + `UpdateStats()`; a bare `WaitForDone()`
  never returns. Transparent backgrounds stay transparent
  because no background source is defined.
- **three** (`three.py` + `js/three-page.html` + `js/three-render.mjs`):
  serves the repo `js/` dir over local HTTP, stages a session dir with the
  glb plus a Y-up-converted `config.json`, and screenshots the page with
  Playwright (`channel: "chrome"`, SwiftShader fallback flags,
  `omitBackground`). Materials come from the glb; lighting is RoomEnvironment
  (or RGBELoader+PMREM HDRI for opaque renders) plus rect/point/directional
  lights mapped from the export. EffectComposer + N8AO (+ bloom for emissive
  scenes), plain WebGL as fallback. Session dir is removed after the render.

## Pixel QA (`logo_maker/checks.py`)

Pure functions over PNG paths; thresholds are module constants.

- `alpha_report`: veil = haze-level alpha (≤ `VEIL_ALPHA_MAX`) covering more
  than `VEIL_HAZE_FRACTION` of the background *outside the object body plus a
  halo zone* (`_veil_exclude_px`), so resampling halos do not count.
  Returns `veil`, `haze_fraction`, `min_bg_alpha`, `bbox`.
- `margin_report(png, min_margin=0.04)`: object bbox vs frame; `cut_off` when
  any margin is under the minimum.
- `color_report(png, palette)`: top-`N_DOMINANT` opaque colors (4-bit bins) in
  OKLab, deltaE2000 via coloraide; roles within `PRESENT_DE_MAX` are present.
- `edge_report`: boundary transitions that jump straight 0→255 (`HARD_JUMP`)
  vs graded steps; `aliased` when the hard fraction tops `ALIASED_FRACTION`.

## Pixel post-ops (`logo_maker/imageops.py`)

- `downsample(src, dst, size)`: long edge → `size`, OIIO lanczos3,
  premultiplied-alpha correct (premult → resize → unpremult).
- `pad_square`, `composite_on(png, color_hex, dst=None)`,
  `soft_shadow(png, opacity=0.26, blur=28, offset=(0,18))` → shadow sprite
  (Pillow); the caller pastes it shifted under the mark.

## Export set (`logo_maker/export.py`)

`export_all(concept_dir, out_dir, *, name, palette, motif_svg)` writes
exactly: `hero-transparent.png` (2000², veil/margin-checked, else
`ExportError`), `hero-paper.png` (paper bg + soft shadow 18 px below the mark), `avatar-1024.png`
(bbox fit to 88% of the inscribed circle, on bg; a mark spanning under 5% of the hero's diagonal
is an `ExportError`), `favicon-16/32/48/180/512.png`

- `favicon.ico` (16/32/48, from the flat motif via `motif.rasterize` with a
resvg fallback), `mark-color.svg` + `mark-mono.svg` (SVGO; mono recolors every
fill to ink via `motif.mono` with a regex fallback), `pwa/` (icons only: `js/pwa.mjs` passes
`--icon-only`, so no splash screens; `manifest.json` srcs rewritten relative),
`manifest.webmanifest` + `browserconfig.xml` + android/mstile sets via
`js/favicons.mjs`, `model.glb` (Draco via `js/gltf.mjs`, when present),
`scene.blend` (copied when present), `contact-sheet.png` (labeled thumbs).
Returns the manifest dict and writes `exports/manifest.json` (sizes + sha256).

Adapter entries: `export:optimize_svg`, `export:draco_compress`,
`export:favicons_meta`, `export:pwa_assets`.

## Tool notes

- Cycles glare needs a compositor node tree, which headless pip `bpy` lacks; a
  scene with `glare > 0` renders without bloom and logs that it did.
- HDRIs come from Poly Haven / ambientCG (CC0) and cache under
  `~/.cache/logo-maker/hdri`; starter scenes use `polyhaven:poly_haven_studio`,
  and `hdri = "none"` renders offline with the rig lights only.
- Font licenses are recorded per spec in `run.json` assets (`font:<Family>` or
  `font:<Family>:<axis>=<value>,...`) with the file's source URL; the cache lives under
  `$LOGO_MAKER_CACHE/fonts` (default `~/.cache/logo-maker/fonts`). The Google
  Fonts check only verifies the download transport; a family that vanishes
  upstream fails at `fonts.resolve()` with a `FontSpecError` naming the fix.
- `primitive` is nondeterministic (it has no seed flag); use it for
  reference-derived abstraction, not for repeatable marks.
- `trianglify` is GPL-3.0 code running locally; the triangle coordinates and
  colors it emits are data, but the dependency is listed in THIRD_PARTY_NOTICES.md.

Sampling profiles, image-bound diagnosis, diagnostic EXRs, explicit controls and job budgets are
defined in [automatic-sampling.md](automatic-sampling.md). `RenderResult.sampling` points to the
job record; its delivered-image hash describes the post-downsample PNG. Exports stage under the
remaining job deadline and retain sampling provenance plus complete output hashes in their manifest.

Explicit alternate renderers retain their adapter execution behavior and return
`outside_cycles_policy`; their intermediate Cycles report cannot attest their delivered pixels.
They cannot inherit a qualified Cycles sampling state or become qualified pipeline winners.
