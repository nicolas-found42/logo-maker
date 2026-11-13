# Apple Silicon study workflow validation, November 13, 2026

The logo-maker CLI and MCP were exercised on Apple Silicon with Blender Cycles Metal and GPU
Open Image Denoise. The runs below are local validation studies. The study IDs refer to folders
under `logos/workflow-validation/`, which is outside the tracked source tree.

| Campaign | Evidence |
| --- | --- |
| Alder Works custom hand plane | `study-38a78029bf76` and `study-2f529eede5a5`. Packed Blender input, four inspection angles, transparent hero, flat exports and local calibration. The revision used a turned front knob, a shaped rear grip and a visible opening in the sole. |
| Northline existing wordmark | `study-10a0694a087c` through MCP stdio with both Jev credentials removed. `study-e10f0426aa95` included the separate dark-surface compact variant. The authoring fixture uses supplied outlined lettering and a declarative scene. |
| Found42 four-design regression | `study-9703d970291c`. Four selected packed scenes, 20 verified Metal views, four transparent heroes, and 40 distinct reference images per design. All 291 ZIP entries matched the delivered manifest, including the manifest itself. |

The first Alder Works build had a spherical front grip and a solid underside. Inspection against
the plane photographs led to geometry and surface changes. The revised scene retained the
original study and generated two independent seeds at the same settings and a separate run with
the hero seed and a lower adaptive threshold. The hero and lower-threshold runs retained
multilayer diagnostic EXRs. This shows the local comparison path and does not qualify a profile.
The front grip and sole construction were compared against related products. [Veritas low-angle jack plane](https://www.leevalley.com/en-us/shop/tools/hand-tools/planes/bevel-up/118457-veritas-low-angle-jack-plane)

The initial Northline icon was low contrast on a dark surface. A lighter version of the same
compact silhouette was exported and inspected at 16 px and 32 px. The no-key MCP call recorded
review as pending, and a later live review ran against the delivered ZIP and recorded a failed
visual outcome. These results exercise delivery and review recovery. [Gemini acrylic letters and logos](https://geminimade.com/signage/letters-logos/flat-cut-acrylic/)

An earlier Found42 regression used the same four packed sources. Its transparent heroes had
SSIM of 0.9969 or higher against the previous delivered heroes. Live review of the 40-photo
package used one craft photo and one holdout per design, each presented in both orders. The
whiteboard, notebook and side label failed the overall visual rubric. The split badge remained
unsettled. Structural checks passed for all four. The samples were related objects, and physical
Found42 samples were unavailable for direct comparison.

`logo-maker doctor` reported 50 of 50 checks in both the project and installed environments.
Lint, type checking and generated documentation checks passed. The final offline run passed
821 tests, and both GPU regression tests passed. Earlier parallel runs failed while other
validation or code edits were in progress.
The affected tests passed together in isolation before the full rerun. The skill was copied
through the installer and its bundled references resolved. The production profile preflight
on this checkout returned `profile_stale` for the code and lockfile digests. Production
qualification requires a current reviewed profile.
