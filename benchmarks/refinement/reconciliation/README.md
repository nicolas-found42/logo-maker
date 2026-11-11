# Main reconciliation and creative studies

This evidence qualifies the reconciled implementation, not approved artwork. Issue #3 stays open.
The audited branch was `beef788`; this change incorporates main at `c20884b`, including the later
sampling fixes, CI repair, craft eligibility and frozen brief/plan infrastructure. No separate
checkpoint branch was merged.

## Implementation

Frozen requirements, their source evidence, reviewed plans and construction intent now participate
in creative revision snapshots. Preview selection and final tournaments require independent craft
eligibility and creative readiness. All eligible final candidates are rechecked around ranking;
exports retain main's exact sampling/winner snapshot checks and recoverable publication.

Blocking refinement hashing, input validation, inspection/comparison preparation and revision
archival use the shared owned CPU boundary. Archives and active render state publish through the
recovery journal. No nested fresh machine-probe session is started inside the owned export worker.
Main's failed-rerender sidecars, prior active provenance, provider accounting and read-only
model/endpoint forwarding remain intact. Custom-bpy previews remain inspectable; unknown custom
file dependencies still deny production reuse.

Optional per-component `smooth = false` and per-material `tangent = [1, 0, 0]` let authored
supported
assets retain planar faces and a deliberate brushing direction. Existing defaults are unchanged.
The metal tangent removes the earlier radial cap highlight without changing roughness, anisotropy,
lighting, seed or sample cap. New bevel artifacts around mounting eyes remain unresolved.
Requirement-support questions now include mandatory, preference, prohibition or open-choice scope;
an avoided property must not be interpreted as a required positive property.

## Observed validation

| Check | Observed result |
| --- | --- |
| `just test` | 423 passed, 6 render/live tests deselected; 49 upstream NumPy/skimage warnings |
| `just lint`, `just type`, `just hooks` | Passed |
| `uv build` | Wheel and sdist built |
| `just render-example` | 2 passed; actual Cycles Metal regression retains SSIM ≥ 0.90 |
| `just doctor` | 48/48 checks passed |
| Explicit live final-runtime test | 1 passed in 68.09 s; actual 4000→2000 Metal/OIDN render, 31 low-level exports and one live QA request |
| Historical evidence verifier | 20 revisions and 158 authored-source files verified; original evidence preserved |
| Reconciled evidence verifier | Three rendered cases, exact source/image hashes, exclusive Metal tracing and executed OIDN Metal logs verified |

The final-runtime fixture uses canned brief/plan answers solely for its synthetic sampling fixture.
Its QA request is live. It stops at sampling review and preserves the prior winner; its low-level
exports are not artistic or pipeline export approval. Actual live brief, plan, creative and revision
comparison requests for the paper/metal studies are separate evidence.

Offline coverage includes changed sources, model/endpoint invalidation, preview-only custom
inspection, blocked hashing/archival/comparison IO, publication recovery, sampling stops, provider
accounting, exact export snapshots and preservation of prior winners/exports. The source hashes in
`validation/source-binding.json` identify the implementation and tests behind this run. Historical
270-test results do not qualify this head.

Jev verified all four submitted evidence claims, but its per-file patch review escalated with
`safe_to_apply = 0.23` and composite `0.596`. Correctness/test-gap uncertainty remains an open review
limitation, not an approval. See `validation/jev-gate.json`. The PR remains a draft.

## Creative outcomes and gaps

| Rendered alternative | Creative craft / fit / material / description | Distinct from retained study | Prior critique resolved |
| --- | --- | --- | --- |
| Joined paper modules | .15 / .49 / .36 / .41 | .95 | .22 |
| Open-space paper study, last rendered revision | .12 / .68 / .23 / .30 | .97 | .41 |
| Metal keyed receiver assembly, structural follow-up | .17 / .94 / .33 / .63 | .95 | .56 |

These are genuinely different visual constructions, not additional text/material combinations.
The original folio and arch descriptions, renders and source histories remain retained. New concepts
have their own current descriptions. Replays after implementation changes are not new design ideas.
The metal follow-up actually cuts matching key receivers and mounting eyes into its supports.
Its current inspection explicitly retains unresolved local edge/shading critique.

A further paper source revision replaces the near-enclosing upper tips with steep outward folds and
laminated pale cores. Its construction plan became settled after the fold/layer interfaces were
specified, but mandate preservation remains uncertain: the brief requests parts framing an open
shared space while also banning a frame. `snapshots/paper-proposal-blocked/review.json` retains that
stop. This proposal has **no render**, and its active sources no longer match the last paper image.
It cannot supply a finalist, winner or export. The owner's interpretation has been requested.

No current study passes creative readiness; no owner artistic approval, qualified finalist or
production export is claimed. Distinctness and a successful runtime test do not resolve these gaps.

## Evidence boundaries

Run `uv run --locked python scripts/verify_reconciled_refinement.py` to verify this public subset.
`manifest.json` binds retained files and maps every recorded source hash to a content-addressed
snapshot or an existing pinned craft reference. Text source blobs retain their original bytes under
`.txt` names. Render revisions keep
source, image, execution, sampling, inspection, judgment and comparison identities separate.
Original absolute job paths in the records are provenance, not portable replay locations.

Full jobs, build attempts, authored but blocked sources, sent-image assets and historical runs
remain
under the ignored `benchmarks/refinement/local/` directory. This public subset supplements the older
`benchmarks/refinement/evidence/` bundle and does not replace it. Hosted CI and the saved PR's
actual
rendered description are checked separately after pushing and retargeting PR #8 to main.
