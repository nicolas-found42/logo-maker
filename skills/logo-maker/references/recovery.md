# Recover a run and deliver assets

## Find the next step

Run `status` on the absolute logo folder. It reports text combinations, authored motifs, rendered
variants and completed refinement comparisons separately. Use its revision paths and the last
stage's stop to resume. Keep sources, prior renders, and published exports. A count or a
`run.json` stage flag records progress. Current eligibility is checked by the stage itself.
For a study, look up its immutable ID in `studies/` and its review in `qa/studies/`. Resume
Jev review of that ID or create a new study after changing inputs. See [3D studies](studies.md).

| Stop or change | What to do |
|---|---|
| Brief is incomplete | Check the generated templates and use project/owner evidence first. An exact source excerpt belongs under `inputs/`. Ask only for facts or choices that change the next decision. |
| Brief or references changed | Rerun `brief` with the reason. Review the effect on palette, type, metaphors and plans. Run affected stages explicitly. `run` can skip intake or ideation based on stage flags. Intake reuses existing generated `intake.json`, `palette.json` and `fonts.json`. Archive only picks or reference results that must be regenerated before rerunning intake. Before rerunning ideation, retain authored concept descriptions and plans. The stage rewrites shortlisted `concept.json` files. Reconcile surviving concepts with the new shortlist and review their plans. |
| Missing plan, motif, construction record or starter scene | Use the named template/file and the [authoring sequence](concepts.md). Rerun the stage that requested the change. |
| Inspection or critique | Open the exact retained image and prior revision and copy its current revision ID into the inspection record. Compare one meaningful source edit at a time. |
| Preview eligibility needs evidence | Put the intended gloss/reflection, material response and edges in `brief.toml`. A usable owner-supplied craft image with its own finish note is required for selection. Ask for it in plain language when missing, and show the flat work or retained study while waiting. Style references and bundled examples do not supply this floor. |
| Preview or final creative checks fail or remain uncertain | Read `qa/eligibility.jsonl` and the saved request assets under `qa/jev/`. Check that the request describes the current object, then repair any visible craft, fit or use problem. If a comparative check stays uncertain after inspection, use an identical-image control with the same rubric to investigate judge behavior. Preserve the control separately from selection evidence. |
| Metal/OIDN, provider or budget error | Report the actual failing row or stage. Fix the specific dependency or provider issue. For a shared `run` budget stop, use the relevant individual stage with its own bounds once you identify the cause. Allow the first kernel compile to finish within its deadline. Reuse retained evidence only while current. |
| Export reports a stale winner | Check whether `ideation/winner.json` exists. With no winner, resume at the first unresolved preview or final gate. With an existing winner, follow the stale stage and refresh the affected evidence before finalizing and exporting. Keep prior exports in place until the current run succeeds. |

A user's overall rejection applies to the exact reviewed artifact. Use `qa/owner-feedback.json`
with the concept ID and current image/input revision hashes. Obtain scope with
`logo_maker.eligibility.owner_review_scope()` and read the checkout's eligibility contract in
`docs/architecture.md` for record fields. Keep past feedback and report preference independently
from model evidence.

When the eligibility stop includes `details.candidates`, open the named candidate image and use
the failed or unsettled checks as inspection leads. If the stop predates these details, read the
matching stage and concept rows in `qa/eligibility.jsonl`.

## Choose the craft reference

Ask for an example in plain language when the user has a required quality floor. For an explicitly
fictional test or delegated direction, choose a separate project-authorized control and disclose
its provenance as a test choice. Open it and describe its own edges, finish and construction in
the reference note. Keep the candidate's brand, shapes and colors grounded in its brief. Add the
reference before the first brief freeze if possible. Adding it later needs an explicit revision
reason and refreshed plan reviews. Independent image eligibility still runs on the actual output.

## Qualify the render

Before committing to a production finish, check whether the host can qualify it. Read
[profile activation](../../../docs/automatic-sampling.md#profile-activation). Set
`[sampling].profile` in each applicable `scene.toml` to the matching retained profile, using an
absolute path or a path relative to the concept. The tool validates runtime, code and material
scope. The supplied M5 Pro comparator has a specific reviewed scope. A stale, unavailable or
out-of-scope profile leaves the render as a study until a valid match or new qualification exists.
Custom Blender components can be inspected but are outside the current production profile scope.

A checkout can pass doctor while its profile is stale. For a concept with a scene recipe, run
the [profile preflight](../scripts/check-final-profile.py) from the tool checkout. Set
`skill_dir` and `concept_dir` to their absolute paths.

```sh
uv run --locked python "$skill_dir/scripts/check-final-profile.py" "$concept_dir"
```

Exit 0 means the approved profile matches the recipe and runtime. Exit 3 reports the qualification
stop and identifies any stale context fields. The final render still verifies execution and pixels.
A final-only profile can appear as `profile_stale` in a preview report because the stage and
resolution differ. Check the final profile preflight and the final sampling report for production.
When a clean checkout has a profile matching this machine and its source, run the whole job
from that checkout with the same absolute logo folder. Change into the tool checkout before
running a Python probe so it imports the matching package, even when the current project also
contains `logo_maker`.
A tool switch after a brief or render can invalidate existing evidence. Reopen the brief and rerun
the affected stages when the tool reports staleness. If there is no matching approved record, use
the sampling policy's recalibration workflow and retain the study for review.

Read `qa/rounds.jsonl` and `.build/final.sampling.json` for a final stop. For technical failures
use [refinement records](refinement.md) to write image-bound `diagnosis.json`. Separate persistent
geometry, alpha, filtering, resolution, typography or material problems from stochastic noise.
For a noise hypothesis compare independent seeds with geometry, lighting and material fixed, and
inspect noisy and denoised detail. Keep explicit controls and reported cap, deadline, memory and
unknown outcomes. The [sampling policy](../../../docs/automatic-sampling.md) owns qualification
and bounded comparisons. A final-stage sampling match attests to render execution. Full export
also needs a current winner and passing image eligibility.
Put study assets in a separate folder and label which creative checks remain open.

## Improve a published logo

Use `improve` when the logo folder has `exports/hero-transparent.png`. It archives the
published round and keeps that hero as the comparison floor. Write fresh metaphors before
starting a new challenge. Follow the returned authoring stops with the same target. Use the
individual stages for authoring and revalidation. `improve` skips stages already marked done,
so explicitly rerun affected stages if you edit inputs after one of those stages passed. For
example, after changing a challenger scene after final selection, rerun `refine`, `preview`, and
`finalize` before resuming `improve`. If the brief changed, reopen it and replay affected intake,
ideation and plan work first. Keep the active `floor/` and return to `improve` for publication.
Report `replaced` or `floor_held` from the result and link the exports that remain current.

## Verify the handoff

For full delivery, open `exports/contact-sheet.png` and `exports/hero-transparent.png`. Verify
the requested formats against `exports/manifest.json` and inspect small versions and contrast.
The mono mark uses one ink color and the sheet previews it on the brand background. The winner's
reason and win tally are in `ideation/winner.json`; a tie can resolve by deterministic ordering.
`run.json` records Jev requests, token usage and reported cost when available.

Give each deliverable its actual state. A requested flat asset can be complete after its flat
checks. For an unfinished 3D job, link the usable flat mark or retained render study with the
missing craft evidence, current qualification stop, or runtime requirement and how to resume.
After a successful export on current evidence, link the contact sheet and requested assets
such as SVGs, favicon set, avatar, transparent hero, editable Blender scene or GLB.

For several objects, `study` packages the named designs into one ZIP. For a qualified export of
each object, start a qualified campaign for each. Keep the exact request in the
parent project. In each campaign, add a source that states which object it covers and cite that
source for the local subject requirement. Write the expected material, edge transitions and sheen
for that object in `intended_appearance`. Carry the shared identity across both and qualify each
package on its own current evidence.
