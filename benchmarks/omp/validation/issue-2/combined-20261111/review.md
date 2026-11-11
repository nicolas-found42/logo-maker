# Independent combined-stack review

Base: main `3ca26d0`. Source checkpoints: `6ae0bba`, `184ee39`, `d9be955`.
Two independent code-review agents reviewed Standards and Spec separately.

## Standards

The initial review demonstrated that stripping essential answers from a current cached proof
still passed export validation. `_validate_proof` now recomputes craft, fit, technical and
actual-obligation checks. Four deletion/contradiction regressions passed. A follow-up caught
reference multiplicity collapsing to a set; `Counter` and a repeated-reference test repair it.
The reviewer verified all five cases and found no remaining blocker in that focused change.
A duplicate Noul-validator shape remains a possible maintainability smell, not a hard violation.

The actual Shared Chamber GPU render exposed a mesh-path integration defect. The verifier now
resolves mesh inputs using the compiled scene's build directory. Independent review confirmed
this matches Blender's input recording; the regression also rejects changed mesh bytes.

## Spec

The initial review demonstrated that a bounded provider timeout could leave no request or usage
record. The client now persists an unknown-cost `submission_pending` attempt before dispatch;
completed or failed responses amend that same request ID. Sent image assets are stored by an
owned worker before dispatch. The real local HTTP timeout regression verifies retained image
hashes, unknown usage and preservation of prior winner, exports and improvement floor.
The reviewer confirmed the original finding is fixed. No additional scope creep was established.

## Qualification limits

These are source and offline reviews, not owner approval of artwork or universal image-model
calibration. The fresh live suite has one failed Chief self-control and two passes. Cross-treatment
and original-appearance controls remain unsettled. Rootshare has no eligible final; Skill Swap
is development data, so neither supplies an untouched transfer. Use Refs #2 and keep it open.

Three Jevgrep discovery calls across the parent and reviewers had no reported price. The ledger
retains them within its explicit unknown-cost reserve rather than assigning zero cost.
