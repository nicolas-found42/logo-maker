# Calibration follow-up — November 10, 2026

Issue #2 and PR #7 remain incomplete on visual calibration. This bundle records the attempted
repairs and their limits. No experimental wording, relaxed threshold, owner-positive override,
or inferred owner label was adopted.

## Owner-label correction

The current `../rootshare/qa/owner-feedback.json` contains only the displayed original sprout
**final**. The withdrawn preview judgment remains unknown. The superseded bytes and correction
history are retained beside that file. Nothing in this follow-up transfers that rejection to
the revised R, or to the failed spiky intermediate shown during authoring.

## Confirmed transport defect

Mixed image sizes need a shared canvas. The former alpha-mask paste applied transparency twice:
source RGBA `(20, 40, 60, 128)` became `(10, 20, 30, 64)` in the transmitted PNG. A public
`JevClient.ask` test decodes the actual HTTP image asset. It fails against the isolated previous
client at `b3790a476ca4b288227768076abd55eac4823707` and passes after copying source pixels
directly.
This is an evidence-integrity repair; it does not establish a cause for every calibration failure.

`padding-calibration/` retains a fresh production-rubric run after the pixel fix: seven cases,
28 requests, both presentation orders. The eight craft, eight fit/use and four technical criteria
and 0.7/0.3 bands were unchanged.

| Case | Craft, both orders | Fit | Technical | Overall visual gate |
| --- | --- | --- | --- | --- |
| Chief original vs itself | Pass | Appearance fails; constraints and clarity unsettled | Pass | Fail |
| Chief reconstruction vs itself | Pass | Clarity unsettled | Pass | Unsettled |
| Chief original vs reconstruction | Unsettled | Appearance fails; constraints and clarity unsettled | Pass | Fail |
| Chief reconstruction vs original | Unsettled | Clarity unsettled | Pass | Unsettled |
| Skill Swap Fold | Unsettled | Symbol and clarity unsettled | Unsettled | Unsettled |
| Skill Swap Gather | Unsettled | Clarity fails; other checks unsettled | Structure fails; other checks unsettled | Fail |
| Skill Swap Commons | Unsettled | Symbol, constraints and clarity unsettled | Structure fails; aliasing unsettled | Fail |

Both Chief treatments retain their owner's positive **craft** labels. Neither treatment has an
inferred positive label for every fit/technical check. The model's unresolved cross-treatment
craftsmanship remains a calibration gap. All three rejected Skill Swap controls remain blocked.
Historical CPU/GPU provenance did not enter visual questions. Preference remains unranked.
`live-tests/` retains the three passing live test payloads: the two craft self-controls and
rejected Gather. Those tests do not prove that cross-treatment calibration passes.

## Controlled diagnosis: unsuccessful alternatives

`diagnosis/qa/jev/requests/` retains 24 dependent diagnostic requests with exact state, questions,
answers, encoded-pixel hashes and assets. These are experiments, not production criteria.

| Requests | Hypothesis and result |
| --- | --- |
| 1–5 | Replay appearance; remove small views; isolate target; describe source recipe; give a deliberately wrong flat black/white target. Original appearance remained failed/unsettled; wrong target failed. |
| 6–10 | Split gloss, reflections, contrast and edge judgments; observe the wax and gold separately, then supply per-surface intent. Wax checks passed, gold reflections/edges remained unsettled. No complete positive. |
| 11–13 | Compare resolved execution against a floor instead of superiority. Approved Chiefs did not pass; rejected sprout did not qualify. |
| 14–15 | Normalize subject scale from alpha bounds. Both approved cross-treatment cases still failed/unsettled. |
| 16–18 | Ask below/meets/exceeds-floor Choice plus an independent resolution Noul. Approved examples still failed/unsettled. Choice was not used as eligibility. |
| 19–21 | Isolate the subject and ask resolved craft facets. Approved form/edge facets remained unsettled. |
| 22–24 | Supply both approved Chief examples and their explicit craft labels. Neither positive passed every essential facet; rejected sprout remained blocked. |

These probes did not produce a rubric that passed approved examples while preserving the required
strictness. They therefore supply no basis for a production wording or threshold change. The
source recipe shows clearcoat on wax and reflective gold; the original's relative “muted” target
must not be silently rewritten as a universal matte requirement. The aggregate appearance
question and per-surface intent remain areas for further calibration.

## Revised different-material development artifact

`rootshare-v2/final.png` is the revised Rootshare R with a seed counter, clay body and pale inlay.
It began as a held-out case; after iterative owner feedback it is a development case for future
brief/authoring experiments, not an untouched validation sample.
Its exact SHA-256 is `27e06fb55845c44c16d9178dd6023c035ba87e2102f5d3649819423784806081`.
The portable source is `../../../qualification/rootshare-v2/`. Its geometry comes from the shared
flat master. Closed offset-ring meshes replace the failed bevel modifier; CPU mesh construction
is permitted host work. Mesh closure does not establish visual craftsmanship: the lower stem has
a visible small surface artifact, and the model still leaves craft/fit/detail checks unsettled.

The final was traced at 4000 px and delivered at 2000 px. Execution JSON and native log retain one
selected Metal device, CPU tracing disabled, and OIDN 2.5.0 Metal RT filter execution. Native
render/denoise/write time was 78.63 s; host orchestration was about 80.32 s. Effective seed was 0,
not the recipe's informational meta seed 74. Sample-count diagnostics and convergence remain
unknown. No sampling setting changed and no generic edge failure raised samples.

`rootshare-v2/calibration.json` and `qa/` retain four production-rubric requests. Craft is unsettled
in both orders; symbol, brand specificity and synthesis pass, while appearance, constraints,
clarity, flat small-size and preserved detail remain unsettled. Overall: **unsettled**. No finalist,
winner or export eligibility is claimed. `owner-labels.json` now records the owner’s overall
rejection and requests for a more specific brief, more detail and comparison with both Chief
finishes. Separate craft/fit labels remain unknown; preference remains unranked.
Owner review must concern this exact final; approval/rejection of another image cannot substitute.

Exact measured Python sources have `.py.txt` suffixes. The portable Python fixture is formatted
for the repository, so its source bytes differ. To audit the retained execution, copy the measured
folder to a temporary directory, restore `scene.py` from `scene.py.txt`, then call
`logo_maker.render.verify_execution(directory, "final")`. The measured mesh dependencies are
retained under `.build/meshes/`; the verifier passes with those exact measured bytes. The compiled
scene preserves original local paths as historical data, not as portable commands.

## Verification and remaining work

- `just test`: 247 passed; 4 GPU/live tests deselected; 49 upstream NumPy/skimage warnings.
- `just type`: passed.
- `just lint`: passed after keeping exact unformatted measured sources as text.
- `uv run --locked python -m pytest -q tests/test_eligibility_live.py -m live`: 3 passed.
- GPU-only tracing and denoising: actual revised final verified independently of model judgments.
- No renderer implementation, numeric sampling default, dependency or production rubric changed.
  The prior GPU regression and 46/46 doctor results remain historical checks, not new runs.

Remaining: resolve the Chief cross-treatment craft and original appearance disagreement without
fitting probabilities to these examples; obtain exact-image owner labels for a held-out material;
validate any future rubric on untouched positive and negative cases. The revised R has now been
owner-reviewed and rejected overall. There is currently no
owner-reviewed different-material success. The strict model gates continue to block uncertainty.
`files.sha256.json` indexes retained measurement/source assets, excluding itself and this narrative.
