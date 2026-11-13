---
name: logo-maker
description: Logos and brand marks. Use when making, redesigning, or improving a logo, app icon,
  favicon set, or social avatar for any project, business, product, or profile, from an idea, a
  reference image, a repository, or a brainstorm.
---

# logo-maker

You are the designer and tool operator. Read the project and the conversation, author the vector
geometry and scene, run the tools, and open the results. Ask the user for decisions about their
brand, exact artwork, or direction when the answer changes the work. Handle TOML, paths, geometry,
render settings, file formats and QA yourself. Build every image from geometry, fonts, materials
and light. Jev judges supplied evidence.

## Choose the deliverable

| User asks for | Start here |
|---|---|
| A logo, favicon, flat icon, avatar, a quick concept, or another size of an existing mark | [Flat assets](references/flat-assets.md). Use this for an underspecified logo request and show a visible result early. |
| A 3D hero, editable Blender scene, or a set of selected 3D designs | [3D studies](references/studies.md). Author from the brief, compare concepts, and deliver the selected designs on Apple Silicon. |
| The production-qualified judged export set | [Qualified 3D workflow](#qualified-3d-workflow). Start with the shared flat symbol, then build the 3D object. |
| Continue or fix an existing job | Find its logo folder and run `status`. Use [recovery and delivery](references/recovery.md) to identify the next stage. |
| Try to beat a previously exported logo | Use [the improvement workflow](references/recovery.md#improve-a-published-logo) in that logo folder. |

Keep exact artwork, spelling, colors and geometry when the user asks to preserve them. Ask which
direction matters only when the choice would change the deliverable. When the user delegates taste,
make a brief-based choice and disclose it when showing the work. Bundled regression examples supply
neither design ideas nor a quality floor.

## Find the tools and keep one target

Read [setup](references/setup.md) when tools or dependencies are missing, or when changing hosts.
For 3D, use Apple Silicon macOS and run `logo_doctor` or `logo-maker doctor` in the environment
that will run the job. A missing Jev key leaves study review pending. You can start the design,
render, and delivery using the [study workflow](references/studies.md).
Before investing in a production 3D job, locate a matching reviewed sampling profile and an
independent craft reference. Doctor checks tools and devices. Use [qualification
preflight](references/recovery.md#qualify-the-render) to check profile scope and
[reference setup](references/recovery.md#choose-the-craft-reference) to establish the quality floor.
Use the flat recipe's import check for flat work. Both paths require access to write and inspect
local artifacts.

For a new 3D job, call `logo_new` or run `logo-maker new <slug> --name "Brand Name" --out "$logo_dir"`.
Choose a fresh absolute output folder in the project or where the user requested. Keep the returned
`logo_dir` as the target throughout. For example, `logo-maker status "$logo_dir"` or
`logo_status(target=logo_dir)`. In the MCP example, pass the actual path string. If the server uses
a different filesystem, use the CLI where the files live. For existing work, use its absolute folder
containing `brief.toml` and start with `status`. Confirm the target before responding to a missing
brief or existing-folder error.

CLI exit `3` with `AUTHORING NEEDED` and MCP `status: authoring_needed` are expected stops. Read the
message and details, open the listed files or artifacts, do the named work, then rerun that stage
or the prerequisite it names. Some paths name files to create. Others are evidence to inspect,
such as a sampling sidecar. CLI exit `2` and MCP tool errors carry actionable failures. Read their
cause before retrying. Keep one stage running per logo folder.

## Qualified 3D workflow

Use the stage name with `logo-maker <stage> "$logo_dir"`, or its `logo_<stage>` MCP tool with
`target` set to the absolute folder. Use the individual stages to locate stops and keep expensive
work bounded. `run` chains the normal pipeline and shares one budget across rendering stages.
An active improvement follows `improve` throughout.

1. **Brief.** Read [brief creation](references/brief-creation.md). Fill the generated `brief.toml`
   and `brief-evidence.toml` from the user's words, project files, and supplied art. Describe the
   real activity, who encounters the mark and where, and its primary intended impression. Capture
   owner mandates and leave optional choices open. Run `brief`. Advance after it writes a passing
   `ideation/requirements.json`. Changed reviewed inputs need `brief --revision-reason "…"` on the
   CLI or `revision_reason` in MCP. Read [recovery](references/recovery.md) for affected stages.
2. **Intake and ideation.** If brand colors or fonts already exist, preserve them. Otherwise use
   the generated `ideation/proposals.toml` to give `intake` six distinct candidates for each
   missing choice. Then write 8–40 distinct `[[metaphor]]` entries in `ideation/metaphors.toml`.
   Each describes what would be seen and what it conveys. Start with 8–12 strong ideas and add
   more when they explore a different visual direction. Run `ideate`. Its text combinations
   narrow to a shortlist and `concept.json` files. Read [concept authoring](references/concepts.md)
   for proposal fields and reference routes.
3. **Design the symbol and object.** Run `plan` to get the templates and review the completed
   plans. For every shortlisted concept, author `motif.py` or supply a contract-clean `motif.svg`.
   Run `motifs`, open each `motif-sizes.png`, and tune the starter `scene.toml` files named in
   the first successful build's authoring stop. Write `construction.json` and keep its current
   description in sync with `concept.json`. Recheck the plans and motifs before rendering.
   Use [concept authoring](references/concepts.md) for the exact authoring order and checks.
4. **Render and inspect.** Run `refine`. Open the returned artifact and its prior revision, then
   write `inspection.json` with the returned revision ID. The tool can stop at one concept before
   reaching the next. Repeat for each current revision. Compare visible differences and revise the
   source when critique is unresolved. Use [refinement records](references/refinement.md) for
   inspection, critique and diagnosis fields. Show the user the best supported directions when
   their preference would determine the outcome.
5. **Qualify and export.** Before `preview`, confirm the brief includes the intended finish and
   a usable craft reference. Before `finalize`, check sampling profile scope for the host and
   materials. See [recovery and delivery](references/recovery.md) for both requirements. Run
   `preview` to select finalists, then `finalize` and open any final inspection it requests.
   After `finalize` records a winner, run `export`. Open the contact sheet and transparent
   hero and check the current manifest before handing over the files.

## Show the result

Give the user a visible image and direct links to the requested files. For a 3D study, show the
overview and link the ZIP, then state the visual, owner, and qualification outcomes that apply.
For a qualified 3D set, link the export folder, contact sheet and main assets. Use
`ideation/winner.json` for the selection reason and `run.json` for reported Jev usage. Report
unknown cost when telemetry is missing. Keep earlier renders and published exports available.
