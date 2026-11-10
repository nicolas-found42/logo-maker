# Issue 2 — strict visual eligibility, November 10, 2026

Base revision: the main-branch merge of PR #6 (`codex/automatic-gpu-sampling`).
This is selection-policy validation, not a claim of successful
creative transfer to a new brand. All source artwork remains geometry/font/material/render output.

## Requirements and judgment chain

The owner asked for more and stricter criteria after rejecting Rootshare's craft and brief fit.
`rubric-chain.json` retains the two dependent Jev design judgments. The bounded strategy Choice
selected independent, stricter gates; the next Noul review supported the brand-specificity and
native-detail additions but left treatment neutrality uncertain (0.73). This uncertainty was
tested on pixels rather than converted into a completion claim. The third step was the expanded
actual-image calibration in `strict-calibration/`.

Eight reference-relative craft criteria cover form, surfaces, detail, edge refinement, material
construction, proportions, hierarchy and lighting. Eight independent brief/use criteria cover
literal symbol, intended appearance, developed brand-specific idea, meaningful synthesis,
constraints, communication and 32 px flat/hero identity. Four technical criteria separately
cover stochastic noise, preserved detail, persistent aliasing and correct structure. Every
essential criterion must pass, for every reference in both orders. Equal craft meets the floor.
The Noul bands remain 0.7/0.3; substantive requirements grew without fitting a global appeal score.

References establish execution level, never a universal palette, geometry or preferred finish.
Whole images over the provider limit additionally supply every native 1000 px tile. Actual flat
masters and hero renders are reduced to 32 px and enlarged with nearest-neighbor pixels.
`qa/jev/requests/` records exact questions/model and encoded-image hashes; `assets/` retains those
pixels. `files.sha256.json` indexes the measurement artifacts before this narrative was added.

## Actual-image results

| Case | Craft comparison | Full eligibility | Owner feedback |
| --- | --- | --- | --- |
| Restrained Chief vs itself | All 8 craft checks pass in both orders | Fail on appearance; other fit checks unsettled | Craft approved; other dimensions unranked/unknown |
| Glossy Chief vs itself | All 8 craft checks pass in both orders | Unsettled technical edges | Craft approved; other dimensions unranked/unknown |
| Chief treatments vs each other | Unsettled craft in both directions | Restrained candidate fails appearance; glossy candidate unsettled | Both remain high-quality craft positives; no universal preference |
| Skill Swap Fold | Unsettled craft | Unsettled | Existing overall rejection; individual causes unknown |
| Skill Swap Gather | Unsettled craft | Fail | Existing overall rejection; individual causes unknown |
| Skill Swap Commons | Unsettled craft | Fail | Existing overall rejection; individual causes unknown |
| Rootshare terracotta sprout | Unsettled craft; brand specificity and edges also unsettled | No preview advancement; no final winner | Owner: “both below floor” — craft and brief fit rejected, preference unranked |

The Chief craft positives are not silently overridden by separate fit or technical results.
The original's appearance judgment conflicts with the intended description and remains a model
calibration limitation. Cross-treatment uncertainty remains review-needed; no automatic
cross-treatment quality ranking is claimed. All rejected controls fail to advance. The final
Rootshare attempt additionally records the owner's hash-bound veto, with the model answers
preserved separately. Owner approval cannot replace missing or unsettled essential evidence.

The first exploratory image probe used incomplete Skill Swap concept descriptions. It is
superseded by the retained authored brief/concept/SVG inputs under `qualification/skill-swap`;
only the expanded, correctly sourced calibration above is used for acceptance evidence.

## Machine and execution

Rootshare is an independently authored sprout for a neighborhood seed library, with matte
terracotta material and no Chief palette, seal, lettering or ribbon geometry. It is deliberately
retained as a rejected held-out control, not a successful new-brand example.

Apple M5 Pro, macOS 27.0.1, bpy 5.2.3 LTS build `e13b728c6880`, OIDN 2.5.0. The actual process
disabled CPU tracing, selected exclusive Metal and retained OIDN-created Metal device and executed
filter diagnostics. CPU host construction, synchronization, submission, analysis and I/O are allowed.
Effective final sampling: adaptive on, maximum 4096, threshold 0.01, minimum 0, seed 0, animated seed
off; 4000 px rendered and delivered at 2000 px. The recipe's meta seed is not substituted for the
observed Cycles seed. Baseline numeric settings were preserved.

Preview host wall time was 3.30 s; final host wall time 39.64 s, of which the native verified
render/denoise/PNG scope was 37.97 s. These are single measurements, not timing distributions or
profile qualification. Sample-count/near-cap diagnostics and convergence remain unknown.
No capped or unknown image is called converged. There was no generic edge-driven sample retry.

`rootshare/concept/.build/` retains execution JSON/logs and measured inputs, while the portable
authored fixture lives under `qualification/rootshare`. `measured-brief.toml` retains the exact
local reference path used in this measurement; use the portable fixture plus an explicit craft
reference when reproducing elsewhere. Historical CPU Chief provenance was never sent as a quality
signal and did not disqualify its pixels from craft comparison.

## Verification

| Command | Observed result |
| --- | --- |
| `just test` | 246 offline tests passed after the reviewer-found remainder-tile fix; 4 GPU/live checks deselected |
| `just type` | Passed |
| `just lint` | Passed |
| `just hooks` | Passed before evidence packaging; final packaged check recorded in the PR |
| `just render-example` | GPU regression passed, SSIM at least 0.90; alternate engines rejected operationally by a separate offline test |
| `uv run --locked logo-maker doctor` | 46/46 passed after locked JavaScript dependency installation |
| `uv run --locked python -m pytest -q tests/test_eligibility_live.py -m live` | 3 live controls passed with the expanded rubric |
| `uv run --locked python scripts/validate_eligibility.py --output DIR` | 7 cases, 28 fresh image requests; exact output retained in `strict-calibration/calibration.json` |
| Actual Rootshare `pipeline.preview` / `pipeline.finalize` | Authoring needed; no winner, followed by explicit owner-veto final attempt |

Offline coverage includes all-poor batches, strong technical/weak craft, uncertain symbol match,
equal-to-floor, absent references, malformed/provider errors, denoiser-smoothed detail loss,
persistent aliasing, structural errors, GPU policy failures, stale export proof, owner veto and
no automatic sampling escalation from a generic edge failure. Existing exports/floor survive
selection failure; same-brand `improve` still has its separate relative preference comparison.

## Remaining limits

No new-brand success is claimed: the owner rejected Rootshare. Cross-finish craft judgments and
some fit/technical judgments on approved Chief artwork remain conservative or discordant, so
review-needed is an expected reachable outcome. There is no universal objective aesthetic score.
Issue 5 still owns diagnostic sampling profiles, numerical cap/seed qualification and bounded
automatic adjustment. No missing diagnostics, low noise, GPU provenance or tournament win supplies
a craftsmanship/fit pass. The initial full-suite run retained dependency deprecation warnings.
