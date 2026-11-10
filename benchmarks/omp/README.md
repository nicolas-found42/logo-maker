# OMP provenance and qualification foundation

Refs [#4](https://github.com/nicolas-found42/logo-maker/issues/4).
This bundle preserves evidence, not brand defaults. It does **not** certify end-to-end quality.

## Verify and replay

From a checkout with the locked uv environment on the owner's Metal-capable Mac:

```sh
uv run --locked python -m logo_maker.benchmark verify benchmarks/omp
uv run --locked python -m logo_maker.benchmark replay benchmarks/omp --output /tmp/omp-replay-2000
uv run --locked python -m logo_maker.benchmark replay benchmarks/omp --output /tmp/omp-replay-4000 --resolution 4000
```

Use a fresh output directory for each run. The first command verifies SHA-256 for every asset and
recipe dependency. Replay refuses to write inside the bundle. The replay uses the original retained
scene body, substituting only packaged font/contour paths and the HDRI argument, then applying the
strict Metal execution policy. No temporary source, font, HDRI, contour or external environment path
is needed. The historical script is retained byte-for-byte as `recipe/wax3d.py.txt`; its original
ending selects CPU for Cycles and is **not** executed. The replay's render settings explicitly select
GPU-only tracing and verified GPU denoising. The original recipe is a benchmark, never a generator
for unrelated brands. The CLI rejects unavailable Metal and unverified/CPU denoising.

The 4000 px replay uses fixed 256 samples to reproduce the historical sampling effort and the normal
Lanczos 2000 px delivery operation. It is **not** #5's adaptive-final qualification. Normal production
finals retain adaptive 4096 / 0.01. A fixed-256 replay does not validate replacement defaults.

Outputs include a new `replay.png`, `execution.json`, native OIDN `execution.log`, input manifest and
`replay.json` with source-manifest hash, seed, effective settings, build, device state, timing scope,
process CPU time, delivered hash and pending review status. CPU host work is permitted. Cache state
is recorded as unknown; the wall time excludes process startup. No energy or universal speed claim
is made. Each process currently accepts exactly one available Metal GPU; ambiguous multi-GPU systems
fail operationally rather than selecting a different device silently.

## Evidence identities and rights

`manifest.json` is authoritative for origins, hashes, permitted use and owner labels. Original seal
and rectangular final PNGs, color/mono SVGs, reconstruction golden, fresh 2000 px reconstruction and
matched-resolution comparison are separate assets. Both matched-resolution Chief treatments are
owner-approved high quality. Neither their material differences nor GPU selection establish a
universal aesthetic ranking. The 256 px golden remains only a fast renderer-regression reference.

Historical final invocation: Cycles **CPU**, 2000 px, 256 samples, tilt 28°, studio HDRI, gold legend.
The retained script's EEVEE default was not the final invocation. The historical build was not pinned;
new replay build/OIDN/device evidence must not be presented as historical provenance. The original
PNG is retained as supplied; no cryptographic chain to the old temporary render bytes is asserted.
The flat SVG family shares relief contours but is not a wax rendering.

The owner supplied/authorized retaining project artwork for this benchmark. This does not grant a
new general trademark license. Open Sans is a retained static Bold instance under **SIL OFL 1.1**,
verified in its embedded license metadata. Relief contours include Playfair Display outlines; both
font licenses are retained. Assets from [Poly Haven](https://polyhaven.com/a/poly_haven_studio) are
CC0. Reconstruction source is retained from repository revision
`c45804d41af3c1ab1bbe32b7a72e1561f2f728f2` under the repository license. Do not regenerate the motif
when replaying that snapshot: its `motif.json`/SVG already preserve the authored outlines.

## Separate evaluation layers

| Layer | Evidence / meaning | Current status |
| --- | --- | --- |
| Renderer regression | Existing 256 px SSIM ≥ 0.90 | Independent fast check |
| Execution | Metal device override, CPU devices disabled, OIDN created Metal device and executed filters | Measured per replay |
| Reproduction fidelity | Perimeter, recess/lips, relief edges, glyph proportions, material response, ribbons and lighting against original | Human/full-resolution comparison pending |
| Craftsmanship | Technical finish at intended output sizes | Both retained Chief treatments approved; new replays pending |
| Brief fit | Intended symbolism and visual appearance for each brand | Separate owner labels pending |
| Preference | Personal material/finish/style choice | Unranked, independent of quality |
| Cross-brief transfer | Rejected Skill Swap controls, successful different materials, held-out briefs | Incomplete |

The Skill Swap Gather, Fold and Commons paper studies retain the owner's overall rejection label;
that label does not identify a particular causal defect. Missing per-feature, brief-fit and style
labels stay unknown. The foundation verifier always reports qualification **incomplete**. It never
converts a passed hash check or approved fixture into evidence that a fresh workflow transfers.

Later qualification must add owner-reviewed successful different-material examples and held-out
briefs, complete images and input/rubric/model hashes, per-dimension judgments, self-comparison,
normalized object scale/background, both presentation orders, and explicit missing/uncertain/error
states. Cached judgments must be labeled replay and bound to exact inputs and rubric/model config.
The historical Skill Swap investigation judgments are not imported as fresh validation. No universal
craft threshold or objective creativity score is invented here.

## Integration with #5

Call `logo_maker.blender.execution.render_verified` after applying candidate settings. It reasserts
exclusive Metal selection immediately before rendering and publishes output only after independent
OIDN runtime verification. `RenderResult.execution` exposes the builder evidence path. Preserve
its log plus full input/settings keys when profiling. Do not retry an operational policy failure as
a crash. #5 still owns sample-count EXR diagnostics, dependency/profile keys, bounded job budgets,
independent-seed detail/alpha checks, full-job cost comparisons, 4000→2000 qualification and owner
review. These remain open acceptance criteria on #4 and #5.
