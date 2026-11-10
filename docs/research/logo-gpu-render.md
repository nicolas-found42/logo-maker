# Logo GPU render investigation — headless Cycles Metal hang on pip `bpy` 5.2.3

**Machine:** MacBook Pro, Apple M5 Pro (20-core GPU), 48 GB unified memory, macOS 27.0.1 (26A434), Metal 4.
**Software:** pip `bpy` 5.2.3 LTS (bundled Python 3.13, venv at `/tmp/logo3d/venv-bpy/bin/python`).
**Scene:** `/tmp/logo/scene3d.py` — 2000×2000 extruded-mark scene with Principled materials and a studio HDRI `/tmp/logo3d-render/poly_haven_studio_1k.hdr`.
**Work dir:** `/tmp/logo-gpu/` (scripts, benchmark PNGs). Prior probes in `/tmp/logo3d-render/`.

## Verdict

**Headless Cycles Metal does NOT hang infinitely on this machine.** The "hang" seen by the prior probes is
**first-run Metal kernel compilation** — it looks dead because nothing renders (no progress, no samples) for
minutes while ~75 kernels compile, and any probe killed mid-compile never benefits. Once the cache is warm,
the same headless script renders in **0.4 s** for a minimal scene and **13 s** for the full logo scene.

Two known upstream bugs make the cold start even more fragile on exactly this stack (macOS 27 + M5 + 5.2.3 LTS):

1. **Slow kernel compile in 5.x** — [#150119](https://projects.blender.org/blender/blender/issues/150119):
   first compile went from ~20 s (4.5) to ~210 s (5.0) on an M4 Pro; `integrator_shade_shadow` alone 16 s → 112 s.
   **#150114** (Cycles "hangs and stuck on sample 0") was closed with: *"GPU kernels are being compiled. These can
   take 3+ minutes … until they're done, nothing will render."* — a verbatim match to the observed symptom.
2. **First-render kernel-load race that aborts the process** — [#165570](https://projects.blender.org/blender/blender/issues/165570)
   (macOS 27.0, M5 Max, 5.2.3 LTS, same commit `e13b728c6880`): intermittent SIGABRT (exit 134) in
   `ccl::path_cache_get` / `MetalKernelPipeline::compile` during first-render kernel load. Fix `ebacac0cd6`
   is **not in 5.2.3**, is in 5.3/5.4, planned for 5.2.4. Intermittent (1 in 30 default scene, ~1 in 8 heavier scenes),
   so a cold-cache probe can crash looks like "hang killed" depending on timeout.
3. **OOM hang variant (WIP PR, not merged)** — [#165305](https://projects.blender.org/blender/blender/pulls/165305):
   largest integrator kernels use >10 GB per Metal compiler instance; several compiling simultaneously can OOM the
   compiler service and *Cycles waits forever for kernels that never load* (M5 Max 48 GB, cold cache, "Loading
   render kernels" indefinitely). Our scene is small (did not reproduce the infinite variant), but it shows the
   failure mode is real for bigger scenes. Env override proposed by that PR: `CYCLES_METAL_MAX_COMPILE_THREADS`
   (not present in 5.2.3 binary — safe to set, just ignored).

## Evidence

### Device enumeration (headless `bpy`, no hang)

```text
bpy 5.2.3 LTS
compute_device_type: METAL
devices: [('Apple M5 Pro', CPU, use=False),
          ('Apple M5 Pro (GPU - 20 cores)', METAL, use=True)]
num_gpu_devices: 1   metalrt: AUTO   kernel_optimization_level: FULL
has_oidn_gpu_devices: True
```

Setup order that works headless: set `compute_device_type="METAL"` → `refresh_devices()` →
GPU device appears with `use=True` → `scene.cycles.device="GPU"`. (Note: prior `probe_cycles.py`
did `prefs.devices[0].use=True` **without** `refresh_devices()` — `devices[0]` is the CPU entry, so the GPU
was never explicitly enabled in that probe. Harmless here because refresh defaults `use=True`, but the
probe order was wrong.)

### Minimal Metal render (256×256, 16 samples, no denoising) — `/tmp/logo-gpu/min_metal2.py`

| Config | Wall time | Notes |
|---|---|---|
| CPU 256, OIDN on, default threads (=18) | 40.6 s | `threads` already 18 on this 18-core machine |
| CPU 1024, OIDN on | 161.7 s | reference for quality comparison |
| GPU 256, MetalRT AUTO, OIDN on GPU | 13.4 s | 3.0× vs CPU 256 |
| GPU 256, same, OIDN off | 8.3 s | OIDN costs ~5 s on top at 2000² (see below) |
| GPU 1024, MetalRT AUTO, OIDN on GPU | 23.3 s | |
| GPU 4096, MetalRT AUTO, OIDN on | 81.7 s | |
| GPU 4096, MetalRT AUTO, adaptive (thresh 0.01) + OIDN | 38.3 s | **2.1× faster than fixed 4096, same quality** |
| GPU 256, MetalRT **OFF**, OIDN on | 138.0 s | same quality, **10× slower** — keep MetalRT AUTO |
| GPU+CPU hybrid 256, OIDN on (both devices `use=True`) | 16.8 s | **slower than GPU-only (13.4 s)** — do not hybridise |
| EEVEE (Metal backend), TAA 64 | 3.2 s | fast draft, visible material downgrade (see below) |

Quality check vs CPU 1024 reference (mean absolute error, 0–255 scale, full 2000×2000 frame):

```text
cpu_256_default.png        MAE 0.18  frac>20 0.04%
gpu_256_auto_denoise.png   MAE 0.18  frac>20 0.04%
gpu_256_nodenoise.png      MAE 0.57  frac>20 0.14%
gpu_1024_auto_denoise.png  MAE 0.01  frac>20 0.00%
gpu_4096_denoise.png       MAE 0.13  frac>20 0.04%
gpu_4096_adapt.png         MAE 0.14  frac>20 0.04%
gpu_256_off_denoise.png      MAE 0.18  frac>20 0.04%
eevee_64.png                 MAE 2.11  frac>20 3.20%
```

- Even **256 samples + OIDN is visually indistinguishable** from CPU 1024 on this scene (MAE < 0.2/255).
- **1024 + OIDN on GPU is pixel-faithful** (MAE 0.01). This is the quality sweet spot.
- 4096 fixed vs 1024 reference shows MAE 0.13 — i.e. 4096 ≠ "cleaner than 1024 by much"; both ≈ reference.
  (Reference itself is 1024+OIDN, so sub-0.2 MAEs all mean "no visible difference".)
- Adaptive 4096 matches fixed 4096 quality (0.14 vs 0.13) at **half the wall time** — recommend adaptive + OIDN.
- OIDN on GPU (`denoising_use_gpu=True`) works on Metal (`has_oidn_gpu_devices() == True`) and is worth its
  ~5 s: without it 256-sample noise is 3× higher (0.57 vs 0.18). **Default `denoising_use_gpu` is `False`
  in 5.2.3 — must be set explicitly** (manual: Denoising › Use GPU).

### Settings that mattered / didn't

- **`compute_device_type="METAL"` + `refresh_devices()` + `scene.cycles.device="GPU"`** — required, sufficient.
- **`metalrt` (MetalRT hardware ray tracing)** — `AUTO` (default) is essential: 13.4 s vs 138.0 s with `OFF` at
  256 samples (same MAE 0.18). Never set `OFF` on Apple Silicon.
- **Tile size** — `use_auto_tile=True` + `tile_size=2048` (default) is fine on 48 GB unified memory; no OOM.
  Manual suggests smaller tiles for Windows display-timeout only — not applicable headless.
- **`use_persistent_data`** — on `scene.render` (was `scene.cycles` in older versions); irrelevant for single frames.
- **Kernel optimization level** — `FULL` (default); `OFF` does not fix #165570 per the issue.
- **Denoising** — `denoiser="OPENIMAGEDENOISE"`, `denoising_input_passes="RGB_ALBEDO_NORMAL"`,
  `denoising_use_gpu=True`, `denoising_quality` `HIGH` default; keep `prefilter` at default.
- **CPU threads** — `scene.render.threads=18` already default (18-core machine); explicit value == default.
- **CPU+GPU hybrid** — measured: 16.8 s vs 13.4 s GPU-only at 256 samples. On a single 48 GB unified-memory
  chip, adding the CPU device only steals samples from the faster GPU. **Do not hybridise.**
- **Env vars** — no `CYCLES_METAL_*` knobs exist in 5.2.3 (proposed only in WIP PR #165305). None needed.

## Recommended configuration (fastest + highest quality)

First run: allow **~2–5 minutes** for the one-time kernel compile (do not kill it). Every later process is warm.

```python
import bpy

# --- device setup (order matters) ---
cp = bpy.context.preferences.addons["cycles"].preferences
cp.compute_device_type = "METAL"
cp.refresh_devices()  # GPU device appears with use=True
cp.metalrt = "AUTO"  # hardware ray tracing when beneficial
for d in cp.devices:
    if d.type == "METAL":
        d.use = True

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"

# --- sampling: adaptive + OIDN (RECOMMENDED) ---
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.01  # manual: typical 0.1–0.001
sc.cycles.samples = 4096  # adaptive ceiling; scene converges far earlier
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
sc.cycles.denoising_use_gpu = True  # default False in 5.2.3 — MUST set, else CPU OIDN
sc.cycles.tile_size = 2048
sc.cycles.use_auto_tile = True

# --- alternative: fixed 1024 if you want deterministic timing (23 s) ---
# sc.cycles.use_adaptive_sampling = False
# sc.cycles.samples = 1024

bpy.ops.render.render(write_still=True)
```

Measured on this machine (2000² scene): **GPU adaptive 4096 + OIDN = 38 s**; **GPU fixed 1024 + OIDN = 23 s**
(identical pixels, MAE 0.01 vs CPU 1024); CPU 256 baseline was 41 s. GPU is ~3× CPU at equal samples and
~7× at fixed 1024 (23 s vs 162 s).

**Flat fallback (no compile risk, e.g. CI cold cache every run):** CPU 256 + OIDN = 41 s, same quality
(MAE 0.18). If cold-cache first-compile time must be avoided entirely, use CPU or EEVEE — see table above.

**With a warm cache, always prefer GPU.** `~/.cache/cycles` persists across processes; never delete it
between renders. Set a generous timeout (≥ 300 s) for the first render of any new scene class.

## EEVEE (Metal backend) headless

EEVEE headless (Metal backend) works fine — `eevee_64.png` rendered in **3.2 s** at 2000² with TAA 64.
Quality vs Cycles CPU 1024 reference: MAE 2.11, 3.2% of pixels differ by >20/255. Visually the image is
clean (no noise, no banding), but the material model visibly downgrades: the coated disc reads as glossy
molded plastic / enamel (no soft translucency/SSS) and the metal relief is flatter and more uniform
(no strong environmental reflections), with slight edge fringing against the transparent background.
**Use EEVEE only for quick layout/iteration drafts; ship the logo from Cycles GPU.**

## Caveats / follow-ups

- **5.2.4 / 5.3+**: update `bpy` when 5.2.4 ships (contains #165570 fix) or 5.3 (fixed + faster compile).
  `pip install --upgrade bpy==...` into the venv; re-run `min_metal2.py` cold to confirm.
- **Intermittent first-render SIGABRT (#165570)** can still hit a cold-cache 5.2.3 run (~3% for a default
  scene, more with volumes/glass). Mitigation: retry the process once; the kernel cache is usually complete
  after a crash+relaunch since kernels already compiled stay on disk. Do NOT "fix" by lowering optimization —
  the issue reproduces with it Off.
- **OOM hang (#165305, WIP, unmerged)** applies to much larger scenes (many shaders/volumes) at 48 GB.
  Our scene compiles fine (211 MB cache, no hang). For big scenes, keep `use_auto_tile=True` and expect
  3–10 min cold compile; consider `CYCLES_METAL_MAX_COMPILE_THREADS=2` (ignored by 5.2.3, harmless).
- Benchmarks are single-frame, single-run wall times from `bpy.ops.render.render` (timing logged in scripts
  under `/tmp/logo-gpu/`). PNGs: `cpu_256_default.png`, `cpu_1024.png`, `gpu_256_auto_denoise.png`,
  `gpu_256_nodenoise.png`, `gpu_1024_auto_denoise.png`, `gpu_4096_denoise.png`, `gpu_4096_adapt.png`,
  `gpu_256_off_denoise.png`, `hybrid_256.png`, `eevee_64.png`, `min_metal.png`.

## Sources

- Blender #150119 — Metal kernel compilation ~10× slower in 5.0 (210 s vs 20 s, M4 Pro) —
  https://projects.blender.org/blender/blender/issues/150119
- Blender #150114 — Cycles hangs/stuck on sample 0 (closed: "nothing will render until kernels done, 3+ min") —
  https://projects.blender.org/blender/blender/issues/150114
- Blender #165570 — SIGABRT in `path_cache_get` at first Metal render, macOS 27 + M5, 5.2.3 LTS identical commit;
  fix `ebacac0cd6` in 5.3/5.4, planned 5.2.4 — https://projects.blender.org/blender/blender/issues/165570
- Blender PR #165305 (WIP) — Metal render hangs on kernel-compile OOM (>10 GB/kernel, M5 Max 48 GB) —
  https://projects.blender.org/blender/blender/pulls/165305
- Blender Manual 5.2 — GPU Rendering (Metal setup, limitations) —
  https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html
- Blender Manual 5.2 — Sampling (adaptive, OIDN, Use GPU) —
  https://docs.blender.org/manual/en/latest/render/cycles/render_settings/sampling.html
