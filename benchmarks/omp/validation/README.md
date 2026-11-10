# Foundation validation — November 10, 2026

Implementation and fixture revision: `2885935` (execution implementation `bec3495`).
This directory retains measured foundation results; it does not certify #4 end-to-end quality.

## Local checks

| Check | Observed result |
| --- | --- |
| `just test` | 204 passed, 2 render tests deselected; 9.31 s |
| `just render-example` | Both local render checks passed; 5.35 s |
| `just lint` | Passed |
| `just type` | Passed |
| `just hooks` | All hooks passed |
| `just doctor` | 46/46 passed |
| `python -m logo_maker.benchmark verify benchmarks/omp` | 21 pinned assets verified; qualification incomplete |

The test suite retained dependency deprecation warnings. No Jev definitions/provider logic changed;
no live aesthetic qualification was performed. A supplementary Jev completion gate was **inconclusive**:
it reported truncated context, composite 0.680 and minimum safe-to-apply 0.35, with all four completion
claims verified but one below the 0.8 auto-accept confidence threshold. Its JSON is retained rather
than represented as a pass. Independent, full-context code review found zero standards findings and
one spec finding: overall Skill Swap rejection had been assigned to craftsmanship. Commit `2885935`
fixed that finding by keeping overall rejection separate and the dimension labels unknown/unranked.

## Actual device enforcement

```sh
uv run --locked python scripts/validate_gpu.py --baseline c45804d
uv run --locked python scripts/validate_gpu.py --render /tmp/logo-inherited-cpu-2885935
```

Both begin with CPU enabled and Metal disabled. Baseline inspection leaves CPU enabled alongside
Metal. The new boundary disables CPU, enables the sole available Metal GPU, overrides the native
Cycles device mask to Metal, and completes an actual render with OIDN-created Metal device and
executed RT filter diagnostics. The probe deliberately reintroduces CPU just before calling the
actual rendering boundary. Native diagnostics, selected devices and settings are retained under
`inherited-probe/`. Baseline inspection does not render with the unenforced configuration.

Offline checks cover missing/stale Metal, inherited CPU, previously disabled Metal, unsupported
GPU denoising, missing diagnostics, CPU fallback diagnostics and preservation of a usable prior
image when a new output cannot be verified. The actual GPU probe verifies the successful path;
synthetic fallback tests are not presented as an actual hardware-failure experiment.

## Packaged original reference replay

Target: Apple M5 Pro (20 GPU cores), macOS 27.0.1, bpy 5.2.3 `e13b728c6880`, OIDN 2.5.0.
CPU tracing disabled, Metal-only native override, MetalRT Auto, GPU OIDN verified, fixed 256 samples,
seed 42, adaptive off, automatic minimum 0, transparent RGBA PNG. Required CPU host work is allowed.

| Run | Render + denoise + PNG | Replay wall scope | Process CPU time during render |
| --- | ---: | ---: | ---: |
| 2000 px source / delivery | 6.224 s | 6.981 s | 2.006 CPU-s |
| 4000 px source → 2000 px delivery | 22.820 s | 23.951 s | 6.044 CPU-s |

One measurement per resolution, not a speed distribution. Replay wall scope starts at scene
construction and includes quality setup, verified render and downsampling; it excludes process
startup/imports, initial fixture verification, final delivered-file hashing and report writing.
Cache state stays unknown. Background/thermal variation was not isolated. These timings are not
comparable to earlier EXR diagnostics or different historical timing scopes as a speedup claim.
The 4000 px replay uses fixed 256 samples and does not qualify #5's adaptive production baseline.

Each subdirectory retains its execution log, execution JSON, replay report and exact input manifest.
Hashes identify the measured source and delivered images. Re-rendered GPU images need appropriate
visual tolerances; bitwise PNG equality is not the quality criterion. The historical CPU provenance
and original PNG bytes remain unchanged. New PNGs were inspected locally and attached to the linked
PR; the retained fresh matched-resolution original/glossy comparison is a separate fixture.

## Remaining qualification

Owner review of the packaged replay is pending. Fidelity must independently inspect perimeter/recess/
lips, relief edge treatment, glyph/legend proportions, material response, ribbons and lighting.
Craftsmanship, brief fit and preference require separate judgments; neither gloss nor exact fixture
reproduction proves creative transfer. Successful different-material owner-reviewed examples,
held-out briefs, per-dimension model judgments, self-comparison/presentation-order/error controls,
cache dependency keys and #5's full production sampling/cost/alpha/detail qualification remain open.
