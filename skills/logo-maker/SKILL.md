---
name: logo-maker
description: Logos and brand marks. Use when making, redesigning, or improving a logo, app icon, favicon set, or social avatar for any project, business, product, or profile, from an idea, a reference image, a repository, or a brainstorm.
---

# logo-maker

`logo-maker` turns a brief into a rendered 3D logo and a full export set. You supply the thinking
that needs a designer's eye: the brief, the metaphors, and each concept's motif and scene. The tool
builds and judges everything else with Jev and real renderers. Every image comes from geometry, fonts,
materials, and light.

Derive every design choice from the brief: the brand's own name, purpose, audience, and tone. Each
logo is designed fresh for its owner.

## 1. Check the toolchain

Run `logo-maker doctor`. Done when it exits 0 (no `FAIL` lines). A `FAIL` line prints its fix
command; run it. When `logo-maker` itself is missing, run `just setup` in the logo-maker
repository, then `uv run python scripts/install.py --agent <host>`.

## 2. Write the brief

Create the folder: `logo-maker new <slug> --name "<Brand Name>"` (`--out DIR` puts it elsewhere). Fill
`brief.toml` from the input you were given:

| Input | Where the brief comes from |
|---|---|
| An idea or description | The user's words. Ask (one form) only for what you cannot infer: the name, and who it serves. |
| A repository | README, package metadata, docs, and the product's own UI copy: name, what it does, for whom, its voice. |
| Reference images | Copy them into `inputs/`; add a `[[references]]` entry each. `use = "style"` lets Jev read their style. `use = "geometry"` traces the image into shapes; use it only for art the user owns. |
| "Brainstorm" | The conversation so far and any project at hand; state the inferred name, summary, and tone back to the user in your final report. |

Leave `[palette]` and `[fonts]` out unless the user or the brand already has them. Done when
`logo-maker intake <slug>` gets past the brief check.

When the brief lacks a palette or fonts, intake asks for proposals in
`ideation/proposals.toml`: write six `[[palette]]` entries with contrasting characters (each
with `primary`, `secondary`, `accent`, `background`, `ink`) and six `[[fonts]]` pairings of real
google/fonts families. Each proposal expresses the brief's tone a different way. Rerun intake; it
drops palettes that fail WCAG AA (the rejects are recorded under `dropped_wcag` in
`ideation/palette.json`) and Jev picks one of each. The picks land in `ideation/palette.json` and
`ideation/fonts.json`.

## 3. Write the metaphors

Fill `ideation/metaphors.toml` with 20 `[[metaphor]]` entries: what the mark could show and why that
fits the brief. Spread them across kinds: literal objects from the brand's world, actions it enables,
abstract forms of its tone, letterforms from its name or initials, and double meanings that join two
of these. Done when 20 distinct ideas are written and no two depict the same thing.

## 4. Run to the first authoring stop

`logo-maker run <slug>`. It runs intake, builds up to 1000 concepts (metaphor x 3D treatment x
material), judges them in three rounds, and keeps a shortlist of 8. It then stops with `AUTHORING
NEEDED` and lists one `concepts/<concept>/motif.py` per shortlisted concept. Those files do not exist
yet — the listed paths are what you create in step 5.

## 5. Author each concept

For every listed folder, read `concept.json` (metaphor, treatment, material, and their
descriptions), then:

1. **Motif.** Write `motif.py` with the motif API
   ([references/motif-api.md](references/motif-api.md)). Build the mark from two or three bold
   shapes with a clear silhouette; let negative space carry a second meaning where the metaphor
   allows; use one to three palette roles, one role per part that should read as its own color or
   material. Shape it for the treatment: solids and extrusions want chunky shapes, plates want the
   mark well inside the rim. Read "How a treatment consumes the motif" in
   [references/scene-grammar.md](references/scene-grammar.md) so you know what the treatment builds
   from your shapes (for example, `tube_lines` traces filled shapes into tubes).
2. **Check.** `logo-maker motifs <slug>` builds every motif and writes `motif-sizes.png` beside it.
   Look at each sheet: done when the mark reads at 16 px and 32 px and matches its metaphor. On first
   success it also writes each concept's starting `scene.toml` from the treatment and stops once for
   step 3.
3. **Scene.** Tune each `scene.toml` with the scene grammar
   ([references/scene-grammar.md](references/scene-grammar.md)): each palette role has its own
   `[materials.<role>]` table and component, so set heights, edges, material presets, colors, camera
   tilt, and light per concept. Size the mark with `[mark] scale` so it clears every rim, recess wall,
   and ring of text. Per-kind component fields and defaults:
   `logo_maker/catalog/components.md`; material presets and their parameters:
   `logo_maker/catalog/materials.toml`; tuning ranges (tilt, framing, tube radius): the grammar's
   "Tuning ranges" section. Write `scene.py` only when the components cannot express the concept.

Done when `logo-maker motifs <slug>` exits 0 and every scene names only catalog materials and lighting
rigs.

## 6. Run to the end

`logo-maker run <slug>` again. It renders GPU previews, keeps 3 finalists judged on the images,
renders finals at 4000 px, and runs up to five QA rounds per finalist (readable, nothing cut off,
clean edges, no veil or box, recognizable at 32 px), fixing scenes after a clear fail (Jev P < 0.3
on a check, or a code-detected veil or cut-off). An edge failure returns scoped diagnosis work.
A head-to-head picks an eligible winner and
the export set lands in `exports/`.

When finalize stops with `AUTHORING NEEDED`, read `qa/rounds.jsonl` and the concept’s
`.build/final.sampling.json`. `sampling_review_needed` means the machine profile, diagnostics or
comparison still needs qualification; `refinement_needed` names the artifact and dimension to
repair. For sampling/profile/budget work, read [the sampling policy](../../docs/automatic-sampling.md)
before editing controls. Retain user overrides and compare independent-seed noisy/denoised detail
before changing one sampling control. Route geometry, typography, filtering, resolution, denoiser
detail loss and alpha defects to scoped refinement. Report device, cap, noise and budget outcomes
separately from craftsmanship, brief fit and preference.

In `qa/rounds.jsonl`, a `needs_simpler_motif` result
means the mark lost its shape at 32 px. Simplify that motif (fewer, larger shapes; thicker strokes)
and run again.

## 7. Report

Look at `exports/contact-sheet.png` and `exports/hero-transparent.png` yourself before reporting
(the mono mark is a one-color silhouette in the brand ink; its contact-sheet chip uses the brand
background, the surface the ink is designed for). Report the winning
concept and why it won: `ideation/winner.json` holds the winner, a `reason` string, the win tally,
and every match row; a tie on wins is broken by deterministic slug ordering and the reason says so.
Also report the export folder and the Jev cost from `run.json`.

## Improve an existing logo

`logo-maker improve <slug>` archives the current round under `history/` and keeps the current logo
as the floor. Write fresh metaphors (step 3) and motifs (step 5) as it asks. The new winner replaces
the exports only when it beats the floor head-to-head on images; otherwise the current logo stays.

## MCP

`logo-maker mcp` serves each stage as a tool (`logo_new`, `logo_intake`, `logo_ideate`,
`logo_motifs`, `logo_preview`, `logo_finalize`, `logo_export`, `logo_run`, `logo_improve`,
`logo_doctor`). A tool that needs files from you returns `authoring_needed` with the exact paths.
