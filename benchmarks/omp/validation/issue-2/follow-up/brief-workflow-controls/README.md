# Live brief controls — incomplete calibration

2026-11-10. These are predeclared development controls for brief review, not logo qualification or
untouched transfer. They use the already-used fictional Sample repair-workshop context.

| Control | Expected | Observed |
| --- | --- | --- |
| Explicit owner color mandate preserved | Pass | Unsettled: source-completeness 0.63 |
| Owner color mandate omitted | Block | Fail: source-completeness 0.04 |
| Owner color mandate recast as designer proposal | Block | Fail: source-completeness 0.09 |
| Material deliberately open | Pass | Unsettled: preservation 0.51, completeness 0.67 |
| Unsupported free home-pickup claim | Block | Fail: grounding 0.09 |

No freeze was written in any case. Negative-control success does not establish a usable calibrated
workflow: both positive controls remain unresolved. Do not weaken thresholds or choose favorable
wording to manufacture qualification. Next work must investigate state and atomic preservation/
coverage judgments with these controls retained. No output image, preference or owner approval is
inferred from these text results.

`results.json` preserves the expected outcomes declared before calls, actual checks and answers.
Each case retains its brief, exact evidence and request/response/usage log. `reproduce.py.txt` is
the executed script source. To rerun, copy it to a Python file in a new scratch directory and invoke
it with `uv run --locked python /path/to/copied-script.py` from this repository. New source paths
change hashes; no identical probability result is assumed. Live calls use the configured provider
and consume budget.

The unconditional completeness question was added after independent Spec review demonstrated that
an omitted owner mandate could disappear from the extracted requirements without any question
checking completeness. Its offline omission/recast regressions were observed failing before the
fix and passing afterward. Live semantic calibration remains unfinished as shown above.
