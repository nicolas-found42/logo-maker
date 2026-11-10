# Machine validation — November 10, 2026

The workflow retained real structural revisions, image inspections, live Jev judgments and comparative
review on the Skill Swap paper case and a separate Keystone metal brief. Both current designs remain
`authoring_needed` because craft/material judgments are uncertain. No creative finalist, production
final or export approval is claimed. This is a tested bounded outcome, not owner artistic sign-off.

## Standalone results before sampling integration

| Case | Authored designs | Retained render revisions | Standalone live probabilities | Outcome |
| --- | ---: | ---: | --- | --- |
| Skill Swap paper | 3 | 5 | craft 0.57; fit 0.76; material 0.70; description 0.83 | craft unsettled |
| Keystone metal | 4 | 6 | craft 0.56; fit 0.90; material 0.56; description 0.75 | craft/material unsettled |

Later renders repeated unchanged artwork after implementation changes invalidated content keys.
They are verification replays, not new creative alternatives. Thresholds were kept at the existing
central Noul bands; no threshold was lowered to qualify these images.

Paper changed from the retained angular S ribbon/slab construction to facing folio leaves, then a
connected binding and attached turned corner. Live comparisons recorded a distinct alternative
(0.98) and resolved the earlier symbol critique (0.84); the binding/corner comparison recorded 0.89
resolution. Independent craft uncertainty still blocks progression.

Metal changed from a generic gate to an assembled arch/keystone. The comparison recorded 0.99 visual
distinction and 0.82 resolution of the missing-key critique. A subsequent normal-change hypothesis
did not remove radial highlights; the incorrect initial inspection was corrected and both inspection
versions were retained. Authoring a shared anisotropic tangent visibly removed the starburst while
roughness, lighting, seed and samples stayed fixed. Comparative/model uncertainty remains recorded;
the workflow did not turn the observed fix into an unqualified readiness claim.

## Execution and provenance

The 11 standalone workflow renders passed exclusive Metal tracing and runtime OIDN Metal
verification on the
owner's M5 Pro: macOS 27.0.1, bpy 5.2.3 `e13b728c6880`, OIDN 2.5.0, MetalRT AUTO. CPU tracing selections
were disabled. CPU construction, synchronization, submission, analysis and file work remained allowed.
Preview settings remained fixed at 1000 px / 256 samples, with a recorded fixed seed per case.

`evidence/summary.json` records image/source hashes, device/settings evidence, native-log evidence,
per-render timing and current judgments. The standalone source-only verification replays used implementation
`ab2969b`. Their render+denoise+PNG times were 3.128 s (paper) and 2.383 s (metal). These are single
measurements with unknown cache state, excluding prior scene construction; they are not speed or
sampling qualification claims. Host total timings are recorded separately.

The PR Before image is a fresh replay of the retained paper source using baseline
`38ba86b9ccff305cb453c46920824509ae989f76`;
its execution sidecar is in `evidence/baseline-paper/`. The After image is the current-source folio
preview. The renderer's behavior is inherited from the GPU foundation; the new feature is the
image-backed authoring/critique/evidence contract, not an automatic style conversion.

Public evidence contains exact authored-source copies, images, inspections, judgments, comparisons,
execution sidecars and native logs. Complete tool/build snapshots, Jev requests/assets and job history
are retained on this machine in `benchmarks/refinement/local/`, intentionally excluded from Git.
Immutable evidence is excluded from automatic format rewriting and checked with:

```sh
uv run --locked python scripts/verify_refinement_evidence.py
```

Standalone observation: 11 revisions and 86 authored-source files verified, including exclusive
tracing selection
and effective GPU denoiser logs. Public evidence does not duplicate every historical tool/build input.

## Verification

- Final combined `just test`: 249 passed, 3 deselected (render/profile tests), 49 upstream
  NumPy/skimage deprecation warnings. The earlier standalone run had 221 passed.
- `just lint`, `just type`, `just hooks`: passed after formatting corrections.
- Cycles regression: `uv run --locked python -m pytest -q
  tests/test_example_render.py::test_example_concept_matches_reference -m render`: 1 passed, including
  the existing SSIM >= 0.90 assertion and verified GPU execution.
- The full `just render-example` recipe also selects an alternate LuxCore render; that unverified
  device path was not executed under the owner's GPU-only policy.
- Live provider: actual `typesafe/jev-1.14` creative and comparison calls are retained for both cases;
  this was workflow validation rather than an owner-calibrated artistic quality test.
- Independent Standards and Spec reviews found two comparative-critique/feedback bugs and one shared
  inventory concern; all were fixed and re-reviewed with no remaining actionable findings.

## Remaining qualification

Owner artistic acceptance, calibrated creative thresholds and broader OMP transfer remain open under
the quality work. No current experimental artwork is a qualified finalist. #5 owns diagnosed sampling
actions, profiles, budgets, independent-seed/noisy/denoised probes and production 4000→2000 qualification.
The 4096 / 0.01 adaptive final comparator and explicit overrides are unchanged. Missing diagnosis stays
unknown; generic edge failures do not cause 8192/threshold-halving retries.

## Completion review limits

The standalone Jev patch gate escalated broad test/blast-radius uncertainty (`safe_to_apply` 0.29,
composite 0.6965); it reported no contradicted completion claims. Its generic pytest-log attribution
was also uncertain. Both reasoning reviewers audited the exact test selection, real renderer path,
source/evidence verifier and corrected orchestration tests. They found no concrete blocker to draft
PR publication. The gate was not rerun or presented as automatic approval. Its complete result is
retained in `evidence/jev-gate.json`. Draft publication is reviewable implementation, not artistic or
production qualification.

## Final combined validation with #5

The creative branch now includes the bounded sampling foundation from PR #9, pinned at
`f3d0f151963aedaa59b6819b1c44bbe6ce62bbf6`. It will be reviewed as a stacked PR against that branch.
The numeric `sampling.decide()` policy is unchanged. Shared budget, sampling/runtime freshness and
production-profile gates compose with the independent creative/inspection/comparison gates.

The final combined suite passed **249 tests**, with 3 render/profile tests deselected. The selected
real Cycles regression passed (SSIM >= 0.90), lint/types/hooks passed, and doctor reported **46/46**.
Twenty-four refinement tests cover structural resume, stale evidence, feedback, source/device changes,
sampling qualification, budget stops and source/inspection edits during final selection. Follow-up
Standards and Spec reviews found no remaining actionable findings in the reviewed integration.

The public bundle now retains **14 render revisions and 110 exact authored-source files**. Seven
actual designs remain: three paper and four metal; the extra source-only replays are not new ideas.
Both latest snapshots match the current core source hashes. Full local jobs, including raw sampling
attempts and diagnostics, remain in the ignored `local/` folder.

| Integrated case | Latest revision | Effective seed | Current live probabilities | Sampling status |
| --- | --- | ---: | --- | --- |
| Paper | `0007-474e8fb143b2-preview` | 1820117 | craft 0.56; fit 0.67; material 0.69; description 0.76 | profile unqualified |
| Metal | `0007-90eaefb82fef-preview` | 42 | craft 0.44; fit 0.86; material 0.41; description 0.55 | profile unqualified |

Both return scoped `authoring_needed`. No creative finalist, final/export acceptance or owner approval
was inferred. The older renderer used effective seed 0 despite the recipe metadata; the integrated
renderer honors the recorded recipe seeds. The PR's baseline/current images are therefore a creative
construction comparison, not an isolated sampling or seed comparison. All settings/seeds are retained.

Custom-bpy previews are reopened only as retained evidence for inspection and critique. Known source,
declared dependencies, image bytes and runtime context are checked, while complete custom dependency
inventory remains unknown. Normal production reuse and sampling qualification still fail closed for
custom scenes; this limited reopening prevents an infinite render→inspection→rerender loop without
pretending Python dependencies are complete. Production custom-scope qualification remains #5 work.

Final selection freezes the approved campaign/image/inspection bindings before online tournament
judgments and rechecks them afterward. In-flight edits roll back winner publication. Policy profile
and diagnosis files are hashed as controls, outside their own image source key, preventing circular
diagnosis binding. No numeric sampling policy is copied into the creative module.
