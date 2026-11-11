# Paper construction and exposure probe

Refs #3. This is a controlled repair of visible color clipping, with actual Metal/GPU-OIDN
renders and retained independent review. It does not qualify the artwork. Issues #1, #3 and #4
remain open; no owner acceptance, finalist, winner, qualified sampling profile or production export
is claimed.

## Construction revision

The paper study now uses one continuous laminated U-shaped card. Three colored paper-skin regions
share an unbroken pale core. Broad, separate scores turn the two outer upright edges outward and
the lower dock forward. There is no backing panel or enclosing border. Seven referenced, closed,
consistently wound supported mesh assets describe the folded stock; the core has one connected
component. Pairwise Boolean checks detect no volume interpenetration above 1e-6 scene units cubed.

The earlier bonded-lap proposal remained construction-unsettled and was not rendered. A first
continuous-core proposal also remained unsettled. Clarifying that its colors denote skin regions
on one sheet, rather than fitted structural parts, gave a construction-plan pass (.77). Geometry
checks, the authored recipe, prior plan result and clarified result are retained. A plan pass
records coherent intent, not rendered execution quality.

## Controlled exposure comparison

Both retained cases use identical authored geometry, materials, camera, lighting, sampling and
`scene.toml`, including `exposure = -1.5`. Before the implementation change, the loader silently
omitted that field. Afterward it forwards the value to native Cycles view exposure. Only
`tool/scene.py` and `tool/blender/settings.py` differ in the render source inventories.

| Case | Retained revision | Near-white fraction | Mean RGB |
| --- | --- | ---: | --- |
| Exposure ignored | `0008-f57c4522d947-preview` | 77.83% | 254.98 / 255.00 / 253.23 |
| Exposure honored | `0009-18d06068d23e-preview` | 0% | 173.78 / 182.25 / 168.15 |

The fixed region is x=640:850, y=350:580 in each native 1000 px render: 48,295 opaque pixels.
Near-white means every RGB channel is at least 250. The pale-green upright now retains visible
tone and fold modeling. This diagnoses display clipping; it is not a noise or sample-cap repair.
The independent image comparison scores local critique resolution .95 and distinctness .03.
That low distinctness is expected for this control and is not counted as another visual concept.

## Independent qualification

Creative craft / brief fit / material intent / description match are .35 / .59 / .52 / .68.
Independent reference-relative craft fails against both accepted Chief treatments in both orders.
The remaining creative dimensions and own-brief fit are not settled. The local color repair does
not close the authoring task or establish the required visual standard.

The manifest retains two source-bound renders, native logs, exact source blobs, inspection,
judgment, comparison, and all 12 new plan/creative/comparative/eligibility provider requests with
their image assets. Shared blobs refer to earlier immutable bundles; the original full histories
and unrendered proposals remain in the preserved ignored evidence directory.

## Runtime and verification scope

The separate fresh synthetic runtime fixture performs an actual 4000-to-2000 Metal/GPU-OIDN
render, verifies 31 low-level export hashes and sends live final QA. Its canned brief/plan answers
qualify only that test fixture. Sampling review preserves the prior winner. Its outputs do not
constitute a qualified artwork export.

Run `uv run --locked python scripts/verify_reconciled_refinement.py` to verify all four immutable
bundles. CI runs the same offline verifier without a GPU or provider key. Validation logs and
source bindings are retained under `validation/`; software checks and model judgments remain
separate from owner artistic acceptance.

| Check | Observed result |
| --- | --- |
| `just test` | 452 passed, 6 deselected, 49 upstream warnings in 305.78 s |
| `just lint`, `just type`, `just hooks` | Passed |
| `just render-example` | 2 passed in 4.97 s; default-exposure GPU regression |
| Explicit live M5 final-runtime test | 1 passed in 61.99 s |
| `uv build` | Wheel and source distribution built |
| `logo-maker doctor` | 48/48 checks passed; no dependency changes |

The runtime source bytes are committed as `16e46a9`; later bundle/CI additions do not change the
renderer. `validation/source-binding.json` binds the complete tested runtime, tests, verifier and
CI/configuration bytes. The native fixture's kernel-cache state and background-load effects are
unknown, so these timings are observations rather than a performance comparison.
