# Sampling qualification evidence

This is technical evidence for [#5](https://github.com/nicolas-found42/logo-maker/issues/5),
not a catalog/default design reference. No qualified replacement profile is shipped.
Owner sampling review, tolerance calibration and owner-reviewed held-out brief qualification
remain open. Both Chief finishes retain their existing positive craftsmanship labels;
these synthetic fixtures do not redefine that standard.

## Machine and method

November 10, 2026: Apple M5 Pro, 18 CPU / 20 GPU cores, 48 GB; macOS 27.0.1 build 26A434;
bpy 5.2.3 build `e13b728c6880`; OIDN 2.5.0 Metal runtime execution. CPU tracing devices
are disabled; required CPU construction, analysis and file I/O remain permitted.

`scripts/validate_sampling.py` creates synthetic directional-instrument (matte/metal),
interlocking-optics (glass), and visible-ring-lettering fixtures. Every job runs actual
`render(..., 'final')`, 4000 px tracing, production 2000 px downsampling, and `export_all`,
including 16/32/48 px flat exports, hero, avatar, PWA and model exports. All 25 jobs have
verified Metal tracing policy and independently observed OIDN Metal filter execution.

Baseline: isolated `git archive` of `38ba86b9ccff305cb453c46920824509ae989f76`, with the
same locked interpreter and external tools. Numeric baseline is adaptive 4096 / 0.01.
Current jobs additionally collect bounded diagnostic EXRs and provenance. Baseline repeats
use actual seed 0; candidate comparisons use recorded seeds 0 and 43. Two observations are
small samples, not confidence intervals or a reliable performance distribution.

Current engine snapshots changed during review; each job retains package source hashes,
full recipe/dependency/settings identity, runtime logs and delivered-image/export hashes.
The corrected typography/control jobs exercise the final publication implementation.
Source changes after those jobs are evidence/docs only. No cached image result or qualified
profile reuse is claimed.

## Complete render/export job cost

Times include host motif preparation, compile, process startup, tracing, denoise, PNG,
current diagnostic EXR write/read/hash, downsampling and the complete export set. They exclude
parent process launch, source-fixture authoring and later review-sheet generation; the batch
interval below additionally includes orchestration/fixture setup. Kernel/cache state is
unknown. First observation does not mean cold kernels.

| Fixture | Baseline 0.01 mean (range), s | Current 0.01 mean (range), s | Current 0.02 mean (range), s |
| --- | --- | --- | --- |
| Matte, n=2 each | 24.51 (21.23–27.78) | 23.69 (23.67–23.70) | 20.69 (18.78–22.60) |
| Metal, n=2 each | 36.94 (35.04–38.84) | 45.11 (40.91–49.30) | 24.57 (23.83–25.30) |
| Glass, n=2 each | 64.52 (63.72–65.33) | 64.04 (63.51–64.57) | 47.93 (47.88–47.97) |
| Visible typography | 47.62 (n=1) | 49.26 (n=1) | 45.64 (44.99–46.29, n=2 seeds) |

The two 0.02 jobs together (selection + independent-seed confirmation, both full exports)
cost 41.38 s matte, 49.13 s metal, 95.85 s glass, and 91.27 s typography. Each exceeds one
baseline job. Running a compulsory search/confirmation on every concept is not justified by
these measurements. A single reused candidate may be cheaper, but its suitability is unqualified.

The 23-job material matrix plus corrected typography/control interval took **912.89 s** of
observed host wall time, including orchestration, process launches and inter-run I/O. Two
exploratory matte pilots outside that interval took another **49.60 s** measured inside their
jobs. All 25 measured job bodies total **955.51 s**. The batch interval uses output-log creation
and final-write timestamps; it is not a kernel timer. Later analysis/visual review and owner
review costs are excluded and unmeasured. This is incurred one-off investigation cost,
not the cost of a completed qualified profile.

For a future qualified profile, cost-only amortization would be
`candidate job cost + one-off qualification cost / reuse count`; suitability and actual reuse
must first be established. No realized amortized speedup is claimed here. The shipped final
baseline remains 4096 / 0.01.

## Diagnostic and visual observations

The actual module emits 20 float channels across Combined, Debug Sample Count, Noisy Image,
Albedo, Specular Albedo, Normal, Roughness and Depth EXR subimages. Counts are normalized:
the analyzer multiplies X by cap. Reports include foreground/dark/alpha-boundary/spatial
quantiles and near-cap fractions. All current jobs retain available diagnostics.

The deliberately cap-16 typography control used 16 samples for every foreground pixel:
p50/p90/p99/max 16, at-cap and near-cap fraction 1.0. Its noisy glyph/detail crop visibly
contains grain; denoising suppresses that grain. This is a useful demonstration that denoised
agreement does not independently establish detail preservation. It is not yet an owner-labeled
negative sampling control or a calibrated automated tolerance.

**Fixture limitation found by visual inspection:** the initial matte/metal/glass ring text
was below the plate surface. Those costs remain valid for their actual geometry, but those
runs do not establish typography quality. The separate typography fixture raises the letters
above the face. Occlusion is a geometry diagnosis; no sampling escalation repairs it. Initial
runs are retained rather than relabeled as successful text validation.

Final-image glyph/counter crops, original-resolution noisy/denoised crops, tiny flat exports,
and alpha composites on light, dark and saturated backgrounds were inspected by the agent.
Matte, metal and glass have different intended appearances; the reports make no craft ranking
based on gloss. The optics motif is a materially different synthetic brief. Owner-reviewed held-out
qualification and owner labels remain pending.

## Retained artifacts and reproduction

[validation/measurements.json](validation/measurements.json) indexes all 25 jobs. Each sibling
JSON contains measurement, execution, sampling, source and delivered/export hashes; adjacent
`.execution.log` files retain native denoiser evidence. Large full EXRs, PNGs, scene.blend,
GLBs, complete source fixtures and exports remain locally at
`/Users/nicolas/Documents/logo-maker-evidence/2026-11-10-issue5/` (about 4.8 GB). This is a
persistent immutable copy; raw JSON keeps original temporary paths and `retention.json` maps
their suffixes to this root. Hashes and reproduction commands are retained in Git. Git evidence
does not contain the large raw image bytes; reviewers on other machines must reproduce them
or obtain the retained bundle. No public raw-EXR download is claimed.

```sh
uv run --locked python scripts/validate_sampling.py --root /tmp/new-sampling-run \
  --prepare-baseline 38ba86b9ccff305cb453c46920824509ae989f76
uv run --locked python scripts/validate_sampling.py --root /tmp/new-sampling-run \
  --case metal --arm baseline --run 1
uv run --locked python scripts/validate_sampling.py --root /tmp/new-sampling-run \
  --case metal --arm current --threshold 0.02 --seed 43 --run 1
uv run --locked python scripts/validate_sampling.py --root /tmp/new-sampling-run \
  --case typography --arm current --cap 16 --run degraded
```

[validation/code-review.md](validation/code-review.md) records Standards and Spec reviews and
fixes. [validation/offline.txt](validation/offline.txt) records 221 offline tests passing;
render regression records 2 passing tests. The second is an explicit legacy LuxCore adapter
regression outside Cycles sampling qualification, not a CPU fallback for these experiments.
Doctor passed 46/46; lint, types and hooks passed. The auxiliary Jev completion gate
escalated for review; it is retained along with the subsequent 25-job mechanical artifact
audit. The PR remains draft rather than claiming automated review acceptance.
Jev questions/provider code are unchanged;
no product live-Jev qualification was run.
