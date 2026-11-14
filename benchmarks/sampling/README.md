# Sampling qualification evidence

This is technical evidence for [#5](https://github.com/nicolas-found42/logo-maker/issues/5),
not a catalog/default design reference. The retained **4096 / 0.01** comparator now has
an owner-reviewed M5 Pro final profile in
[profiles/apple-m5-pro-final.json](profiles/apple-m5-pro-final.json). No faster numeric
replacement is enabled. The owner rejected 0.02 detail, accepted the shown 0.01 controls
and the cap-16 typography control, and explicitly accepted both independent-seed held-out
orbit/prism studies technically. Cap16 is therefore not a rejected control. Clover's broad
face-reflection defect was diagnosed as shading and resolved in a source-copy probe;
edge/bevel craftsmanship remains unresolved. Sampling acceptance is separate from
craftsmanship, brief fit and preference. Historical sections retain their original epoch
and qualification state; the final follow-ups supersede earlier pending-label statements.

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
fixes. [validation/offline.txt](validation/offline.txt) records 232 offline tests passing;
render regression records 3 passing tests (Cycles image, explicit LuxCore image, actual profile
library identity). The LuxCore image is an explicit legacy adapter
regression outside Cycles sampling qualification, not a CPU fallback for these experiments.
Doctor passed 47/47 (including the system process-status adapter); lint, types and hooks
passed. The auxiliary Jev completion gate
escalated for review; it is retained along with the subsequent 25-job mechanical artifact
audit. The PR remains draft rather than claiming automated review acceptance.
Jev questions/provider code are unchanged;
no product live-Jev qualification was run.

## Final dependency and region audit

Implementation `8797ced` also rejects custom bpy qualification/reuse until arbitrary input
dependencies can be inventoried. A source hash alone is insufficient. Normal profile identity
includes Python/image/geometry library versions and the project lockfile. Noise repair uses
the explicitly reviewed region, so unrelated saturated pixels cannot choose the control.

Five additional full production smoke jobs are retained in
[validation/final-runtime-validation.json](validation/final-runtime-validation.json), separately
from the original 25-job calibration cost matrix. All have verified GPU render/denoise,
4000→2000 delivery and 31 verified export-file hashes each. The final historical smoke’s recorded source
scope matched the then-current implementation (before the host-worker changes below).
Its runtime stack/lock identity is populated.
Owner qualification remains pending; these are operational checks.

## Owner review outcome

The owner rejected threshold **0.02 at cap 4096** in the shown typography and glass
comparisons: “No, 0.02 loses needed detail.” The faster numeric candidate therefore fails
its demonstrated detail requirement and is not qualified or selected. Keep the unchanged
**4096 / 0.01** comparator. The agent’s earlier provisional assessment is superseded by
this owner feedback. This is a sampling-detail verdict, not a craft or preference ranking.

The cap-16 control remains owner-unrated: the response requested clarification, not a quality
label. The comparison does not imply absolute/transfer approval of the 0.01 baseline.
[validation/owner-review.json](validation/owner-review.json) binds the exact owner response
to shown figure/source image hashes. No qualified replacement or automatic noise/detail
tolerance is enabled. Additional positive/held-out qualification remains open.

## Export deadline follow-up

The first hosted test attempt on `f3d0f15` timed out in the existing PWA helper at 300 s.
The unchanged failed-job rerun passed; the root cause remains unknown. This is retained in
[validation/ci-attempts.json](validation/ci-attempts.json), not described as a proven browser fix.

Separately, a local heartbeat regression proved that tool/browser work could survive the
outer export timeout. The fix owns a POSIX process session, reserves cleanup time within
the budget, signals launcher cleanup hooks, gives the group its grace period even after
the immediate worker exits, then force-kills/reaps remaining session work. Regression cases
cover both deadline expiry and an inner-tool error with a delayed detached-browser hook.
Prior exports remain intact. Uncooperative processes escaping without supported cleanup
hooks remain outside the adapter contract.

## Hosted macOS process-state correction

Final-head hosted tests exposed EPERM when inspecting an exited, unreaped process group.
A minimal local zombie-group probe reproduced it; reaping changed the response to ESRCH.
The fix uses bounded `/bin/ps` ID/state inspection only on denied group signals. Empty or
zombie-only groups have stopped work; live denied groups and failed inspection return
explicit cleanup-unconfirmed states. No command lines or process environments are read.
The platform utility is registered as an adapter and included in third-party notices.

Two deterministic regressions inject EPERM on real dead/live processes. Both were red
before the fix; all eight export tests now pass, with 228 offline / 3 render checks and
47/47 doctor checks. A fifth later full production smoke verifies the final source scope.
The narrow Jev gate escalated (composite 0.56225, safe-to-apply 0.24) and questioned the
red/green claim at low confidence. The independent Spec reviewer checked the exact logs
and confirmed both failures-before/eight-passes-after. The escalation is retained; no
automated merge approval is claimed. Final hosted validation remains separately tracked.

Owning platform sources: [Apple process-group signal handling](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sig.c),
[macOS ps license](https://github.com/apple-oss-distributions/adv_cmds/blob/main/ps/ps.c),
and [Linux procps license](https://gitlab.com/procps-ng/procps/-/blob/master/COPYING).

## Hosted lifecycle fixture timing

The next hosted run passed both process-state regressions, but the lifecycle fixture’s
four-second whole budget expired before its fake browser started. The test now allows
20 seconds including cold imports/format setup; its fake browser lasts up to 60 seconds
so natural exit cannot satisfy the cleanup assertion. Both reviewers confirmed that the
heartbeat-start, delayed-hook, stopped-work and prior-output checks remain meaningful.
Production code and budgets are unchanged. The final local suite still passes 228 tests;
three actual render checks and the final M5 operational smoke remain valid for unchanged
production source. Final hosted validation is tracked in the PR/issue.

The tests-only Jev gate escalated (composite 0.82275, safe-to-apply 0.61) for low confidence.
It verified the final local checks at 0.98 confidence, but classified the combined
tests-only/pending-hosted claim unsupported: no new hosted run existed in the supplied
evidence. The source diff shows only fixture timing edits; hosted results remain a
separate pending check. Prior broader gate escalations remain retained.

## Owned host stages and new production measurements

Heavy configuration/compilation/dependency hashing, image processing/EXR/hash and cache
verification now run in owned CPU workers sharing export's neutral process-session module.
Scene wall limits include initial configuration time. There is no unbounded `render_many`
compilation prepass. Interrupted attempts retain execution paths. Asset events return as
typed records; arbitrary `on_asset` callbacks report a budget conflict rather than running
unbounded or losing parent-process effects.

Public-seam FIFO regressions reproduced six-second budgets returning after ten seconds
for compilation, image hashing and cache validation; an implicit scene-only budget also
started preflight after expiry. Those checks now pass inside the wall bound and retain
prior results. Final local checks: **232 offline / 3 render / 47 doctor**, lint/types/hooks pass.

[host-budget-production.json](validation/host-budget-production.json) retains two separate
additional baseline/current typography pairs, outside the original calibration matrix.
Both use 4096 / 0.01, seed 0 and the real 4000→2000/full-export path. Each arm has verified
exclusive Metal tracing, executed Metal OIDN and 31 verified export hashes. The first pair
records body times 48.76 / 51.07 s. The second also records complete outer invocation times
**47.61 / 49.24 s**, with body times 47.40 / 49.02 s and launch/import/shutdown/reporting
overhead 0.21 / 0.22 s. Source-module paths and hashes bind the second baseline to
`38ba86b9ccff305cb453c46920824509ae989f76`
and current to the measured worker implementation. Each pair has one observation per arm;
cache/kernel state is unknown. No speedup, quality equivalence or amortized profile benefit
is inferred. Validation-copy/review work and measurement annotation are outside that timer.

The matched second pair has identical alpha. Opaque RGB differences are at most 2/255;
a 255/255 RGB outlier has alpha 1/255 in both images. These are supporting diagnostics,
not calibrated image-quality acceptance. The owner's 0.02 rejection remains unchanged.
A separate 1.57 s live CPU compilation probe verified Poly Haven asset-event transport;
it is not another GPU render or a visual qualification case.

At that source revision, whole-job hard-bound acceptance remained **partial**:
profile/control JSON and hashes, publication/export provenance, and QA/provider work
retained cooperative parent boundaries. The control/provenance follow-up below
supersedes those two read-path gaps. Positive/held-out owner qualification and a qualified
profile remain absent.

## Coordination with refinement and acceptance

A temporary clean three-way merge with #3 PR #8's 9cb556b snapshot compiled but failed
**2 tests / 255 passed / 3 deselected**. No branch was changed. The failures are custom
preview inspection and custom production-cache rejection: the merged local cache checker
refers to `inspection_only` without receiving it. Its flag must cross the worker protocol,
while production remains denied. Preserve #3's expanded creative source inventory and
policy-file identity exclusions inside owned workers. `refinement.current/capture` also
need bounded hashing/archival work. These are concrete integration dependencies; the
earlier #3 integration claim only covered f3d0f15. See
[the test log](validation/host-refinement-integration.txt). #2 must retain separate
technical/operational versus craft/fit/preference outcomes.

The host-worker Jev gate escalated (composite 0.580431818, safe-to-apply 0.14). It gave low
confidence to test counts and questioned the first measurement pair at 0.14 confidence.
An independent reviewer checked the original logs/images/native evidence and all 62 export
hashes, supporting those narrow observations. The broad escalation remains unresolved;
there is no automated merge recommendation.

## Owned sampling controls and export provenance

Profile/diagnosis loading and profile qualification evidence reads now run in the
owned host worker. Effective settings and explicit overrides cross the worker as
JSON, along with qualification, diagnosis and hashes of the exact control bytes.
The override regression uses a real synthetic profile instead of mocking internal
qualification functions. Its synthetic review labels are test inputs only.

Export now reads and hashes provenance and the delivered image inside its existing
owned worker. The manifest embeds the exact provenance bytes that were parsed,
without a later independent provenance read in the parent. Public-seam FIFO checks
reproduced blocked profile and export provenance calls taking 10.665 / 10.015 seconds
under six-second budgets. Their green single-test suites finished in 5.12 / 5.22 seconds;
these are test-suite durations, not precise render timings. The tests preserve prior
outputs and start no render attempt; diagnosis loading uses the same boundary.
The formerly undocumented macOS sysctl dependency now has an adapter and source-linked
BSD-3-Clause notice. Local checks passed **235 offline / 3 render / 48 doctor**,
plus lint and types. Final hooks and current-head CI are reported separately.

Whole-job hard bounds are still **partial**. Parent publication/manifest bookkeeping,
QA/provider work and #3 caller-side hashing/archival remain cooperative. Export also
has a pre-existing concurrent-input race between final-image hash verification and
its later image read; qualification does not cover concurrent edits to that source.
Owner-reviewed positive/degraded/held-out qualification remains incomplete. Nothing
in these operational fixes approves 0.02 or rates the cap-16 control.

Three additional production jobs are retained in
[controls-provenance-production.json](validation/controls-provenance-production.json).
One baseline overlapped offline tests and is excluded from comparison. The other
baseline/current pair ran sequentially after tests, at unchanged 4096 / 0.01, seed 0.
Complete invocation times were **46.44 / 48.91 s**; body times were **46.19 / 48.72 s**.
Each arm has actual Metal-only tracing, executed Metal OIDN, 4000→2000 delivery and
31 verified export hashes. The current manifest embeds the exact final sampling
record and matches its hash. Current dependency hashes match the measured source.
Module fingerprints bind the baseline to the starting revision and current to this source. One
observation per arm, unknown other machine load/cache and unmeasured later review
prevent distribution, speedup or visual-quality conclusions.

The control/provenance Jev gate escalated (composite 0.336, safe-to-apply 0.09),
questioning test counts and red/green claims at confidences 0.44 / 0.48, and labeling
the override claim unsupported at 0.67. An independent reviewer then read raw logs
and current source: counts are supported; exact failing-call durations differ from
the green suite durations as clarified above; override behavior is supported by the
real synthetic-profile test with mocked GPU execution. These narrow factual questions
are resolved by direct evidence; the broad escalation remains unresolved, without
automatic merge approval. See
[the raw gate](validation/jev-gate-controls-provenance.json) and
[review record](validation/code-review.md).

## Bounded final QA and provider operations

Finalization now binds a view of the original Jev client to the shared budget.
The parent retains request numbering and aggregate usage. HTTP retries/backoff,
response decoding, sent-image loading/encoding, tiny-image preparation, verified
asset persistence and CPU QA image checks use owned workers. Split/concurrent calls
share the deadline. Unsupported custom clients fail explicitly; other unbudgeted
judging interfaces keep their client contract. Default finalize timing begins
before setup, and an exhausted caller is rejected before reading finalists.

Public finalize regressions reproduced six-second budgets overrunning on provider
Retry-After (10.987 s call), CPU QA image reading (12.099 s), split-request image
encoding (10.247 s), and tiny-image preparation (10.098 s). The individual green
suites finished in 6.32 / 6.43 / 6.36 / 6.61 s, including fixture rendering/setup;
these are suite durations, not precise operation timings. Each retains the prior
winner. A separate regression caught a FIFO accepted as an existing judgment asset;
hash verification and atomic replacement repair it. Received answers/usage are
recorded before budgeted asset IO, whose request status remains pending if interrupted.

Local checks passed **241 offline / 3 render / 48 doctor**, lint/types. The explicit
`-m live` M5 final/export/finalize test passed: **one native attempt**, actual Metal
tracing and executed Metal OIDN, **4000→2000** output and **31 verified exports**.
The same budget covered all phases. Live judgments and CPU checks completed, while
finalize returned **sampling_review_needed**, retained the prior test winner and
left the profile unqualified. Five legacy QA pass verdicts do not establish owner
sampling/detail, craft or held-out acceptance.

Its measured body cost was **52.03 s**: render **45.92**, export **3.73**, final QA
**2.36**; the remainder is fixture/job/motif setup. This includes actual provider and
retained-image IO, but excludes pytest/import startup and later evidence-copy/review.
One request used 6275 input / 103 output tokens, client-recorded cost **$0.000264**
(potentially estimated), reconciled
against request records. One observation, unknown other workload/cache and missing
owner qualification prevent a performance or quality conclusion. The first live
invocation failed before GPU/API work because the test could not import its fixture
script; loading that local script explicitly fixed the test setup.

Whole-job hard bounds remain **partial**: parent input/QA bookkeeping, provider-log
publication, render/export staging/publication and refinement caller archival still
need hard deadline qualification. Interrupted provider completion/usage may be unknown.
No sampling control, GPU enforcement, owner label or numeric quality tolerance changed.

A separate same-setting render/export pair after the QA worker changes recorded
**47.19 s baseline / 49.38 s current** complete invocation; body times **46.96 / 49.15 s**.
Both ran sequentially after the checks, with explicit cap4096 / threshold0.01 / seed0.
Each has verified Metal tracing/OIDN, 4000→2000 delivery and 31 export hashes.
[Pair provenance](validation/qa-workers-production.json) and
[live shared-budget evidence](validation/qa-workers-live.json) keep their scopes distinct:
the pair excludes live QA; the live job includes it. One observation per arm,
unknown other workload/cache and no qualified replacement prevent a speedup or
amortized profile claim. Complete original calibration/confirmation costs remain
reported above; no extra search is required for normal concepts.

The preceding core `e8834a6` CI first failed the existing PWA export helper at300s;
an unchanged failed-job rerun passed (233passed/2skipped/3deselected). The exact
export test passed five focused local invocations. The intermittent root cause
remains unknown; a passing rerun is not a fix. This history stays separate from
new-source CI and from the budget regression fixes.

The QA worker auxiliary gate escalated (composite0.71975, safe-to-apply0.46,
test-gap confidence0.16). Its live GPU/export claim was unsupported at confidence0.20
with measurement-only evidence. An independent reviewer then audited the raw native
logs, original images, 64 current dependencies, 31 export hashes, both sent assets,
provider/usage/QA/prior-winner records, both comparison jobs and all check logs.
That audit supports the limited operational claim. Broad escalation remains open;
no automated merge or owner-quality approval is claimed. See
[raw gate](validation/jev-gate-qa-workers.json) and [review](validation/code-review.md).

## Judge identity reconciliation with #3

The first budgeted view hid model/endpoint metadata from #3's creative/comparison
cache key. Its public changed-model and changed-endpoint tests reproduced two
failures. Read-only forwarding of model/url fixes invalidation, including rebinding.
This eight-line backport is byte-identical with the shared client tested in
published #3 `2f0c5f228d35f8da923ec534c611219c9edc83c0`. Independent reasoning reviews
found no further issue in that small fix. Root offline241 and render3 checks passed
afterward. Pinned core318 hosted CI passed239/2skipped/4deselected in268.76s.

An independent source archive of the published #3 stack passed **50 tests / 2
render-live deselected** in73.76s. Its retained full run reports270/4, not independently
rerun here. Archive files were matched to Git blobs and the shared client was
compared byte-for-byte. [Execution provenance](validation/refinement-qa-integration.json)
and [subset log](validation/refinement-qa-integration.txt) preserve that scope.

The #3 stack also ran an actual shared-budget final/export/live-QA job with this
identical client:53.64s body (render/capture47.22, export3.81, QA2.33), one native
attempt,4000→2000,31 low-level exports and one request/two assets. The original
native logs, image/exports, source dependencies and sent assets were audited again;
finalize retained the prior winner and stopped at sampling_review_needed. See
[combined-path evidence](validation/refinement-qa-live.json). This is the combined
Issue #3 implementation, not a rerun of every later root file. The earlier root52.03s live
job and47.19/49.38 pair remain explicitly tied to measured core318. No new GPU
policy, sampling control or owner approval follows from forwarding judge metadata.

## Owner follow-up and additional glass studies

[Owner follow-up](validation/owner-review-followup.json) records actual answers with
figure/source hashes. The owner accepts the technical sampling detail of the left
4096 / 0.01 typography control **and** the cap-16 control. The latter is an accepted
low-sample example, not a negative control. The earlier 0.02 detail-loss rejection
remains unchanged. The shown matte, metal and different optics/glass 0.01 controls were
also accepted technically. These ratings do not imply craftsmanship, style preference
or approval of unshown briefs.

The owner requested three further glass samples. Independent seeds **44, 45, 46** used
archived checkpoint `8261315`, unchanged 4096 / 0.01 and the production 4000→2000/full-export
path. All native runtime and delivered-image hashes and **93 export hashes** were checked;
complete invocations were **64.14 / 63.16 / 63.50 s** (unknown cache/other workload; offline
checks also ran on the host). These are additional qualification cost, not a speedup trial.
[Retained job records](validation/glass-independent-20261110.json) bind the original EXRs,
images and sources under the persistent local bundle. The owner answered “they look good”
to their technical-detail question, then requested different shapes and lighting.
These jobs validate checkpoint 8261315, not the uncommitted deadline increment.

Three separately authored glass studies use an orbit/three-point rig, split prism/raking
rig and clover/top-flat rig. Their recipes and outputs are retained under
`/Users/nicolas/Documents/logo-maker-evidence/2026-11-10-issue5/glass-shape-lighting-20261110/`.
Geometry and lighting intentionally differ for the owner's requested studies; they are
not one-control sampling-repair comparisons. Their owner review remains pending.

The first auxiliary glass verification used a compound claim with incomplete dimensional
evidence and returned a low-confidence contradiction (0.61 contradicts, confidence 0.42).
The raw image dimensions, recorded floating-point controls and source/seed/export checks
were then supplied explicitly with separate claims. All three limited claims were verified
without contradiction; [verification](validation/glass-independent-jev.json). This is
factual verification, not visual approval or broad patch acceptance.

## Filesystem publication and current-source validation

The filesystem increment owns parent input/record IO, prior-record archival, copies,
staging, publication, cleanup and winner finalization. A three-second recovery reserve
stays inside the original deadline. A failed retry retains its prior active provenance;
pipeline export pins the exact qualified record through currency and worker snapshot
checks. CPU host work remains allowed. Fresh reviews found and closed three real gaps;
[review history](validation/code-review.md) and the new public failure tests retain the details.

Current runtime source passed **252 offline / 3 render / 1 actual GPU-live / 48 doctor**
checks; lint/types/hooks passed. The actual shared-budget job body took **52.42 s**
(render 45.94, export 3.77, final QA 2.70; fixture/setup is included). Raw records, all 65
source dependencies, Metal tracing/GPU OIDN, 4000→2000 delivery, 31 exports, the provider
request/two assets and prior-winner preservation were rechecked in
[the current-source audit](validation/filesystem-live-current.json). It stopped at
sampling_review_needed. This validates operations without creating a qualified profile.

The owner liked the orbit and prism studies and flagged angular clover reflections.
The bands exist before denoising. An exact-mesh probe found flat-cap shading normals
3.59–9.93 degrees from the geometric normal. A one-variable source-copy rerender changed
only cap smoothing, with identical mesh bytes, recipe, material, lights, seed 49 and
4096 / 0.01. The flat-cap probe reaches at most 0.02 degrees and removes the broad face
bands. The owner confirmed: “Yes, the face issue is resolved.” Edge/bevel faceting remains
unresolved. This is a shading/craft diagnosis, not a sampling escalation; the package's
geometry builder was not changed by this probe. See
[retained diagnosis](validation/clover-shading-diagnosis.json).

The three authored studies cost **76.30 / 83.06 / 142.06 s** complete invocation;
the cap-shading probe cost **106.69 s**. Their full 31-file exports were hash-checked.
These additional one-off costs are separate from the original calibration matrix.
Other host work and cache state were uncontrolled; no speedup is claimed.

## Scoped retained-baseline qualification

The owner explicitly accepted both held-out orbit and prism studies after reviewing
seeds 47/57 and 48/58 and their native noisy/GPU-denoised crops. Their current confirmations
cost 71.77/81.77 s complete invocation, including full exports. Native Metal/OIDN, 4k→2k
and 62 export hashes were checked. [Confirmation](validation/glass-heldout-confirmation.json)
and [verbatim labels](validation/owner-review-followup.json) retain their scope.

The qualified profile keeps **4096 / 0.01**, automatic minimum 0 and actual job seeds.
The 0.02 candidate failed owner detail review; cap 16 passed only its shown typography
case and lacks cross-material qualification. This is the least expensive fully demonstrated
suitable setting in the retained tested scope, not a global optimum. The profile's runtime
context agrees across the current live job and held-out confirmations. It covers only the
reviewed matte_plastic, polished_metal and clear_glass presets at final 4000→2000, and is
invalidated by runtime/package changes. Current-image and independent craft/fit/preference
gates remain necessary. No automated noise/detail acceptance tolerance was introduced.

Two fresh same-setting baseline/current pairs measured complete invocations
**47.20/50.09 s** and **46.93/50.20 s**. Current diagnostics and bounded bookkeeping add
cost in these observations; no speedup is claimed. The baseline is the isolated `38ba86b9ccff305cb453c46920824509ae989f76`
source with the same fixture and settings, while current runtime code matches 3d19e4a.
[Raw comparison](validation/filesystem-cost-current.json) includes all 124 export hash checks.
These timings include launch/import/render/denoise/output/full exports/shutdown; live QA,
offline qualification and later evidence analysis remain separate costs. Cache state and
other host load remain unknown. A normal job performs no candidate search; profile
qualification and independent-seed confirmations are one-off costs, never a free prelude.

A real normal final with this profile consumed the reviewed settings, reported qualified
and profile_baseline, made one native attempt and used the pinned-qualified pipeline export
path for 31 files. The operational fixture's winner was supplied only to exercise export;
artistic approval is not inferred. [Consumption evidence](validation/profile-consumption.json)
retains startup/preflight and whole invocation cost separately from its job body.

The fresh normal-profile check measured **51.29 s complete invocation**, including
profile/review preflight, process launch/import, fixture setup, render/denoise/diagnostics,
downsampling, qualified pipeline export, bookkeeping/publication, retained evidence and
process exit. Its job body was 51.15 s; the remaining 0.14 s covers preflight/startup/reporting.
A separate earlier consumption body was 50.34 s and remains retained with its narrower scope.
The earlier round's 14 complete invocations and two body-only checks total 1100.92 s of known
job latencies. This is not elapsed session wall or GPU active time. The original 25-job
955.51 s body total and intervening historical validation are additional. Authors' analysis,
review-sheet work and human review are unmeasured; omitted overhead is unknown, not zero.
[Cost inventory](validation/qualification-cost-inventory.json) lists each job and scope.
No amortized benefit is claimed.

The top-level `transfer_approval:false` / `qualified_profile:null` fields in the owner
follow-up record describe its initial typography-review epoch. Its later
`heldout_technical_acceptance` section supersedes that initial pending transfer state;
[the scoped profile](profiles/apple-m5-pro-final.json) is the current qualification record.
Likewise, raw confirmation measurements say owner review pending at capture time; the
later explicit owner acceptance is preserved separately. Historical fields are retained,
not relabeled as if approval preceded the measurements.

A final description-only profile metadata correction was followed by another real
consumption check: **51.75 s complete / 51.62 s body**, one native attempt and 31 pinned
qualified exports. The preceding 51.29 s invocation is retained as its own epoch. All 15
complete invocations plus two body-only checks now total 1152.67 s known job latency;
the inventory preserves both rather than overwriting spent qualification cost.

## Current-main requalification

The November 12, 2026 requalification used `b381d05` on Apple M5 Pro. The shipped
record returned `profile_stale` because the lockfile, package hashes and render settings
key had changed. Eleven current-main 4000→2000 jobs repeated the material, fine type,
dark and alpha controls, the 0.02 comparisons, and the held-out orbit and prism on seeds
47/57 and 48/58. Each verified exclusive Metal tracing and OIDN Metal denoising.
All 341 inspection export file hashes matched their manifests.

The owner approved the shown 4096 / 0.01 controls and held-out replays and rejected
0.02. The [November 12 review record](validation/m5-pro-main-b381d05.json) binds that decision
to the render, diagnostic and export evidence. The bundled profile retains its existing
three-material scope, automatic minimum and job seed. This qualification covers sampling.
Live creative, technical and export eligibility still apply to each production job.

## November 13 Apple M5 Pro activation

The owner approved the refreshed 4096 / 0.01 controls and held-out renders and rejected
0.02 for production. The [November 13 review record](validation/m5-pro-20261113.json) binds
that decision to 11 full render and export runs. All 341 export hashes matched. The
4096 / 0.01 profile passed preflight on the measured host.
A fresh seed-61 typography render used the profile's 4096 cap and 0.01 threshold in one
verified Metal attempt. The qualified sampling record was bound to the 31 verified exports.

The requested 8192 cap was tested at the same 0.01 threshold with automatic minimum,
matched scenes and matched seeds. Nine full runs verified Metal rendering and denoising.
All 279 export hashes matched. In the glass control, the median foreground sample count
was 80 at both caps, and the 99th percentile rose from 4096 to 6656. Full images,
native detail crops and the profile submitted for review are in the local
`logos/workflow-validation/sampling-20261113/cap-8192/Apple-M5-Pro-8192-Sampling-Review.zip`.
The owner approved these [8192 / 0.01 renders](validation/m5-pro-20261113-8192.json).
The [production profile](profiles/apple-m5-pro-final.json) now sets that cap for the
qualified Apple M5 Pro runtime and material presets. The 0.02 threshold remains rejected.
A fresh seed-61 typography render inherited both settings from the profile, used Metal
for tracing and denoising, and delivered a transparent 2000 px PNG. The sampling record
was bound to the export manifest, and all 31 export hashes matched.
