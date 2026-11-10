# Logo 3D — Rendering Quality + Materials (slug: render)

**Question:** beyond the current EEVEE floor (bpy 5.2.3 headless), which alternative/complementary renderers run headless on Apple Silicon, which CC0 sources feed them, and what material/post recipes lift the enamel disc beyond "nice raster"?

**Brand anchor:** blue enamel disc (#1E4A7A), gold rim, raised ivory Playfair Display "C", polished gold check. Calm/capable/discreet. Palette and fonts as briefed.

## TL;DR recommendation

**Primary final path: Blender Cycles (CPU is fine at 640–2048px; Metal if an interactive session works) + Blender Compositor Glare + Poly Haven HDRI.** Cycles is the smallest lift from the existing bpy scene (same `.blend` graph, same materials): swap `scene.render.engine` to `CYCLES`, add the HDRI `ShaderNodeTexEnvironment` world, set samples 64–256 with OIDN. It gives true path-traced gold (specular IOR, envmap reflections) that EEVEE fakes.

**True alternative final: Mitsuba 3 `metal_ad_rgb`** — verified running on this Mac (below). Best gold physics (spectral IOR via `Au`), differentiable, scriptable from Python without Blender. Hand-write XML scenes (no Blender import); export the disc from Blender as glTF/OBJ if reusing geometry.

**Do not chase:** appleseed (last macOS build 2019, x86_64), pbrt-v4 (CPU-only reference tracer; needs hand-written `.pbrt` scenes), LuxCore on Metal (OpenCL only, no Metal backend; BlendLuxCore has a reported macOS crash).

**Assets:** Poly Haven API (`api.polyhaven.com`, **.com** — `.org` returns 522) + ambientCG v3 API, both CC0, both verified live, no keys.

## Verified probes (this Mac, Apple Silicon, /tmp/logo3d-render/)

### Probe 1 — Blender EEVEE vs Cycles + Poly Haven HDRI (bpy 5.2.3, Python 3.13)

- HDRI: `poly_haven_studio_1k.hdr` (1,682,195 bytes) from `https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/poly_haven_studio_1k.hdr` (200 OK; `file` reports Radiance HDR). File-listing JSON at `https://api.polyhaven.com/files/poly_haven_studio`.
- Scene (`probe_cycles.py`): blue enamel cylinder (#1E4A7A, coat 1.0 / coat-rough 0.06), gold torus rim, Playfair Black "C" (`/tmp/logo3d/PlayfairDisplay-Black.ttf`), gold check bar, dark ground, sun light, world = HDRI envmap. Camera (2.2, −3.2, 1.4) looking at disc.
- Output: **`C_eevee.png` (455,464 bytes) and `C_cycles.png` (475,967 bytes)**, both 640×640. EEVEE noted `BLENDER_EEVEE` (5.2.3 has no `BLENDER_EEVEE_NEXT` enum — first run failed on it, fixed and reran).
- **Cycles rendered headless in ~3 s wall total (CPU path)** — this is the trustworthy headless mode today. Center pixels: EEVEE (157,177,193) vs Cycles (149,168,183) — Cycles reads slightly deeper (path-traced env).
- **Metal enumeration works, Metal headless render hangs:** `compute_device_type="METAL"` + `refresh_devices()` lists `("Apple M5 Pro (GPU - 20 cores)", "METAL", True)` in both pip-bpy and system Blender 5.2.2. But actual GPU renders hung across 3 attempts (full scene twice, once via system Blender, plus a minimal 256px/16-sample cube killed before completion) — no file after >3–5 min each. Likely first-run Metal kernel compilation or a headless Metal queue stall. **Conclusion:** keep Cycles Metal for interactive/GUI sessions where a kernel cache can warm; use Cycles CPU (fast enough at logo sizes) or Mitsuba Metal for headless finals until the warm-up is done once interactively.

### Probe 2 — Mitsuba 3 (mitsuba 3.9.1, drjit 1.5.0, uv venv)

- Install: `uv pip install mitsuba==3.9.1` — clean install (49.9 MB + drjit 4.0 MB), Python 3.13. `mi.variants()` returns 13 variants including **`metal_ad_rgb`** — Metal AD is present on this Mac.
- Scene (`scene.xml`): path integrator, 640×640 hdrfilm, 64 spp, `poly_haven_studio_1k.hdr` envmap emitter, two `Au` roughconductor spheres (alpha 0.1) + #1E4A7A roughplastic disc.
- Output: **`mitsuba_scalar_rgb.png` (571 KB), `mitsuba_llvm_ad_rgb.png` (580 KB), `mitsuba_metal_ad_rgb.png` (580 KB)**, all valid 640×640 PNGs. Center pixel (the gold sphere) (141,110,61) — gold reads warm/orange as expected from spectral Au IOR.
- Gotchas found and fixed (useful for the real scene): gold material key is **`Au`** (no `gold.eta.spd` in the wheel); roughplastic color key is **`diffuse_reflectance`**; sensor transform name is **`to_world`**; Mitsuba 3 XML parser is strict (unreferenced properties are errors); disk scene dicts need variant-specific transform types — **use XML** (`mi.load_file`). Note: `mi.util.write_bitmap` raised `FileNotFoundError` after writing in this probe, but the PNGs are valid — write with PIL/numpy for finals. License: repo LICENSE is BSD-3-Clause style ("Redistribution and use in source and binary forms…"); GitHub API reports NOASSERTION, so treat as BSD-3-Clause by text, not SPDX.

## Renderer comparison (headless, Apple Silicon)

| Renderer | License | arm64 + headless | Metal? | Role | Verdict |
|---|---|---|---|---|---|
| Cycles via bpy | Apache-2.0 (Blender ≥4.5) | ✅ | ✅ enumerates; ⚠️ headless render hung in probes | final | **Default.** Same scene, swap engine. CPU headless verified fast. |
| Mitsuba 3 | BSD-3-Clause (by text) | ✅ (pip wheel) | ✅ `metal_ad_rgb` verified | final alt | **Best alternative.** Spectral gold, differentiable. XML scenes. |
| LuxCoreRender 2.11 | Apache-2.0 | ✅ (v2.10+, PyPI wheel) | ❌ OpenCL only | final alt | Strong stills, but no Metal; BlendLuxCore crash reports. |
| pyluxcore 2.11.2 | Apache-2.0 | ✅ wheel | ❌ (OpenCL) | scripting | Drives LuxCore without Blender addon. |
| BlendLuxCore | GPL-3.0 | ✅ addon | ❌ | in-Blender | GPL viral; crash on material copy (2025 report). |
| appleseed | MIT | ❌ (2019 x86_64 zip) | ❌ | — | Dormant. Skip. |
| pbrt-v4 | Apache-2.0 | ⚠️ CPU only (source build) | ❌ (OptiX only) | reference | Ground truth only; no glTF pipeline. |
| Filament 1.80 | Apache-2.0 | ✅ universal mac.tgz | via Metal/Vulkan | preview | Real-time PBR; validate glTF chain. |
| Filament gltf_viewer | Apache-2.0 | ✅ `filament-v1.80.0-mac.tgz` | ✅ | verify | Headless batch: `gltf_viewer --headless --batch=spec.json --ibl=sky model.glb`. |
| OIDN | Apache-2.0 | ✅ | bundled in Blender | post | Denoise Cycles/LuxCore outputs. |
| OpenImageIO 3.2.2 | Apache-2.0 | ✅ pip (`uv pip install OpenImageIO`) | n/a | post | oiiotool, tonemap, contact sheets. Brew bottle exists but **not installed** (no-system-install rule) — use pip. |

## CC0 asset sources (primary APIs, verified live)

- **Poly Haven API** — `https://api.polyhaven.com` (note: **.com**, not `.org`; `.org` answered `error code: 522` during probes). `GET /files/studio_small_05` returned JSON with tonemapped + HDR 1k–16k URLs, sizes, md5. Endpoints: `/assets` (filter `type`, `category`), `/files/{slug}`, `/search?q=&t=`, `/info/{slug}`. Assets + API are CC0 (per `polyhaven.com/en/our-api`); API terms just ask for a visible "assets from Poly Haven" credit line. Studio picks: `poly_haven_studio` (used), `studio_small_05` (1k HDR 1.72 MB), `studio_small_08/09`.
- **ambientCG v3** — `https://ambientcg.com/api/v3/assets?type=material&q=metal&limit=1&include=title,downloads` returned `totalResults: 214`, first asset `Metal063` with `https://ambientcg.com/get?file=Metal063_1K-JPG.zip`-style URLs. CC0 1.0, no key. Also `https://ambientcg.com/api/blender/` remote-library index (9,382 assets) for in-Blender browsing. Zips contain Color/NormalGL/Roughness/Displacement(/Metalness/AO/Opacity) + `.mtlx`. Use for paper/cloth backgrounds; gold/enamel stay procedural.

## Material recipes (Blender shader nodes, drop into current scene)

All verified against Principled BSDF input names in Blender 5.2 (Coat Weight / Coat Roughness). Palette hex → linear in nodes where noted.

1. **Enamel (primary disc)** — Principled: Base `#1E4A7A`, Metallic 0, Roughness 0.18, **Coat Weight 1.0, Coat Roughness 0.06**, Specular IOR 1.5. The coat is what separates enamel from matte plastic in Cycles.
2. **Polished gold (rim/check)** — Principled: Base `#F2C14E`, Metallic 1.0, Roughness 0.12. For CG-chrome look; for leaf realism see #3.
3. **Gold leaf** — Metallic 1.0, Base `#F2C14E`, Roughness 0.1 + Noise Texture (scale ~40) → Roughness for lap variation, faint Bump. Stops the "plastic trophy" read.
4. **Brushed brass (warm alt)** — Metallic 1.0, Base mix `#B45309`/`#F2C14E`, Roughness 0.25–0.35, Anisotropic 0.6 with brushed Noise → Tangent rotation. Warmer, less mirror than polished gold.
5. **Letterpress paper (wordmark ground)** — Base `#F8F6F1`, Roughness 0.9, Noise (scale 60, detail 4) → Bump 0.03, Subsurface 0.15. Behind wordmark only.
6. **Porcelain (alt disc)** — Base `#F8F6F1`, Roughness 0.22, Coat 0.5, Subsurface 0.3 with `#E8DFC8` radius. If enamel reads too plastic in finals.
7. **Glass (alt dome)** — Transmission Weight 1.0, IOR 1.5, Roughness 0.02–0.05. Cycles-only (EEVEE transmission is fake).
8. **Beeswax** — Subsurface 0.4, radius `#B45309`, Roughness 0.55, Sheen. Only if wax-seal direction returns.

## Post pipeline (cheapest that lifts quality)

1. **Cycles DOF** (camera `dof.use_dof`) — only true DOF in the chain.
2. **Blender Compositor Glare** (Fog Glow, Threshold ~0.8, Size 7–9) for rim/check bloom — more controllable than oiiotool bloom.
3. **OIDN** via Cycles denoising (CPU device) or standalone on EXR.
4. **OpenImageIO oiiotool** via pip for tonemap/contact sheets/HDRI EXR conversion. No brew needed.

## Risks / needs user permission

- **Cycles Metal headless hang** (3/3 attempts): warm the kernel cache once in an interactive Blender session, or accept Cycles CPU. No install needed either way.
- **LuxCore/BlendLuxCore**: no new installs needed (PyPI wheel + addon zip), but BlendLuxCore is GPL-3.0 — flag if the logo output might be redistributed with the tool.
- **OIIO via brew** (`brew install openimageio`, 3.2.2.0 bottled): needs user sign-off; pip wheel covers it without system install.
- **appleseed arm64**: only via from-source CMake build — do not invest without approval.
- Filament `filament-v1.80.0-mac.tgz`: third-party binary download from GitHub Releases (universal, signed by Google) — preview-only; needs user OK to download.
- No API key used, no system-wide installs performed, no AI image/3D generation used. All probes in `/tmp/logo3d-render/`.

## Probe artifacts (for Main to view)

- `/tmp/logo3d-render/C_eevee.png`, `/tmp/logo3d-render/C_cycles.png` (Cycles CPU + HDRI)
- `/tmp/logo3d-render/mitsuba_{scalar_rgb,llvm_ad_rgb,metal_ad_rgb}.png`
- Scripts: `probe_cycles.py` (scene), `mitsuba-probe/scene.xml` + `probe2.py`, `min_metal.py`
- Full machine-readable list: `logo-3d-render.jsonl` (29 rows).
