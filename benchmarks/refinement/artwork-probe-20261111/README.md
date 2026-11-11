# Post-merge artwork probe

Refs #3. These actual previews follow main `90ed214`, after PRs #8 and #10 merged. They preserve
failed qualification as evidence. Issues #1, #3 and #4 remain open; no owner approval, finalist,
winner, qualified sampling profile or production export is claimed.

## Metal structural repair

The keyed-release construction now uses explicit planar caps and chamfer bands in three closed,
consistently wound supported meshes. No Blender bevel modifier or averaged PLY vertex normals
is used. A copper waist has wider front and rear shoulders that overlap the steel receiver arms.
The native Metal/OIDN preview is `0008-b02f721c0b4e-preview`.

The four bore areas no longer show the large triangular cap shading patches seen in `0007`.
The retained live comparison scores that local critique resolved at .92 and distinctness at .76.
Against the original retained arch, distinctness is .95 and critique resolution is .71. These
judgments do not establish overall qualification.

Creative craft, brief fit and material intent pass at .72, .82 and .70; description match remains
uncertain at .53. The separate execution-quality comparison against both owner-accepted Chief
references, in both orders, remains **unsettled**. Most craft dimensions remain uncertain. Fit
passes seven dimensions, with intended appearance uncertain; technical aliasing is also uncertain.
The explicit local repair did not close the reference-relative craft gap.

A more literal visible description and dimensioned plan were proposed next. Their construction
review remained uncertain, so they were not rendered through a lower-level bypass. Their sources
and review journal are retained under `unrendered-proposals/metal/`. The current sources were
restored exactly to the source-bound `0008` render and its passing plan; its uncertain description
judgment is retained.

## Paper replay and unrendered proposal

The owner permits open paper structures without an enclosing border or backing plate. The current
open-space paper source remains the laminated outward-folded construction from `0005`.
Consolidating the checkout changed its renderer context, so it received a native replay,
`0006-cc05c44adb56-preview`. This is **not** a new visual decision: comparison scores .01 for
distinctness and .05 for critique resolution. Creative craft / fit / material / description are
.18 / .64 / .48 / .61. The independent Chief craft-floor comparison **fails** in both orders
against both references. Shared-core small-size checks pass; several fit dimensions and technical
aliasing/detail preservation remain uncertain.

A structural proposal replaced variable vertical extrusion thickness with constant normal stock,
rounded scores and two paper lap contacts. Its construction plan remained uncertain; an earlier
version also left mandate review uncertain. These proposals were not rendered or counted as
visual alternatives. The final unrendered concept, construction-intent and plan records and the
full review journal are retained under `unrendered-proposals/paper/`. The unrendered meshes and
authoring recipe remain in the original ignored evidence directory. Current rendered sources
were restored exactly; their complete source and render histories remain intact.

## Independent eligibility and evidence limits

These focused refinement jobs originally had empty metaphor pools. Their first production-
eligibility calls correctly stopped with `missing_evidence`, rather than supplying a craft pass.
New text ideation supplies 20 metaphors per brief and 480 live fit-scored pool combinations per
case. Both current concepts are included. This metadata is separately retained under each case's
`ideation/`; it does not establish 20 rendered alternatives or retroactively describe old work.
The subsequent independent eligibility outcomes are metal **unsettled** and paper **fail**.

The manifest binds two renders, exact authored/runtime source blobs, native GPU execution logs,
sampling sidecars, current inspection, live creative/comparison and craft/fit/technical requests,
and every retained provider image. Shared source and image blobs refer to earlier immutable
bundles. `matches_active_sources` describes capture-time source identity; this archive does not
promise future machine-context eligibility.

Run `uv run --locked python scripts/verify_reconciled_refinement.py` to verify all three bundles.
Fresh post-merge main CI is
[43003865338](https://github.com/nicolas-found42/logo-maker/actions/runs/43003865338). That green
software CI does not qualify either artwork.

## Fresh software validation

These are the probe's original `5518ce5` runtime/test-source results. Subsequent process-cleanup
hardening and fresh head checks are reported in
[PR #11](https://github.com/nicolas-found42/logo-maker/pull/11).
Archived source bindings do not authorize reuse after implementation changes.

| Check | Observed result |
| --- | --- |
| `just test` | 436 passed, 6 deselected, 49 upstream warnings in 313.00 s |
| `just lint`, `just type`, `just hooks` | Passed |
| `just render-example` | 2 passed in 6.32 s; actual GPU regression |
| `just doctor` | 48/48 checks passed |
| `uv build` | Wheel and source distribution built |
| Explicit live M5 final-runtime test | 1 passed in 64.34 s |

Raw logs and exact tested source hashes are under `validation/`. The separate synthetic runtime
fixture delivered a fresh 4000-to-2000 Metal/OIDN image, verified 31 low-level export hashes and
sent one live final QA request. It stopped at `sampling_review_needed` and preserved the prior
winner. The measured body took 64.22 s, including 55.31 s native render, 4.40 s exports and 3.72 s
finalize/QA. Kernel-cache state is unknown. The synthetic fixture uses canned brief/plan answers;
its QA request is live. Its complete native/render/request evidence is under
`snapshots/final-runtime/`. Neither artwork case has a qualified final or export.

The advisory Jev gate escalated at safe-to-apply .69 and composite .79125, with low test-gap
confidence. It verified three claims and left the paper-provenance claim unsupported at low
confidence. Independent Spec adjudication checked all 98 paper source hashes between `0005` and
`0006`, the raw comparison, failing craft checks and hash-bound unrendered plan journal: that
claim is supported, with no concrete defect found. The gate was not repeated. Raw gate output,
final Standards/Spec reviews and adjudication are retained under `validation/`; advisory
uncertainty is not relabeled as automatic approval.
