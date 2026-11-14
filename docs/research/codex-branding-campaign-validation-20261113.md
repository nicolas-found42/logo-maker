# Codex branding campaign validation

Three frozen fictional briefs exercised the skill and tool on Apple M5 Pro. Breakwater Supply
needed an original cast dock fitting. Meridian FM required an enamel-and-brass adaptation
of a supplied circular SVG. Seedwell needed a glazed ceramic propagation planter. The prompt
for each trial delegated the brief and concept choices and retained final owner review.

## Installation and recovery

The scoped installer created three independent, locked Python and Node environments and
copied the skill from each tool snapshot. Fresh Codex sessions read the skill, researched each
brief, built two directions, exported editable scenes, and chose their preferred design.
The installed Codex MCP server separately returned 50 of 50 doctor checks and accepted
`logo_campaign init` from a fresh session. The trials used the installed CLI for authoring
and render calls. A follow-up used the repository campaign command to produce the exact
8192 / 0.01 review handoffs.

The first workspace sandbox runs could not initialize Blender Metal and crashed. A trial
attempted to patch and launch a copied Blender application, which caused a Gatekeeper prompt.
Those sessions were stopped and the modified copy was moved out of its temporary location.
The installed Blender application had five unsigned Python bytecode files dating from before
the trial. Moving the listed caches aside restored the original signature verification.
Gatekeeper accepted the installed app as Notarized Developer ID, and an ordinary background
launch exited successfully. The repeated trials used the locked `bpy` module with Metal access
and left the app bundle untouched. The setup instructions now specify where to stop if Metal
preflight fails.

The Found42 regression interrupted a two-concept real Metal preview after one completed
view. The next invocation reused the verified view without changing its cache record and
rendered one remaining view. Seedwell also exposed a motif currency bug. The campaign now
prepares the motif before capturing source hashes.

## Initial handoff results

| Trial | Study | Verified handoff |
| --- | --- | --- |
| Breakwater Supply | `study-1031faaa12d1` | 15 objects in the packed editable scene |
| Meridian FM | `study-471dc393c4c3` | 13 objects and all four source apertures preserved |
| Seedwell | `study-3ef1a19fa566` | 87 objects in the packed editable scene |

Each handoff contains a transparent 2000 px PNG from a native 4000 px hero, an editable
Blender scene, inspection views, color/mono/compact SVGs, PNGs and favicons. The 15 delivered
views used verified Metal tracing, GPU OIDN, the 8192 cap, 0.01 adaptive threshold and automatic
minimum. Every shareable ZIP entry matched its inventory. The scenes reopened in a clean
temporary folder and had no linked libraries. Private photos and the raw brief stayed out
of the shareable ZIP.

Breakwater passed appearance, structure and the small-size checks. Jev failed brand specificity
and left grain unsettled. Meridian passed Jev on source identity, the requested adaptation and both small-size checks.
Its appearance score was 0.27. A tracked revision adjusted only the enamel surface. With the
same camera and lighting the appearance score was 0.26, so the stronger earlier result
remains available. Seedwell passed the symbol, small-size and structure checks. Noise,
detail, aliasing, appearance and brand specificity remained unsettled.

These are review handoffs. The trials did not acquire 40 relevant and verified photographs
per selected design with matched craft and independent holdout crops. Public-image sourcing
hit rate limits, and the available images were insufficient for the mandatory comparisons.
The Breakwater sampling run retained verified 0.01 and 0.02 renders of the cleat and
0.01 and 0.005 renders of a separate tie-down eye. On opaque pixels the 95th percentile
maximum channel differences were 2 and 1 levels respectively. The packet is pending owner
review and covers satin cast metal only. The runner fingerprint also predates subsequent
campaign edits, so it must match a final installation before activation. Final owner acceptance
remains open. The campaign maintains the production gate while evidence is outstanding.

Raw prompts, session events, build inputs, evidence and packages are local to
`logos/workflow-validation/codex-campaign-trials/`.

The initial validation checkout passed 825 offline tests and both GPU regression tests. Earlier
parallel test runs during the renders hit deadline-sensitive cases. The affected cases
passed in isolation and the stable run passed in full. Lint, type, generated documentation
and skill checks passed.

## Enforced workspace rerun

The same three selected designs ran in a Codex-generated Seatbelt workspace profile on
the Apple M5 Pro. The local opt-in CLI build verified 1,024 GPU results and a shared event.
The boundary probe denied writes to a temporary file outside the workspace and Git metadata,
denied localhost TCP, and confirmed that a child inherited the write restriction. The
bundled `bpy` module verified Cycles Metal tracing and GPU OIDN with binary archives disabled.
The installed Blender signature passed strict verification. The build and reproducer are in
the [Metal sandbox research note](codex-metal-primary-sources-20261113.md).

The owner approved the regenerated 8,192 / 0.01 production and held-out renders and
rejected 0.02 for production. The independent tie-down eye also rendered at 0.005 for
comparison. The profile matched the renderer at the time and qualified on import into
Breakwater for satin zinc-gray cast metal. Later runtime and tool changes made that evidence
stale for the current revision. Meridian and Seedwell use different material classes.

| Trial | Latest verified study | Distinct photos | Jev result |
| --- | --- | ---: | --- |
| Breakwater Supply | `study-02fd06e8c4f6` | 42 | Unsettled |
| Meridian FM | `study-c75756513c73` | 78 | Unsettled |
| Seedwell | `study-d243ae3556f1` | 61 | Unsettled |

Each package includes the verified transparent hero, front, grazing, rear and underside
views, a packed editable scene, flat artwork and favicons. Archive hashes and scene
reopening passed. Breakwater's raised lettering is visible on the mounting flange, and
both bolt holes are open. Meridian's stronger teal at grazing angles leaves its four
source openings clear. Seedwell has a supported draining liner, a tapered seedling
and a trimmed clay foot. The last three studies had six unsettled matched comparisons
each. Final artwork approval is pending for all three.

All three identical-photo controls passed the matched Jev questions in both image orders.
Different real objects produced two unsettled comparisons and one failure. Two independent
camera views of the same Auckland Museum bowl gave foot-ring visibility scores of 0.90 and
0.91, and finish scores of 0.42 and 0.56. Both views show the same physical foot-ring
construction under different framing. The experiment shows that a low finish score alone
cannot localize an object defect. Use exact crops, construction checks and retained render
evidence together. The workflow preserved the original questions and thresholds.
[Bowl AM 1545, photo 5](https://commons.wikimedia.org/wiki/File:Bowl_(AM_1545-5).jpg),
[photo 7](https://commons.wikimedia.org/wiki/File:Bowl_(AM_1545-7).jpg)

The 12 focused campaign and skill tests passed inside the workspace sandbox. A broader
offline-suite run was stopped after failures, including fixtures that bind local sockets.
That result does not establish a full-suite pass inside the render profile. Ruff, type
checking, the skill validator and `git diff --check` passed.

## Campaign implementation and later validation

The project-local launcher passed a real 64 px Metal and GPU OIDN render with enforced
workspace writes, network restrictions and child inheritance. The installed CLI passed
preflight, and the installed MCP server verified Seedwell's 61 distinct photographs.
Breakwater, Meridian and Seedwell delivery regressions validated archive members and reopened
16, 14 and 97 editable objects respectively. They retained review-needed status.

The first release attempts exposed an entry point problem. A fresh Codex shell could pick up
the globally installed CLI, whose native work had no Metal access in that shell. Two trial
sessions went on to call the installed Blender application and import `bpy` directly after
preflight failed. The macOS reports attribute the resulting segmentation faults to those
Codex parents. Several fault stacks terminate in Blender's Metal backend detection at a null
address. Those trial sessions and all owned validation workers were stopped. Strict signature
verification and Gatekeeper assessment accepted the installed Blender app as notarized.

The hardened launcher denies file access to the installed Blender bundle and Homebrew cask,
and checks that denial from inside Seatbelt. The authoring and construction-check workers
now use the same offline Metal profile as the renderer. A failed device check exits before
authoring scripts or Blender scene imports. The skill explicitly stops modeled work at a
preflight failure. A read-only negative probe confirmed read denial on the installed executable.
A separate harmless executable showed that read denial alone does not prevent process execution.
The pinned runtime now enforces an explicit Seatbelt execution denial for `Blender` and
`blender`. The same inert executables ran with the earlier runtime and were denied by the
current runtime while ordinary commands still ran. The current runtime also passed the
64 px sandboxed Metal and GPU OIDN preflight using the locked Python module.

After the user reported continuing crashes, 23 owned trial and render processes were
stopped. A process check found no remaining trial, renderer or Blender app process. At
00:52 EST, the latest Blender crash report was still the 00:18 EST Codex child crash.
Strict signature verification and Gatekeeper assessment again accepted the installed app.
The desktop launch was left for the user's normal session, and the trials and current
sampling controls remain unfinished.

The owner labeled eleven development cases Sound. The existing matched rubric and an
experimental rubric that isolates visible defects both returned Unsettled on all eleven.
The owner also labeled all seven initial holdout pairs Sound. Separate source- and crop-based
checks established two obscured-feature cases and three cases with documented cracks or chips.
The resulting six-case diagnostic comparison recorded no false passes, but both variants
abstained on the sole Sound case. The existing rubric settled one defect and one visibility
failure. The experimental variant settled two defects and one visibility failure. This small
panel does not qualify either evaluator. The original owner labels remain intact.

## Stop point, November 14, 2026

A broad offline run overlapped fingerprint-changing edits and native jobs and reported six
failures. An earlier stable run passed 825 tests. After fixing a same-file copy in flat
packaging, the stable suite passed 830 tests with `just test -n 6`. The regression test covers
authored monochrome, compact and dark SVGs. Lint, type checking, the skill validator and
`git diff --check` passed. These checks establish offline behavior.

The fresh Aftertone session worked around the flat packaging error by moving some artwork out
of the campaign. A follow-up with the fixed tool restored the lockup, monochrome and compact
variants and verified the archive. Aftertone is ready for exact-artwork review. It served as
development evidence for the fix and needs a replacement held-out brief.

The 64 px Metal and GPU OIDN proof passed on the earlier hardened tool revision. The next
preflight, started after the flat fix changed the code fingerprint, was interrupted when the
owner stopped work. It produced no current preflight receipt. At handoff, the owned Blender,
render and trial processes had exited.

### Resume 3D validation

1. Install the matching tool and skill in the scoped Codex project on Apple Silicon. Verify
   the pinned runtime and its companion host, then run the workspace boundary checks and a
   real Metal and GPU OIDN preflight. Stop native work if either check fails. Run only the
   sandboxed campaign worker for native work.
2. Regenerate the 8,192 / 0.01 controls on that exact revision and runtime. Include the
   0.02 degraded comparison and an independently authored held-out scene at 0.01 and the
   stricter comparison threshold. Present the packet for explicit owner approval. Verify
   coverage for each material class before reusing any approval. The interrupted Breakwater
   controls have no completed receipt.
3. Finish Jev calibration with independently labeled held-out cases for sound construction,
   visible defects and insufficient evidence. Preserve the owner's original labels. Freeze
   the evaluation before running it and require zero defect or insufficient cases called
   Sound. Report errors by class. The experimental triage run reached the request limit
   with one pair outstanding. Obtain a concrete budget extension if needed. The production
   evaluator has no passing held-out result.
4. Run the Found42 and prior trial regressions, including interruption and reuse of verified
   views on the final revision. Finish three fresh release trials covering an original modeled
   object, supplied artwork adaptation and a brief with no prescribed medium. Freeze a
   replacement for any brief used to tune the workflow. Switchyard and Cairn were interrupted
   before a modeled preview. Record 40 distinct real photos per modeled design with varied
   angles and lighting, matched construction evidence and independent holdouts.
5. Resolve mandatory Jev findings on the current artwork. Verify the hero and all four
   inspection angles, reopen each editable scene from its delivery archive, and verify the
   flat assets and archive hashes. Obtain exact-artwork approval for every release trial
   before declaring production qualification.

The local workspace retains frozen briefs in
`logos/campaign-release-development/frozen-release-briefs/`, session events in
`logos/campaign-release-development/hardened-release-trials/`, and evaluator inputs in
`logos/campaign-release-development/calibration-heldout-verified-cases/`. The repaired
Aftertone review ZIP is under
`hardened-release-trials/03-aftertone/aftertone/exports/flat-delivery-8f94787b24f9916c/`
within that development folder. The repository excludes these local artifacts.
