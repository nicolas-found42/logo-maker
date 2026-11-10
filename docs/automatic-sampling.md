# Automatic sampling

Issue [#5](https://github.com/nicolas-found42/logo-maker/issues/5) owns this contract.
Sampling is a technical resource policy. Craftsmanship, brief fit and preference remain
independent acceptance dimensions under #2. Refinement requests go to #3. GPU enforcement
is #4's existing `render_verified`; ordinary CPU host work is permitted.

## Effective controls and budgets

Stage defaults remain test 64 fixed / 256 px, preview 256 fixed / 1000 px, and final
4096 / 0.01 adaptive / 4000→2000 px. `meta.seed` now explicitly reaches Cycles.
Compiled `quality` records samples, threshold, minimum, adaptive state, seed and `overrides`.

Optional `[render]` fields are `max_samples`, `adaptive_threshold`, `min_samples`, `adaptive`
and `seed`. An explicit false/zero survives compilation. A cap/threshold override enables
adaptation unless `adaptive` explicitly says false. Minimum 0 delegates to Cycles. Threshold
0 invokes Cycles automatic semantics; it is not an error of zero percent. A minimum above
the cap is invalid. Profile settings fill only controls the user did not specify. A repair
that needs to change an explicit control returns `override_conflict`. Overrides differing from a
profile’s reviewed settings retain their values and require independent qualification.

Optional `[sampling]` fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `profile` | absent | JSON qualification record, relative to concept or absolute |
| `diagnosis` | absent | JSON review tied to source/settings/seed and delivered image |
| `wall_seconds` | 1800 | Whole concept job wall budget, including setup and all attempts |
| `attempt_limit` | 2 | Native attempt ceiling, including crash retries; range 1–4 |
| `diagnostic_bytes` | 2147483648 | Per-attempt EXR storage/decoded I/O bound; 0 disables |

A child render inherits the earlier caller deadline and also enforces its scene budget.
Finalize and `run` share a 1800 s deadline across final QA, candidates and export; the overall
native ceiling is four attempts per finalist (12 in `run`), with the tighter scene ceiling
still applied within each render call. Standalone export starts a fresh explicit budget.
QA rounds are separately limited to five. Exports run in a subprocess capped by remaining
wall time, and publish a complete staged directory only after success. On macOS/Linux,
the worker owns a process session and reserves one second of the job budget for SIGTERM
launcher cleanup and final SIGKILL/reaping. A budget too small for that reserve does not
launch the worker. The supported browser launchers use termination hooks to close detached
browsers; arbitrary processes escaping the session without cleanup are unsupported. Render
subprocesses get min(900 s, remaining deadline). Configuration loading, compilation and
dependency hashing, final downsampling/alpha cleanup/EXR analysis/image hashing, and cache
validation now run in owned CPU workers using the same process cleanup. Their startup,
output transfer and cleanup count toward the deadline. Normal CPU host work is permitted;
the verified GPU rendering/denoising boundary is unchanged.

Configuration initially uses the caller's budget, or a bounded default 1800 s bootstrap
when no caller budget exists. Once read, the scene's wall limit includes elapsed bootstrap
time; it does not start a fresh clock after compilation. `render_many` runs each bounded
job in turn instead of an unbounded parallel compilation prepass; its `workers` argument
is retained for source compatibility. Host phase timings and interrupted attempt paths
are retained in the sampling report.

Asset-use events return as `RenderResult.assets` records and in the sampling sidecar.
An arbitrary `on_asset` callback now returns an explicit `budget_conflict`, because it
cannot both retain parent-process side effects and run in a killable worker. Direct
`scene.compile` still supports caller-managed callbacks. Profile/control JSON handling,
light publication/orchestration and final QA/provider work still use cooperative checks;
complete whole-job hard-bound qualification remains open.

Job timing includes scene compilation, environment probing, attempts, denoise, diagnostic
EXR writing/reading/hashing, PNG output, downsampling and cleanup. The export manifest adds
export time and the shared budget ledger. Calibration/independent-seed confirmations must
use that same caller budget when part of a live job; profile qualification is a separate
one-off cost, reported separately from reuse. Kernel/cache state remains `unknown`; a first
measurement is not automatically a cold measurement. No quality target is loosened to meet
a deadline. Time, attempt, memory, device, cap, noise and visual outcomes have separate fields.

## Profiles and reuse

No qualified numeric replacement ships with this change. Missing, invalid, stale or
out-of-scope profiles retain the unchanged adaptive baseline and return a review stop at
finalize. Low-level `render` and `export_all` can produce inspection artifacts explicitly
labeled unqualified; they cannot become pipeline winners. Legacy direct image exports are
marked `unattested_legacy_image` in the manifest.

A schema-1 profile contains:

- `context`: the actual environment fields from `.build/final.sampling.json` except
  `material_presets` and `custom_scene_sha256`. It includes hardware model/core/memory,
  OS/build, Blender build, all OIDN library hashes, backend/device/MetalRT, denoiser guides,
  stage/resolution, Python/image/geometry library versions, the project lockfile hash,
  render/postprocessing settings key, and package-source hashes. Paths
  inside `code_sha256` are package-relative. OIDN's version string is independently recorded
  in each runtime execution log; binary hashes invalidate versions before rendering.
- `settings`: `samples`, `adaptive`, `adaptive_threshold`, `min_samples`, `seed` (the
  profile seed describes calibration; production retains the job's seed).
- `material_presets`: explicitly reviewed transfer scope. New material presets return
  `profile_out_of_scope`. Custom `bpy` components return `profile_out_of_scope` and cannot
  reuse cached images: arbitrary Python can read undeclared files, so a source hash alone
  does not establish a complete dependency inventory. Direct inspection renders remain
  available. Qualification/reuse requires a future explicit custom-dependency contract.
- `coverage`: matte, metal, glass, dark, typography and alpha.
- `owner_review: "approved"`, plus `cases` with roles `positive`, `degraded`, `held_out`.
  Each case has an `evidence` object with `path` and `sha256` for its retained review record.
- `job_costs`: repeated `baseline_seconds` and `candidate_seconds` covering complete jobs,
  with calibration/confirmation/IO included. Keep raw runs, timing scope and amortization
  assumptions in the retained case records.

These are manually reviewed provenance records, not automatic attestations. The validator
checks scope, positive numeric costs, required case roles and retained review-file hashes;
it cannot establish that an owner's label is truthful or that a case actually tests its
claimed material. Review the records and pixels. Candidate settings must be selected from
measured, owner-approved candidates, choosing the least expensive demonstrated suitable one;
this schema does not prove a global optimum or automatically synthesize a profile.

Timing scope deliberately excludes random seed; image identity includes seed and complete
source/compiled settings/dependency hashes. Image-result caching is not timing-profile reuse.
`artifact_current` verifies source/code/catalog/assets/control-file and retained review hashes,
delivered bytes, execution
sidecar and current machine. Newly added source files invalidate a prior image. The compiled
scene plus resolved meshes/fonts/HDRI/texture files bind the execution; runtime native logs
also carry their own hashes. Changed profiles or diagnosis files invalidate reuse. Previous
records and candidate artifacts remain available after a failed later job.

## Diagnostics and decisions

The pinned bpy 5.2.3 module uses `image_settings.media_type = MULTI_LAYER_IMAGE` before
selecting `OPEN_EXR_MULTILAYER`. Enable `pass_debug_sample_count` and
`denoising_store_passes` before the verified render. Normal single-layer output has 20 float
channels in this build; a conservative 24-channel bound is checked before enabling capture.
Additional passes, AOVs, multiple layers, missing capability or storage exhaustion are
`unknown`, never zero noise. Bound each attempt and retain at most its configured attempts'
EXRs per job. Long-lived job history requires explicit operator retention management.

Analyze all EXR subimages. `ViewLayer.Debug Sample Count.X` is normalized; multiply by the
configured sample cap. Foreground is Combined alpha > 0.01. Summaries retain p50/p90/p99/max,
at-cap and ≥95%-of-cap fractions for foreground, dark regions, alpha boundaries and 4×4
spatial tiles. Dark/alpha masks locate review regions; they are not noise classifiers.
An empty region is null. Foreground saturation is never diluted by transparent background.
Native denoiser diagnostics must verify actual Metal filter execution, as #4 requires.

A diagnosis JSON binds `source_key` and `image_sha256` from an attempt record, with `kind`,
`basis`, `region`, `independent_seeds`, and `noisy_and_denoised_reviewed`. `region` names
the reviewed foreground/dark/alpha-boundary/tile entry; missing region evidence is unknown.
Sampling uses that region’s counts rather than saturation in unrelated pixels. For `sampling_noise`,
retain
at least two distinct seeds including the current seed and the actual supporting crops.
This declaration is review input, not a model confidence score. Generic `clean_edges` or
aliasing failure alone returns `edges_unknown_cause` to authoring without sampling changes.

| Evidence | Outcome |
| --- | --- |
| Reviewed stochastic noise with near-cap reviewed region | Compare a doubled cap, threshold held; ceiling 8192 |
| Reviewed stochastic noise with no near-cap reviewed region | Compare half threshold, cap held; floor 0.001 |
| Geometry, typography, resolution, filtering, alpha, denoiser detail loss | Scoped `refinement_needed` |
| Stale/uncertain diagnosis, missing samples, duplicate seeds | `unknown` |
| Explicit conflicting control | `override_conflict` |
| Budget/attempts exhausted | Stop, retain prior output, report limit |
| Unverified GPU render/denoise | Operational error; no new published image |

A comparison stops for fresh review; its predecessor's diagnosis cannot recursively escalate
new pixels. The policy changes one control at a time. It never changes lighting, materials,
roughness, clamping, caustics or geometry to make a sampling benchmark faster. A matching
reviewed profile may render its baseline without searching candidates. The resulting sampling
state is `profile_baseline`, subject to independent current-image QA. A capped result retains
its cap label even if independently accepted; this state does not claim proven convergence.

## Qualification procedure

1. Capture baseline revision and actual environment. Run `scripts/validate_sampling.py --help`.
   `--prepare-baseline REV` extracts source into a separate directory without changing Git
   worktrees. It uses the same locked interpreter and installed external tools.
2. Measure repeated baseline adaptive 4096 / 0.01 complete jobs and prospective settings on
   matte, reflective metal, transmission, dark areas and fine type, including a different
   brief/motif. Verify native Metal/OIDN reports on every run. Keep failed/limited runs.
3. Include independent seeds and full-size noisy/denoised detail. A crop/preview can reject
   cost or diagnose a defect; it cannot approve the whole image or certify 4000 px from a
   2000 px pilot. Use actual downsampling and full exports, including tiny flat glyphs.
4. Inspect glyph strokes/counters, bevels/highlights and dark gradients at final pixel density.
   Composite alpha on light, dark and saturated backgrounds. Retain original full images,
   seeds, source hashes, crop coordinates and export manifests.
5. Ask the owner to label positive and deliberately degraded controls, then held-out briefs.
   Record intended style and preference separately from craft and technical sampling quality.
   Both Chief finishes are positive craft examples; gloss is not the acceptance rule.
6. Calibrate any future automated noise/detail tolerance against those labels before enabling
   it. This implementation adds no automated noise/detail acceptance threshold or new Jev
   questions. Image metrics and seed agreement remain supporting diagnostics.
7. Compare total candidate selection + confirmation + final + export cost to baseline; also
   report one-off qualification cost and amortized reuse separately. Keep the baseline when
   extra probing is not justified. Publish a profile only after review and scope completion.

Primary sources: [pinned Blender adaptive/pass
properties](https://github.com/blender/blender/blob/e13b728c6880/intern/cycles/blender/addon/properties.py),
[pinned denoiser
selection](https://github.com/blender/blender/blob/e13b728c6880/intern/cycles/integrator/denoiser.cpp),
and [OIDN guidance](https://www.openimagedenoise.org/documentation.html).
