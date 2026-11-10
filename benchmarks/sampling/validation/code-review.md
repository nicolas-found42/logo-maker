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
