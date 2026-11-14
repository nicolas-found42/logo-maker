# Codex branding campaign

Use this route for a complete new 3D brand or a modeled adaptation on Apple Silicon. You operate
the tools and author the geometry. Use an existing directory for continuation. Call
`logo_campaign(target=logo_dir, action=…)` or run `logo-maker campaign <logo-dir> <action>`.
Use the [project-scoped install](setup.md#codex-project-installation) and run `preflight`
before native work. Use `author` to run a construction generator with the offline workspace
profile. Pass the generator path relative to the logo directory as `script` and its optional
string arguments as `args` in the record.
For the CLI, repeat `--concept ID` for selected designs, pass the owner's actual words via
`--note`, and put the action's JSON data in a file passed as `--record FILE`.

1. **Research and brief.** Create the logo folder with `new`, then run `campaign init`.
   Read project and supplied artwork, research the brand and real materials, and write cited
   `research.md` and `brief.toml`. Follow [brief creation](brief-creation.md) to establish intended
   appearance, identity constraints and uses. Summarize the researched brief for the owner.
   Run `approve-brief` with the decision or explicit delegation and the record's `medium`
   (`modeled`, `flat`, or `typographic`). Begin ideation after this step. For flat or typographic
   campaigns, use [flat assets](flat-assets.md) to author the master and compact variants.
   Record visual and usage references in the research, then follow direction approval and use
   `flat-preview`, `select`, `flat-accept` with the preview `archive_sha256`, and `flat-deliver`.
2. **Directions.** Explore distinct physical objects and original arrangements of existing
   artwork. If feasibility is uncertain, model a small sample and run `prototype` with one
   concept and a `risk` record. Inspect the sample before recommending that direction. Present
   the research-backed pitches and record `approve-directions` for the concepts the owner
   authorizes for modeling. Author motifs and geometry as in [3D studies](studies.md). Run
   `preview` with those IDs and open the returned sheet. Present tradeoffs and run `estimate`.
   Include expected research, authoring and qualification effort alongside measured tool costs.
   Record `select` for every design the owner chooses and the agreed budget.
   The optional
   selection record sets `wall_seconds`, `renders`, `requests`, and `repair_rounds` (default 3).
   Report unknown charges as unknown. Only set `request_max_usd` beside a `max_usd` ceiling when
   you can document a conservative per-attempt price bound.
3. **Construction and references.** For each selected design save a packed `source.blend`,
   `construction.json` and `references.json`. Use `fetch-photo` with `url`, `source`, and
   `license` for a direct public image URL. Enter its returned path and provenance in the
   reference record. Run `references` to find specific coverage gaps before `render`.
   The scene should reopen with named editable parts and a clear hero camera. Cameras named
   `Study front camera`, `Study grazing camera`, `Study rear camera` and
   `Study underside camera` can supply matched inspection views. Keep source generators or
   documented build inputs in the concept folder. In `construction.json`, list their relative
   paths in `sources`, name actual material classes in `material_classes` and list visible
   construction risks in `critical_features`.
4. **Review and repair.** Open the transparent hero, inspect the retained views and the 16/32 px
   light/dark sheet, and compare critical features with the photographs. Run `diagnose` to judge
   the craft photos and retain the exact crops in the diagnostic record. Run `review` when the
   design and independent holdouts are ready for the formal comparison. Read the
   paired visibility and execution judgments in both image orders. If a pair is unclear, repair
   the evidence before judging the object. If results stay unsettled, compare one photo to itself
   and two independently photographed objects with the same visible feature in both orders.
   Inspect the exact crops. A real-photo pair that scores poorly calls for checking comparability
   before changing geometry. Keep these diagnostic results outside the production decision.
   Use `check-construction` for targeted checks of open bores, clearance, and expected
   surfaces on the exact editable scene. Pass one selected concept and a `rays` array
   with an `id`, model-space `origin`, `direction`, `distance`, and `expect` (`open` or `hit`)
   for each ray. A hit may name the expected `object`.
   Record `repair` for one concept with `diagnosis`, `evidence`, `change` and
   `comparison` before editing. Replace consumed holdouts, render again and compare the actual
   revision with the strongest previous result. Use `compare-repair` with `observations` and
   `outcome` (`improved`, `unchanged`, `worse` or `inconclusive`). Cache hits reuse verified views.
   An exhausted limit needs a concrete continuation decision before `extend`.
   For an inspection render while the photo set is incomplete, pass `{"inspection_only": true}`
   to `render`. Deliver it with review-needed status if useful. Complete coverage for the next
   production attempt.
   While rendering, read `status` to see which views are pending, rendering, verified, or
   failed. Present the complete inspection sheet only after the study verifies.
5. **Sampling and acceptance.** Run `qualify` with `candidate` and `holdout` concept IDs to
   prepare controls for the hardware, code, controls and material scope. The holdout is an
   independently authored scene covering the same classes. Open the comparison and native
   images with the owner using the returned `review_packet`. Record the reviewed
   `qualification_id`, `profile_sha256` and `decisions` only from the owner's result.
   Decisions are `positive: accepted`,
   `degraded: rejected`, `held_out: accepted` when those outcomes are observed. Report any
   remaining visual findings. Use `accept` with the actual owner's acceptance of the exact
   delivered study. Include its `study_id` and `archive_sha256` in the acceptance record.
   Sampling approval and acceptance answer different questions.
6. **Delivery.** Run `deliver` with a `usage_guidance` string. Link the overview and
   `branding.zip`, then state technical, visual, evaluator, sampling and owner status. Check the receipt
   for the reopened scenes and all four verified inspection angles. Keep `evidence.zip`
   in the project archive. The owner can use a review package with open findings. Continue
   repairing mandatory findings before claiming a qualified package.

## Photograph records

Keep 40 distinct real captures per design with varied camera angles and lighting. Use the
[study photo format](studies.md#establish-the-brief-and-physical-reference) and add
`capture_id`, `capture_source` (the photographer or capture session), `angle`, `lighting`,
and `features` (names from `critical_features`) to each row. Provide an independent matched
`holdout` and a matched `craft` photo for each critical feature. Name one critical feature per
matched crop. Use research rows for additional
views. Record whether a paired image can be sent to Jev with `review_allowed`; retain its source
and license. Inspect near-duplicate pairs before recording `distinct_capture_review`. Replace
a holdout once it has informed a repair. Use photos of physically comparable parts; show the
corresponding region at useful size in both images.

Run `qualify` without a record to reuse compatible approved coverage from this project or
list the material classes that need controls. For a previously approved packed-scene
profile from another project, pass its `profile.json` path as `approved_profile`
to `qualify`. Keep the adjacent approval and control files together. The tool checks the runtime
and material coverage before importing the profile.
