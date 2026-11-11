# Review against 38ba86b9ccff305cb453c46920824509ae989f76

Two independent agents ran the code-review skill against the starting revision. Initial
findings below were fixed and received focused independent re-review.

## Standards

Initial findings: alternate render dispatch contradicted the architecture contract;
per-finalist attempt ceilings were not persistent across QA rounds; new package files did
not invalidate reuse; source inventory was duplicated. Commit `21b8fe5` restores explicit
alternate execution outside Cycles qualification, adds a persistent finalist budget and
centralizes source/catalog inventory. The second pass found a publication deadline gap;
`85b6660` stages all copies and checks before/during commit with rollback.

Final focused review: the prior publication finding is resolved. Render artifacts are staged
before publication, budget is checked before and during commits, and failures restore prior
outputs. Backup cleanup occurs only after success, preserving recovery files if rollback
fails. Export publication likewise restores its prior directory on deadline failure.
No further material breach was found in these helpers by source inspection.

## Spec

Initial findings: explicit controls outside a profile's qualified settings could inherit its
acceptance; review-file changes were not checked on reuse; machine probing used a new deadline.
Commit `21b8fe5` gives mismatched settings an override-conflict state, hashes retained review
files and threads the shared deadline through freshness checks. The second pass found the
same publication issue; `85b6660` fixes it and adds a failing-before/passing-after regression.
Final focused review found the publication issue resolved and no other material remaining
bug in that focused pass.

External acceptance remains incomplete: owner sampling labels, calibrated tolerances,
owner-reviewed held-out briefs and a qualified profile. This PR uses Refs #5.

Final unresolved implementation findings: Standards 0, Spec 0 in focused re-review;
qualification gaps above remain open. Reviews were source inspection, not independent visual
sign-off or proof that every issue acceptance criterion is satisfied.

## Auxiliary completion gate

`jev-gate.json` retains a separate Jev gate that escalated rather than accepted automatically.
The review composite was 0.5685, safe-to-apply 0.18, with low confidence/test-gap and blast-radius
signals. It verified the test-count claim (0.98 confidence), but returned a low-confidence
contradiction on the 25-job GPU claim (verified .39 / contradicted .44 / unsupported .17).
This is not an automated review pass or a merge recommendation. The PR stays draft.

A subsequent deterministic audit (`artifact-audit.json`) read all 25 retained final images,
native logs, execution selections, and every exported file. All assertions passed: exclusive
Metal selection with CPU tracing off, Metal override, actual OIDN Metal logs matching their
hashes, 4000 px rendering, delivered 2000 px hashes, and full export-file hashes. Seeds 0/43
and the cap-16 control are present. This resolves the narrow operational fact mechanically;
it does not establish owner visual approval or overrule the broad automated review escalation.

An independent stronger-reasoner recheck also read the retained originals: all 25 operational
records and all 775 manifested export-file hashes match. There are 21 seed-0 jobs, four seed-43
jobs, 24 cap-4096 jobs and one cap-16 typography control. This supports the operational claim
without implying every job has an independent-seed counterpart or establishing quality approval.

## Final dependency and region fixes

Both reviewers found no material concern in the final focused fixes: custom bpy cannot
qualify/reuse images from source identity alone; decisions use the named reviewed region;
and runtime versions plus manifest/lock hashing invalidate stale contexts. New public-seam
regressions were observed red then green, and the actual M5 runtime-profile test verifies
image-processing library identity. Final offline tests passed 224; GPU/adapter/profile
checks passed 3. The additional production smoke is retained separately from the cost matrix.

The final Jev gate (`jev-gate-final.json`) rechecked the changed implementation and new
evidence. All four limited completion claims were verified (none contradicted/unsupported),
with low confidence remaining on the operational artifact claims. The broad patch review
still escalated: composite 0.583640625, safe-to-apply 0.14. It remains a review-needed signal,
not an automated acceptance or merge recommendation. Owner qualification remains open.

## Export cleanup and owner feedback follow-up

Both reviewers rechecked the owned-process cleanup change. Standards found that grace must
follow group liveness after Python exits; Spec found cleanup must also run on inner-tool
failure. Both findings were fixed. The delayed launcher-hook regressions failed before the
fix and pass afterward for timeout and inner failure, preserving prior exports. Both final
focused reviews report no further actionable findings. Claims remain limited to owned
POSIX sessions and supported launcher cleanup hooks. The earlier hosted PWA timeout has
unknown root cause; an unchanged successful rerun does not prove this fix resolved it.

Final checks: 226 offline tests and 3 render/adapter/runtime checks pass; lint, types and
hooks pass. Four later production smokes remain separate from the original cost matrix.
The owner rejected threshold 0.02 in the shown typography/glass comparisons. This replaces
the agent's provisional visual assessment. The cap-16 control is unrated; no positive or
held-out profile qualification is inferred. The prior broad Jev escalation remains retained.

The narrow final cleanup Jev gate also escalated (composite 0.63125, safe-to-apply 0.19).
All three limited claims were verified; the test-count claim confidence was 0.79, below
its 0.8 automatic threshold. No claim was contradicted or unsupported. This does not
replace the broad gate or establish automatic acceptance. See `jev-gate-cleanup.json`.

## Hosted macOS process-state correction

Both independent reviewers found no actionable issue in the focused EPERM correction.
The adapter, docs, notices and bounded ID/state inspection follow the contract. Real
zombie/live process regressions were observed red then green. Offline 228 / render 3 /
doctor47 checks pass. The Jev gate-process-state result escalated composite0.56225,
safe-to-apply0.24; it also returned a low-confidence contradiction on the red/green and
pending-hosted claim. The independent Spec reviewer then read the exact retained red and
green logs and confirmed the claim: both parameter cases failed before; eight export
tests passed afterward. This resolves the narrow factual question independently, without
overruling the broad review escalation or asserting hosted success.

## Lifecycle fixture timing re-review

Both reviewers approved the tests-only allowance for slow hosted setup: 20-second test
budget and 60-second fake-browser lifetime preserve the lifecycle regression. Production
settings and budgets are unchanged. Final offline228, lint/types/hooks pass. The narrow
test-timing gate remains escalated (composite0.82275, safe-to-apply0.61); local-check claim
verified.98, tests-only/pending-hosted claim unsupported. No hosted pass is inferred.

## Owned host stages: fresh Standards and Spec reviews

Fresh independent agents reviewed the approved starting revision plus the current host
delta. Standards: no hard documented violation; optional typed RPC records if the small
protocol grows. Spec: no new actionable mismatch in owned config/compile/dependency/image/
cache work; whole-pipeline and qualification requirements remain partial. Both endorse
explicit callback conflict with returned asset records, rather than pickling side effects.

The new gate escalated composite0.580431818, safe-to-apply0.14. Test-count confidence.26;
the first M5 pair was questioned at confidence.14. The independent Spec reviewer then
read original logs:232offline/3render/47doctor, observed48.762266417/51.067629958s, Metal
only/MetalOIDN4k, delivered2k and all62export hashes match. This resolves the narrow factual
question, not the broad review signal, timing reconstruction or visual qualification.
A second instrumented pair binds the baseline module to the starting revision and measures outer
invocations; details and scope are retained separately.

PR #8 integration was checked in a temporary merged archive, without branch mutation:
2failed/255passed/3deselected. Inspection mode must be carried into the cache worker, and
creative dependency/policy-file semantics preserved. #3 current/capture archival remains
unbounded. These are explicit integration gaps, not a passing combined-stack claim.

The separate invocation-measurement delta gate verified its narrow claim at confidence0.64
but escalated (composite0.85875, safe-to-apply0.58) for low-confidence test coverage. Its
actual measurement files, source fingerprints and timer scope are retained. It does not
replace any earlier gate or supply performance/visual qualification.

## Owned sampling controls / export provenance follow-up

Fixed point remains owner-approved `38ba86b9ccff305cb453c46920824509ae989f76`.
Fresh parallel Standards and Spec agents reviewed the branch and working increment.
Standards found a missing sysctl adapter and stale sampling documentation; both
were repaired, and its follow-up found no unresolved finding. A repeated settings
key tuple was reduced to one local declaration during review.
Spec found no new incremental regression; it independently ran the real synthetic
profile override and stalled-export-provenance checks (2 passed in 6.64 s).
It noted the existing concurrent-final-input read/hash race. That is retained as
an unresolved qualification gap, along with parent publication/QA/provider bounds.
Offline tests and synthetic owner labels do not prove Metal execution or actual
owner/held-out qualification. No full-issue completion or merge approval is claimed.

Jev follow-up: composite 0.336, safe-to-apply 0.09; two factual claims were labeled
contradicted at confidence 0.44 / 0.48; override support was labeled unsupported at 0.67.
The independent Spec reviewer audited actual raw logs and current source without
rerunning tests. It confirmed 235 offline / 3 render / 48 doctor, lint/types/hooks;
red timed calls 10.665 / 10.015 seconds; green *test-suite* times 5.12 / 5.22 seconds.
It confirmed synthetic max_samples=1 survives a reviewed-profile cap4096 request,
with override_conflict/review_needed and stale-review invalidation assertions.
The factual contradictions are inconsistent with direct records. Precise render-time
claims were corrected to test-suite durations. Broad review escalation remains open.

## Final QA/provider worker increment

Fresh parallel Standards and Spec reviews used the owner-approved fixed point
`38ba86b9ccff305cb453c46920824509ae989f76`, including the working worker module.
Standards found no blocking documented breach. Its two ownership smells were
repaired: general orchestration is now host.run, with render's legacy private
alias retained, and client-owned helpers update asset-log schema/status.
Spec found no new confirmed defect. Default finalize setup is now charged from
entry; an exhausted caller fails before finalist loading. Input/log/publication
work remains cooperative and whole-job hard qualification remains incomplete.
Both reviewed the opt-in live test and its limits. Actual source-frozen execution
then passed: native Metal/OIDN/full exports plus live provider QA, returning
sampling_review_needed with an unqualified profile. Owner approval is not inferred.
The measured request usage reconciles against parent records, and only one native
attempt occurred. New code does not claim qualified profiles or held-out acceptance.

The QA worker Jev gate escalated: composite 0.71975, safe-to-apply 0.46,
test-gap confidence 0.16. Counts were verified at 0.79; timing at 0.91.
The live GPU/export claim was labeled unsupported at confidence 0.20 because
its supplied evidence only contained the measurement and paths, not raw native
records. An independent reviewer then audited the originals: Metal OIDN RT filters
at 4000 square, 2000 delivery, log/execution hashes, all 64 current dependencies,
31 export hashes, exact embedded sampling record, one request/two retained assets,
usage, sampling_review_needed and prior winner retention. It also checked both
pair originals and the 241/3/1/48 logs. These support the limited factual claim;
the broad escalation remains unresolved and is not automatic merge approval.

### Integration identity follow-up

Issue #3 found that the new budget view omitted model/url, collapsing distinct judges'
creative/comparison cache identity. Two public regressions reproduced the defect;
the exact eight-line forwarding patch is now backported. Both reviewers checked
this follow-up and found no additional issue; Spec also checked dynamic forwarding
through rebinding and read-only assignment failures without network calls.
The complete client source is byte-identical with published2f0. Root241offline and
3render passed after the patch; independently extracted #3 subset50/2 also passed.
The combined M5 final/runtime and its actual original logs/hashes were audited,
while the root31852.03s live run remains labeled at its measured revision.

The small identity backport's separate gate verified all three limited claims,
without contradictions/unsupported claims, but escalated broad uncertainty:
composite0.83325, safe-to-apply0.68, test-gap confidence0.24, blast-radius confidence0.
Identity/source claims retain review confidence0.76/0.50; check counts0.80.
Independent source comparison, Git-blob verification, the public integration tests
and both reasoning reviews support these narrow facts. This is not a new broad
approval of the complete sampling feature or its incomplete qualification.

## Whole-job filesystem follow-up from 8261315

Fresh code-review skill agents reviewed `8261315...b0b79ab` separately.
Standards found one hard breach: recovery's random quarantine destinations were absent
from the journal, contrary to the documented discoverability contract. Recovery now uses
predeclared journal paths, and cleanup includes them. The dictionary transaction protocol
was also flagged as a possible Primitive Obsession; this is an optional heuristic, not a
hard repository rule.

Spec found two P1 issues. Failed-render finalization replaced restored active provenance
with a `published=false` failure record, leaving the old PNG present but unusable through
normal currency/export checks. Failure evidence now uses a separate report when a published
active record exists. A public render/retry regression checks byte-identical prior pixels
and active provenance, a separate failure report, and successful current-artifact validation.

The second finding was a qualification race beyond the final-image byte race: pipeline
qualification could precede a concurrent unqualified or missing sidecar, which low-level
export allowed as inspection/legacy data. Pipeline now pins the exact qualified record hash
through current-artifact validation and into the snapshot export worker. Public pipeline
regressions substitute unqualified/missing records after the check and verify rejection and
preserved prior exports. The original hash/decode regression still exercises a concurrent
live-final replacement after hashing.

Seven focused review-fix/publication tests passed in 21.64 s. Fresh re-review and final
current-source checks remain pending. The earlier 249-test run and three GPU regression
checks retain their original source scope; new glass studies use archived 8261315.

Both fresh follow-up reviews closed the findings at `3d19e4a`. Standards confirmed
journaled quarantine paths and found no new documented breach in the focused fixes.
Spec independently ran the three public active-provenance/qualification race cases:
**3 passed in 2.46 s**, and found no additional actionable issue in that delta.
The optional dictionary protocol maintainability observation remains nonblocking.

Current-source offline validation then passed **252 tests / 4 deselected** in 147.50 s.
The actual final/export/live-QA check passed **1 test** in 52.59 s. Its 52.42 s job body
contains one native attempt, 4000→2000 delivery, 31 exports, one provider request/two
retained assets, reconciled usage, sampling_review_needed and prior-winner retention.
A fresh raw audit matched all 65 dependencies to the current runtime source, native
Metal/OIDN logs and hashes, every export, both sent assets and the prior winner.
This is operational validation; qualification and owner artistic approval are not inferred.

The two final subset Jev gates preserve the complete (untruncated) filesystem and
QA/provider deltas. All three limited factual claims were verified without contradiction,
but both broad reviews escalated: safe-to-apply 0.20, composites 0.65775/0.593,
correctness confidences 0.34/0.13. No automatic merge approval is inferred.
The Spec reviewer then independently audited the original current files—not just the
report—and confirmed all 252/1 check counts, native Metal/OIDN execution, 65 dependencies,
31 exports, two sent assets, usage and prior-winner preservation. It found no concrete new
implementation gap in that audit. This supports the limited facts; broad uncertainty and
profile qualification remain separate. See `jev-gate-filesystem-filesystem.json` and
`jev-gate-filesystem-qa.json`.
