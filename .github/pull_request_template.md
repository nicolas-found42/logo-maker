<!-- rumdl-disable MD041 -->
## Summary

<!-- State the problem and trigger, the behavior before/after, and why this change helps.
     Link the issue or spec when available (Closes #N only when this PR resolves it).
     Name affected stages or exports and any deliberate scope limits. -->

## Evidence

**Visible app change:** <!-- Yes: name the affected app surface or rendered visual output;
     or No: explain why there is no visible app change. Mixed PRs use Yes. -->

### Before

**Revision:** <!-- Baseline commit and any local changes. -->

**Scenario:** <!-- Inputs, environment and exact command/request or reproduction steps. -->

**Observed result:** <!-- Actual output, response, measurement or relevant old text excerpt,
     with a durable evidence link where useful. For visible app changes only, embed a
     real screenshot or rendered output image and explain what the reviewer should notice.
     Keep code, diffs, logs and docs excerpts as text; never screenshot them. -->

### After

**Revision:** <!-- Final commit and any local changes. -->

**Scenario:** <!-- Matching inputs, environment and exact command/request or steps;
     explain any unavoidable differences from Before. -->

**Observed result:** <!-- Matching observed proof and explanation of what changed or stayed
     equivalent. Visible app changes require a distinct real after image. Other changes
     require detailed text evidence, not screenshots. A bare "tests pass" is insufficient.
     Missing baseline/results remain unresolved under Gaps. -->

### Verification

<!-- Record actual results: pass, fail, or not run/N/A with a reason. Include exact
     commands, relevant test names and output or evidence links. Run checks appropriate
     to the change; do not claim success from an unchecked box or an intended command. -->

| Check | Result and evidence, or reason not run |
| --- | --- |
| Offline tests: `just test` | |
| Lint and formatting: `just lint` | |
| Types: `just type` | |
| Repository hooks: `just hooks` | |
| Render changes: `just render-example` | |
| Dependency changes: `logo-maker doctor` | |
| Jev/provider changes: relevant live tests with `-m live` | |

### Gaps

<!-- List failed or pending checks, missing evidence and next steps; write "None"
     when there are no gaps. GPU and live-provider checks are separate from offline CI.
     If an issue needs GPU or live-Jev validation, record the required check there and
     use the matching needs:gpu-validation or needs:live-jev label until resolved. -->

### Applicable project rules

<!-- Fill every response with what changed or a reason the rule is unaffected. -->

| Rule | Response or reason unaffected |
| --- | --- |
| Stage contracts in `docs/architecture.md` | |
| Jev definitions in `logo_maker/jev/questions.py` and regenerated `docs/jev-questions.md` | |
| New external-tool adapters and license documentation | |
| Brand-neutral catalog/defaults; examples used only for regression | |
| Images from geometry/fonts/materials/renderers; models only judge | |

## Merge Danger

**Door:** <!-- One-way or two-way, and why. -->

**Blast Radius:** <!-- Affected users, stages, files or exports; plausible failure. -->

**Recovery:** <!-- Rollback steps and limits; migration or rollout steps if relevant. -->
