# Beginner workflow validation, November 12–13, 2026

## Recorded sequence

1. The adversarial pass used a beginner persona to exercise installation, exact SVG reuse, flat
   favicon output and stage recovery. Its final recorded pass reported 801 offline tests and two
   GPU regression tests passing on the earlier local tree.
2. The Field Kettle walkthrough began with a one-sentence brief for a trailhead coffee cart. After
   the owner requested two freestanding objects, the mug and espresso maker received separate
   briefs. The mug handle moved to the right wall with two vertically spaced joins. Both models
   were aligned upright in their editable scenes. The color and one-ink flat marks carry a
   shared ridge.
3. The two 2000 px renders passed Metal/OIDN sampling checks on the profile-matching checkout
   at `afdad6a`. The export worker produced study packages with 31 manifest entries each.
   All listed file digests matched. Live image review left craft and appearance unsettled.
   Comparing the craft reference with itself also produced unsettled surface, edge, and material
   judgments. No current finalist or winner was admitted and the production export remained
   gated. Study images, requests and manifests are retained in the local Field Kettle workspace.
4. The review branch integrated the pending changes with `origin/main` at `3809473`.
   Conflict resolution retained upstream path resolution and sampling policy ownership.

## Checks on the integrated tree

| Check | Result |
| --- | --- |
| Lint, formatting, skill frontmatter and type check | Passed. |
| Generated documentation and doctor | Passed. Doctor reported 49 of 49 checks. |
| GPU regression, `just render-example` | Two tests passed. |
| First six-worker offline run | Four failures while commit hooks temporarily hid unstaged source. This run is invalid as a check of the integrated tree. |
| Six-worker offline rerun with a stable tree | 813 passed, two deadline cases failed before reaching the injected fault. |
| Focused offline rerun | Nine passed, including all five deadline cases and all four tests from the invalid run. |

Commit hooks initially reported spelling fixtures, a broken relative documentation link and
wrapping issues. The final commits passed their hooks after those fixes. The first split also
exposed cross-commit imports in untracked tests. Those tests were committed after their code
dependencies.

## Unfinished work

- **Field Kettle production export.** The renders and format checks establish study packages.
  Visual qualification and a current production winner remain open.
- **Sampling profile transfer.** The final-profile preflight on the integrated source returned
  `profile_stale` for `code_sha256`. The earlier owner-reviewed profile is tied to the exact
  profile-matching checkout. No new sampling profile was approved for this branch.
- **Lighting study.** The optional `studio_45` rig is available. A dedicated visual comparison on
  the integrated revision is unexecuted.
- **Other unexecuted checks.** The full opt-in live Jev test suite, live Field Kettle qualification
  on the integrated tree, installation into real agent configurations, and hosted CI for the
  review branch were unexecuted at handoff. Live Field Kettle attempts on the older checkout are
  recorded above.
