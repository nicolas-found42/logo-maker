# Reviewed publication and creative follow-up

This snapshot follows `020e1d2`, incorporating main `c20884b`. It records current implementation
validation and actual renders. Issue #3 stays open: distinct artwork is observable, but creative
readiness and production qualification have not been achieved. Historical snapshots remain intact.

## Review fixes

### Standards

Revision history now excludes private `.archiving-*` and `.publishing-*` stages. The architecture
promises that unpublished archives are not visible. A failing regression on `020e1d2` demonstrated
the breach; the new history test passes. The independent Standards review found no residual
violations in the reviewed delta.

### Spec

The independent Spec review reproduced edits during winner publication displacing the prior winner
with stale evidence. Publication now checks frozen creative, craft, source, inspection, judgment
and export/sampling evidence after staging and after renames. A conflict restores the previous
selection/exports and run record within the original owned-operation deadline and recovery reserve.
The guard executes inside the existing worker, with no fresh deadline or nested worker session.

A second reproduction changed an inspection between refinement and preview selection. Preview now
carries the exact admitted inspection and judgment proof, instead of recomputing an approval from
new bytes. Inspection content and hash come from one owned snapshot. Retained render bytes are
also rechecked. The independent Spec review reported no residual findings in this delta.

`validation/publication-history-red-020e1d2.txt` retains two real baseline failures. The final suite
adds 13 regressions, including edits during staging/after renames, stale preview approval, blocked
guard reads and previous winner/finalist/export/run preservation. No claim of filesystem locking
against later user edits is made; subsequent edits invalidate future reuse.

## Fresh validation

| Check | Observed result |
| --- | --- |
| `just test` | 436 passed; 6 render/live tests deselected; 49 upstream warnings |
| `just lint`, `just type`, `just hooks` | Passed; raw logs under `validation/` |
| `uv build` | Wheel and source distribution built; setuptools license-table deprecation warning |
| `just render-example` | 2 passed in 19.93 s; actual Metal/OIDN regression |
| `just doctor` | 48 checks passed |
| Authorized live final-runtime test | 1 passed in 73.30 s |
| Live creative/comparison paths | Actual image-backed calls for both paper alternatives; metal unresolved-critique stop and live comparisons retained |

`validation/source-binding.json` binds runtime and test source bytes for this run. Offline coverage
includes source/model/endpoint invalidation, preview-only custom inspection, shared-deadline
hashing/archival/cleanup, sampling stops, owned accounting, publication recovery and exact export
snapshots. Historical 270-test results do not qualify this head.

The live runtime fixture delivered 4000→2000 with exclusive Metal tracing and executed OIDN GPU
denoising, verified 31 low-level export hashes and sent one live final QA request. The measured
body took 73.15 s: render 63.49 s, exports 4.73 s and finalize/QA 3.87 s. It stopped at
`sampling_review_needed` and retained the prior winner. Brief/plan answers for this synthetic
runtime fixture were canned; the QA request was live. This proves a runtime path, not artistic
acceptance or qualified pipeline export. Kernel cache state is unknown.

The final incremental Jev gate escalated (`safe_to_apply = .05`, composite `.3365`) and
flagged three claims as contradicted without a factual explanation. The independent Spec reviewer
checked the raw logs and all 92 current source bindings: all four validation claims are supported,
with no factual contradiction or new concrete defect identified. The advisory escalation remains
an unresolved review limitation, not automatic approval; raw gate and adjudication are retained.
The PR remains a draft.

## Owner scope and actual artwork

The owner clarified: “Open paper structures are allowed, without an enclosing border or backing
plate.” Exact clarification, original brief and the scoped current source are retained under
`snapshots/paper-owner-scope/`. The revised brief and plans passed live review. Earlier frozen
briefs, plans, renders and current concept descriptions remain in the ignored jobs and preceding
content-addressed snapshots.

The paper open-space revision is now rendered: laminated pale cores, outward-folded upright leaves
and a bent lower assembly surround an open space. There is no backing plate or enclosing border.
The metal study has real matching receiver cutouts, through mounting eyes and a separately seated
copper key. These are authored supported mesh assets, not unknown custom-bpy dependencies.

| Current render | Creative craft / fit / material / description | Distinct from original retained study | Original critique resolved |
| --- | --- | --- | --- |
| Joined paper modules `0006-1d90c6828729-preview` | .16 / .47 / .37 / .39 | .95 | .26 |
| Laminated open paper `0005-cc05c44adb56-preview` | .20 / .64 / .46 / .60 | .96 | .65 |
| Metal keyed receiver `0007-f95d050b17c4-preview` | Blocked by unresolved mounting-eye edge/shading critique before creative readiness | .95 | .42 |

The new laminated paper geometry scored .82 distinct from its preceding paper source revision.
Source-identical replays after runtime changes score .01–.02 distinct and are not counted as
new visual decisions. Neither distinctness nor a resolved brief ambiguity qualifies weak artwork.
The metal inspection preserves its unresolved triangular light/dark patches near mounting-eye
bevels. No finalist, winner, production reuse, export qualification or owner artistic approval is
claimed. Custom-bpy remains available for preview inspection; unknown dependency inventory denies
production reuse.

## Evidence boundaries

Run `uv run --locked python scripts/verify_reconciled_refinement.py` to verify both integration
snapshots. The manifest maps every retained source hash to an exact blob or an existing pinned
reference; shared blobs are reused rather than duplicated. Source text retains original bytes
under `.txt` names. Native execution logs, sampling profiles, images and live provider requests
remain separate artifacts. Absolute paths are original provenance, not portable replay locations.
The metal inspection stop intentionally produces no creative-readiness judgment for this render.

Full jobs and prior histories remain under ignored `benchmarks/refinement/local/`. This public
subset records the observed limits; hosted CI and the final saved PR layout are verified separately.
