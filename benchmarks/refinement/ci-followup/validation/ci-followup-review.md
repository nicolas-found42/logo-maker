# Independent CI follow-up review

Reviewed the current delta from `64a342c`, the installed PWA browser installer/selection
implementation, and the named local evidence below. No concrete standards or practical
specification defect found in the CI/test-only follow-up. No runtime implementation or package
lockfile changes are present.

## Claim adjudication

- **Three named regressions pass locally: supported.** `ci-three-regressions-verbose.txt`
  explicitly records PASSED for `test_export_set_sizes_and_manifest`,
  `test_provider_timeout_keeps_pending_attempt_unknown_and_prior_output`, and
  `test_finalize_interrupted_winner_publication_restores_winner_and_run_state`: **3 passed in
  21.11s**. Use this named result rather than attributing names to the earlier terse 20.36s run.
- **The two fault regressions pass with deliberately delayed setup: supported with a provenance
  limit.** `ci-phase-green-verbose.txt` names both timeout/publication regressions PASSED: **2
  passed in 30.58s**. The inspected `/tmp/ci_phase_delay.py` plugin delays the relevant
  `pipeline.finalize` calls by 4.2s and 8.2s. `ci-phase-red.txt` names both tests FAILED in
  **15.41s**, including failure to reach the publication marker. These artifacts support the
  supplied delayed-setup reproduction; the verbose green log alone does not record plugin
  invocation, and this review did not rerun it.
- **Lint/format, type checks, and repository hooks passed: supported** by `ci-followup-lint.txt`,
  `ci-followup-types.txt`, and `ci-followup-hooks.txt`.

## Patch assessment and limits

The tests allow setup time, then shorten the same shared budget at the actual
transport/publication boundary; they do not replace or extend that budget. They retain fault-
reached, deadline, rollback, unknown-usage, and retained-asset assertions. CI provisions and smoke
launches PWA's selected, dependency-pinned headless Chrome before offline tests select its local
revision. Provisioning has a three-minute step timeout. The architecture contract matches this
behavior.

This supports addressing observed browser setup interference and tests expiring before reaching
their intended fault. It does **not** establish the exact cause of the historical PWA timeout,
hosted CI success, or a full offline-suite pass. The full offline run was still pending when this
review was requested.

## Advisory model escalation retained

`ci-followup-jev-gate.json` remains **escalate**, with `safe_to_apply = 0.29` and composite
`0.5785`; it marked the first two claims unsupported using the earlier terse logs. The named logs
above resolve that specific evidence ambiguity for this independent review. They do not change the
retained model result or constitute model approval. No model rerun was requested or performed.
