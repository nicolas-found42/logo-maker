# CI browser setup and timeout-fault follow-up

The first main-targeted run for `64a342c` failed: 3 failed, 431 passed, 2 skipped and
6 deselected in 900.86 s. [Failed run](https://github.com/nicolas-found42/logo-maker/actions/runs/42989491071).
The complete offline-test portion of its log is retained in `validation/ci-failed-64a342c.txt`.
No historical passing retry is used to dismiss that failure.

## Observed failures and repairs

Two tests supplied 4/8-second whole-job budgets, then asserted that a provider/publication fault
had been reached. The hosted run expired during preparation. A controlled delay before finalization
reproduced both missing-fault assertions: 2 failed in 15.41 s. Both tests now allow cold preparation,
then shorten the same existing deadline at the target phase. They do not create a fresh budget or
extend the original deadline. Real provider/rename faults, cleanup timing, pending usage/assets and
previous winner/run/export bytes remain asserted.

The controlled delayed-setup loop now passes both tests in 30.58 s. A verbose run of the three
specific hosted failures passes in 21.11 s. The named test identities and raw results are retained;
`delay-plugin.py.txt` records the exact delay injection used for the red/green reproduction.

PWA export hit the previously observed 300-second helper timeout. Inspection of the installed,
locked dependency shows that its system-Chrome path uses the default profile and may fall back to
a browser download. The failed log does **not** prove which browser step blocked. CI now provisions
the dependency's exact preferred headless Chrome revision and smoke launches it during dependency
setup, with a three-minute setup limit. Offline tests use the upstream `PAG_USE_LOCAL_REV=1` option
to select that installed revision, which Puppeteer launches with a private profile.

A controlled nonresponsive system-Chrome executable reproduced a bounded stop in 7.09 s; changing
only the upstream cached-browser option generated actual PWA icons in .66 s. The 512 px output was
checked. The probe and output are retained, without claiming to recreate the historical runner's
exact cause. Browser revision `156.0.8078.47` was installed and launched locally by the same setup
script used in the workflow.

## Scope and validation

No `logo_maker/`, JavaScript helper, dependency lock or package configuration byte changed from
`64a342c`. The actual creative renders in the [review snapshot](../review-followup/README.md) retain
their source bindings and artistic limitations. This follow-up changes CI setup, two tests and
supporting documentation/evidence. Issue #3 remains open and the PR remains a draft.

Fresh lint/format, ty, hooks, doctor, wheel/sdist build, GPU regression and the authorized live
final-runtime test passed. GPU regression: 2 passed in 5.83 s. Live final-runtime: 1 passed in
67.10 s; 31 low-level exports and one live QA request, then `sampling_review_needed` with the prior
winner preserved. The complete offline rerun passed: **436 passed, 6 deselected, 49 warnings in 319.38 s**.
`validation/current-source-binding.json` pins this run, including the updated tests and workflow.
Hosted results are recorded separately in the final PR body.
Raw local logs and fresh runtime measurement are retained in `validation/`.

The independent Standards/Spec reviewer found no defect in the CI/test delta. The incremental Jev
gate escalated (`safe_to_apply .29`, composite `.5785`), verifying lint/types/hooks but marking the
two terse test-log claims unsupported. Additional verbose logs identify every passing target.
The escalation remains an advisory limitation, not approval. The earlier `.05` refinement gate
and its independent adjudication remain in the review snapshot; this does not replace them.

The full ignored jobs, runtime exports, failed CI log and PR inspection captures remain under
`benchmarks/refinement/local/`. No owner artistic approval or production qualification is inferred
from browser setup, distinctness or passing runtime tests.
