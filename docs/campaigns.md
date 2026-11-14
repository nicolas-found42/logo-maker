# Codex branding campaigns

This is the contract for ADR 0002 and the approved Codex branding workflow.

## State and decisions

`campaign.json` records scope, owner decisions, limits, consumed work, selected designs and
revision history. A campaign is one logo folder and permits one active writer. Research is
recorded in `research.md`; approval binds that file, `brief.toml`, and the chosen medium.
Approve proposed directions before rendering previews. Selection binds the verified preview
archive, concept directions and current brief. Geometry changes preserve direction approval but invalidate
render/review/delivery evidence. Changed briefs require renewed approval. Owner notes record
actual user direction or an explicit delegation; the tool never infers acceptance from a pass.
Final acceptance names the exact study and its archive hash. Existing schema 1 campaigns keep
their recorded decisions and can be opened under the current runtime.

Every concept supplies `construction.json` with its critical features and construction sources.
References identify distinct captures, angle, lighting, covered features and development/holdout
role. Modeled production review requires at least 40 distinct captures. Flat and typographic
designs use visual, typography, and placement references. Each critical modeled feature needs
useful development and independent holdout coverage, with verified render and photo crops. Near
duplicates are flagged for inspection. References used to diagnose a repair are consumed as
development evidence; replacement holdouts are required for the next independent check.
Development-only diagnosis retains exact crops and excludes held-out photos from the provider
request. The formal review uses independent holdouts. An unmatched crop routes to evidence
repair. Pair-level findings are interpreted alongside direct scene measurements.

## Rendering and repairs

The campaign applies 8192 / 0.01 / automatic minimum to previews and inspection views. Heroes
render at 4000 px and downsample to transparent 2000 px; inspection views are 1000 px. Authored
named cameras provide matched close-ups. Cache keys include exact source, mesh dependencies,
renderer code, runtime, controls, seed behavior, camera choice and output resolution. Reuse checks
every retained file hash. Interrupted work preserves only completely verified views.

The project install pins a local Codex binary. CLI and MCP use a named workspace sandbox for
every render and reopen, and repeat boundary checks at each launch. A native preflight verifies
rendered pixels, Cycles Metal, and GPU OIDN. Geometry generators use the same offline Metal
worker, and the preflight is cached by launcher, renderer, Blender, and operating system.
The current device and workspace policy are checked at each invocation.
Direct photo requests use a public HTTPS domain allowlist, and Jev uses its own provider profile.

Three meaningful repair rounds per concept are included. Each records the defect, evidence,
single intended cause, previous revision and comparison outcome. Unchanged inputs do not earn a
new judgment. Inconclusive repairs stop for better evidence. Campaign time, native attempts and
provider requests persist across calls; failures consume their reservations. Missing provider
pricing stays unknown. An explicit cash ceiling requires a conservative pre-dispatch price bound.
Exhausted limits preserve prior artifacts and return a continuation decision. The estimate uses
measured previews to propose job limits at selection. Authoring and photo research happen in
the Codex session. Include their estimated ranges when proposing the whole-project budget.
The tool time ledger measures active campaign calls. A bounded prototype can verify a material
or construction risk before the owner approves a full direction.

## Qualification and delivery

Packed scenes reject external links, scripts, caches and unsupported dynamic dependencies.
Inventory includes named objects/materials, packed resources and exact scene bytes. Clean owned
workers reopen the source. GPU tracing and OIDN Metal proof are required on every render.

Packed-scene sampling profiles bind the actual runtime/code, settings, material scope and
positive/degraded/held-out cases with verified artifact hashes and owner decisions. New profiles
are pending until their comparisons are reviewed. Declarative profiles cannot certify packed
scenes. Technical, visual, sampling and owner states remain separate in all receipts.

Delivery verifies all selected designs together, streams archive members against their inventory,
and reopens each packed scene from the archived bytes in an isolated worker. The shareable package
contains transparent PNGs, editable Blender files and construction inputs, color/mono/compact SVGs,
favicons,
comparison sheets and usage guidance. Private source research, photo copies and raw Jev payloads
stay in a separate archive. Production requires current passing mandatory evidence and owner
acceptance. Review packages identify every unresolved dimension. No archive is called qualified
because its files merely validate.

## Release evidence

Use a pinned matching Codex skill/tool install. Calibrate the evaluator against independent
human labels, with tolerances frozen before testing. Retain results by class and the exact
rubric and model identities. Keep calibration examples separate from held-out evaluation.
Freeze three unrelated briefs before trials (original physical object, supplied identity
adaptation, and an initially unspecified medium). Start fresh
Codex sessions with the brief and installed skill, retain raw execution records and actual asset
inspection, and interrupt one job deliberately to verify reuse and invalidation. Previously used
Found42, Breakwater Supply, Meridian FM, Seedwell, Field Kettle, Alder Works and Northline are
regression fixtures. Replace any release brief used to tune the tool with a fresh held-out brief.
Record each unmet acceptance condition; a partial study never establishes production readiness.

The `evaluate` campaign action reads a panel directory named in its record. The directory
contains the reviewed crops, their inventory in `evidence.json`, and independently frozen
`labels.json`. The worker uses the restricted Jev profile. It reports mistakes by actual
and predicted label, includes unsettled results, and binds the exact model and rubric. The
development panel can contain a single class. A held-out panel must contain all three classes.
An evaluation that never recognizes a sound example cannot qualify the production evaluator.
The observable-feature variant is available for development experiments.
