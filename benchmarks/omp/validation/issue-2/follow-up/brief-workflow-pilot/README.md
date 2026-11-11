# Brief workflow pilot — Rootshare development case

2026-11-10. This is an unresolved intake result, not a qualifying design or a solved calibration.
The new brief separates archived seed-library facts from the proposed shared-resource priority,
material direction and open construction choices. The previous rejected R remains unchanged.

Two calls through the actual CLI used the same production rubric and brief. The first passed
activity, audience, communication, grounding, consistency, factual support and both source-backed
requirements, but left mandate preservation unsettled (0.55). Inspection found that reference
roles and hashes were absent from review state. A public-boundary regression demonstrated the
omission; the implementation now supplies that metadata and binds reference bytes into the freeze.
The second request tested that structural fix without changing wording or thresholds. Mandate
preservation remained unsettled. No freeze was written, and no candidate was authored or rendered.
The state omission was real; fixing it did not resolve this semantic disagreement.

Exact requests, answers, provider usage and both review records are retained here. Request states
contain original local paths; image bytes are the unchanged assets at
`benchmarks/omp/assets/original-seal-2000.png` and `reconstruction-rendered-2000.png`.

To reproduce from the repository root, copy this folder's brief, evidence and text inputs to a
new logo folder, then copy those two assets into its `inputs/` directory. Run:

```sh
uv run --locked logo-maker brief /absolute/path/to/copied-logo-folder
```

Provider probabilities may differ; a settled pass is not assumed. Do not repeatedly reword the
requirement until it passes. Next investigation must separate which established mandate is
unrepresented from whether a future design actually achieves it. An intake review cannot certify
future detail, craftsmanship or the final comparison outcome.

Implementation checks observed during this slice: the four focused test files
`test_brief_workflow.py`, `test_eligibility.py`, `test_jev_questions.py` and `test_jev_stages.py`
passed 113 tests; lint and type checks passed. Required full, live-image, GPU, independent-review
and CI checks remain part of the overall issue's completion audit.
