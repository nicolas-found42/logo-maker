# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Beginner instructions for flat assets and staged 3D qualification, including profile
  preflight and recovery. The [November walkthrough](docs/research/beginner-workflow-validation-20261113.md)
  records the checks and open qualification work.
- Optional `studio_45` lighting with a 45-degree key, fill and rim lights. Dedicated visual
  comparison remains open.

### Changed

- `scripts/install.py` registers the MCP server on every host as
  `uv run --quiet --project <checkout> logo-maker mcp` (live source, no `logo-maker` on PATH
  needed): `~/.omp/agent/mcp.json`, `claude mcp add-json --scope user`, and
  `[mcp_servers.logo-maker]` in `~/.codex/config.toml`. Claude now gets a linked skill instead of
  a plugin copy. Run it with `uv run python scripts/install.py` (it imports `tomlkit`). The root
  `.mcp.json` uses the same command, and the Codex plugin ships the skill only.
- The MCP `logo_doctor` tool returns the same rows as `logo-maker doctor` (environment checks
  included) plus `passed`/`failed` counts; both come from `logo_maker.doctor.checks()`. Every
  check is required: `Adapter.required` and the `warn` state are gone, and a cold Metal kernel
  cache now fails with its fix (`just warm-gpu`).

### Fixed

- LuxCoreRender renders on macOS arm64. The hang blamed on pyluxcore's OpenMP runtime was
  logo-maker calling `RenderSession.WaitForDone()` without `UpdateStats()`: LuxCore checks
  `batch.haltspp`/`batch.halttime` only inside `UpdateStats()`, so the render never halted. The
  renderer now polls `HasDone()` + `UpdateStats()` in-process; the macOS arm64 guard, child
  process, and `LOGO_MAKER_LUXCORE_TIMEOUT` are gone.
- The Blender builder's scene export (used by the mitsuba, luxcore, and three renderers) called the
  nonexistent `bpy.context.evaluated_depsgraph()`; it now calls `evaluated_depsgraph_get()`.
- LuxCore materials and lights receive RGB instead of the export's RGBA (LuxCore rejected the
  4-value color).
- `just setup` and CI install node-canvas's Homebrew build libraries (cairo, pango, and friends):
  `canvas@2.11.2` (via trianglify) has no Node 24 prebuild, so `npm ci` failed without them.
- Overlapping MCP stage calls no longer corrupt stdout: they share one redirect, so progress never
  reaches the JSON-RPC stream and `sys.stdout` is restored once the last call ends.
- MCP stage tools check for `brief.toml` like the CLI, so a mistyped target fails instead of
  reporting `done` and creating folders, and every `RuntimeError`/`ValueError` reaches the agent
  as an MCP error with its message (the framework hides unexpected exceptions' text).
- A malformed or invalid `brief.toml` is reported as a `brief.toml` problem (listed in `files`)
  instead of a `brief-evidence.toml` one; `logo-maker new` and the stage commands print one error
  line and exit 2 for an existing logo or an unusable slug.
- The skill's MCP tool list names `logo_brief` and `logo_plan`.
- Wrong-shaped authored files fail with an error naming the file instead of a traceback or silent
  corruption: `brief.toml` field types (`tone = "abc"` no longer becomes three tones),
  `proposals.toml`, `metaphors.toml`, palette hex values, `scene.toml` booleans used as numbers,
  motif `data-height` of `nan`/`inf`, a corrupt `run.json`, and malformed sampling diagnoses,
  profiles or provenance records (these fail closed).
- Tool output that is not UTF-8 no longer aborts a stage.
- The jev client caps `Retry-After` at 60 s and reports a 200 response with missing or malformed
  answers as a `JevError` naming the question ids, not a downstream `KeyError`.
- A rejected publication removes its staged copies after restoring the prior set.
- `ital=1` selects the italic file of a static-only font family.
- `dropped_wcag` in `ideation/palette.json` records `{proposal, palette, problems}`.
- The docs no longer promise PWA splash screens (`js/pwa.mjs` generates icons only), the README
  stage list includes `refine` and `status`, and `docs/jev-questions.md` no longer lists
  `brand_specificity` as an intake color question.
- The jev client rejects answers a decision cannot use: a `noul` outside [0, 1] (NaN, booleans),
  a non-finite `score`, and a `choice` that is not one of the question's options now raise
  `JevError` naming the question, instead of reading as "unsettled" or a unanimous unknown pick.
- `ideation/tournament.jsonl` rows carry an `input_hash` of their state and questions; an edited
  metaphor, treatment description or brief re-asks the affected pairs instead of reusing the stale
  pick. A malformed JSONL line names its file and line, and rewrites go through a temp file.
- Empty `[[palette]]`/`[[font]]` proposal tables ask for authoring instead of raising
  `StopIteration`.
- Preview and final screening stop messages include the eligibility reasons (for example "candidate
  pixels missing") and list the unresolved checks and retained evidence. The literal fit and
  structure checks use authored treatment and material descriptions when available.
- Motifs: a zero-area path names its layer in `MotifError`, `fit` scales a line by its non-zero
  axis, `low_poly` validates its sizes and point count, and `voxels` rejects a non-mapping spec.
- `scene.toml`: unknown material keys are rejected with the known ones;
  `emission_color` is validated and kept; non-finite component numbers and radii <= 0 are rejected.
- `fonts.text_path` returns `('', 0.0)` for empty text without resolving the font and raises
  `FontSpecError` for characters the font does not cover instead of dropping them.
- Adapter metadata: the licenses of `postprocessing` (Zlib), N8AO (ISC), `pwa-asset-generator` and
  `@gltf-transform/functions` (MIT) match their manifests (checked by a test); the `primitive`
  lookup is shared by the check and the runtime and ignores an empty `GOPATH`; the Chrome check
  accepts Google Chrome only; the HDRI checks test httpx, the client they use; the `coloraide`
  fix is `uv sync`; the Node check is time-bounded and names an unreadable version.
- Copy installs (`--copy`, `--agent skills`) bundle `docs/automatic-sampling.md` inside the skill
  and re-point the skill's links to it, replacing a leftover linked install instead of copying onto
  the checkout; `scripts/skill_check.py` also checks links whose text wraps across lines.
- `logo-maker new` escapes the name in `brief.toml` (quotes and backslashes survive) and rejects
  control characters before writing. `brief.toml` rejects blank tone entries, a palette value with
  a trailing newline, empty or NUL reference paths, and non-UTF-8 text with a `BriefError`.
- A long-lived process (the MCP server) no longer reuses a cached `run.json` after the logo folder
  was deleted or the file moved aside; malformed `stages`/`jev` entries are "not a valid run record".
- Brief review names a missing craft reference as a `brief.toml` problem and a missing
  `path`/`excerpt`/`baseline` field with its row id.
- Malformed `construction.json`, `concept.json` and `inspection.json` ask for authoring (or name the
  file and line) instead of raising `AttributeError`/`TypeError`; a failed revision archive removes
  its `.archiving-*` staging copy.
- `python -m logo_maker.benchmark verify` reports malformed or empty manifests as named errors.
- `primitive` is also found through `GOBIN` and every `GOPATH` entry; `ital=1` on a family with no
  italic file is a `FontSpecError` instead of silently using the upright face.
- Exports: the `hero-paper.png` shadow is offset once (it was shifted twice, 36 px), a missing
  `final.png` is an `ExportError`, and a hero whose mark spans under 5 % of the frame is rejected
  instead of resizing the avatar without bound. HDRI downloads land under a temporary name, so a
  killed render cannot leave a truncated file in the cache. Non-positive image sizes raise
  `ValueError`.
- The scene grammar docs state that only `renderer = "cycles"` renders; mitsuba, luxcore and three
  load but `render()` refuses them under the GPU-only policy.
- The "no brief" error from a stage run with `--out` (MCP `out`) now names the command that
  creates that folder, `logo-maker new <target> --out <folder>`, with the target shell-quoted.
- A `run.json` whose Jev cost or token total is `null` (recorded when the provider omitted
  telemetry) reloads instead of being reported as an invalid run record.
- `logo-maker new` with a name that is not valid Unicode text (a lone surrogate from JSON or an
  undecodable argument) is a `BriefError` and writes nothing; `brief.toml` paths that cannot be
  read (a directory, no permission) are a `BriefError` naming the path.
- `construction.json` and other concept JSON that is not UTF-8 is a named error for that file.
- Scene material `color` and `emission_color` must be exactly `#RRGGBB` when the scene loads,
  so the motifs-stage check catches `#GG0000` or `#FFF` instead of the render failing later.
- Intake: a style reference that is not a readable image asks for a `brief.toml` fix naming the
  reference; a palette proposal with a role outside `primary`, `secondary`, `accent`,
  `highlight`, `background`, `ink` is rejected (a typo previously skipped the WCAG check); a
  malformed `ideation/palette.json` or `fonts.json` (wrong shape, or a palette value that is not
  `#RRGGBB`) names the file and the fix.
- `LOGO_MAKER_CACHE` expands `~` and resolves relative paths instead of creating a literal `~`
  folder in the working directory; a value that cannot be used (a file, an unknown `~user`) is an
  error naming the variable.
- `motif.py` output that is not UTF-8 no longer crashes the motifs stage, and a failing script's
  own message reaches the error. Each run sets the previous `motif.svg`/`motif.json` aside, so a
  script that saves nothing fails with "wrote no motif.svg" instead of reusing the old motif, and
  a failed run puts the previous motif back instead of leaving its own partial output. A torn or
  wrong-shaped `.motif-state.json` re-runs the motif instead of failing every later call.
- CLI stages print `error: <message>` and exit 2 for stage errors (bad state files, tool and
  brief errors) instead of a traceback, as documented. `status` names a malformed
  `shortlist.json` or `revision.json`; a damaged `comparison.json` counts as unresolved.
- Host and export worker failures report the worker's exact `Type: message` instead of the tail
  of its traceback, so scene, file and export errors keep their wording even when the message
  contains newlines. A message over 2000 characters keeps its start (the failing tool) and its
  end (the cause).
- Damaged tool-written state no longer crashes `refine`, `finalize` or `export` with a bare
  error: a cached `judgment.json` or `qa/comparisons.json` row is reused only when complete
  (otherwise judged again), a `comparisons.json` that is not a list, a malformed
  `finalists.json`, and a `winner.json` without a concept id name the file and the stage to
  rerun, and a wrong-shaped `render-state.json` reads as not current.
- An authored `diagnosis.json` or `inspection.json` critique with the wrong types is reported as
  invalid (`invalid_diagnosis`, or a request to resolve the critique) instead of a `TypeError`.
- A wrong-shaped `.build/<quality>.sampling.json` reads as stale render provenance, an unreadable
  one is named, and a GPU profile preflight that outlives the budget is a `time_limit`.
- Scene type errors name the types in words (`must be int or float`).
- `ideate` re-asks stored stage-1, stage-2 and tournament rows that lack a field it reads
  instead of crashing. An unreadable `metaphors.toml` or `proposals.toml` (bad TOML, not UTF-8,
  a directory) names the file, and a metaphor `id` or `text` that is not a string is rejected
  instead of being stringified for jev.
- `improve` finishes as `floor_held` when the archived round had no `winner.json`, instead of
  failing after the whole challenger round.
- MCP stage tools keep the `authoring_needed` payload when a damaged state file stops the
  progress counts (`counts: {"unavailable": ...}`, as the CLI already did), and an `OSError`
  (path too long, a file where a folder belongs) reaches the agent with its path instead of a
  textless tool error or a CLI traceback. `logo_new` rejects a blank `out` instead of writing
  under `logos/`, and a blank `name` defaults from the slug as in the CLI.
- `plan` reviews every shortlisted concept and lists every `plan.toml` that needs work in one
  stop; a provider failure on one concept no longer hides another concept's authoring work.
- `export` before `finalize` says to run `finalize` instead of asking for `ideation/winner.json`,
  and `finalize`/`export` report an invalid `brief.toml` as authoring work like the other stages.
- Named errors for a damaged `concept.json` (shape, treatment or material), a non-UTF-8
  `scene.toml`, an evidence source or obligation baseline `path` that is not a string or not a
  file (an invalid baseline brief is reported against its obligation, not `brief.toml`), a
  shortlist whose ids share a concept folder, a brief that has not been reviewed yet, and a
  damaged `qa/owner-feedback.json` (file and missing key named).
- The QA `tiny` image keeps the final's transparency instead of flattening it onto black, so
  the small-size check sees the same mark as the full render.
- `scripts/skill_check.py` reports unreadable files and unusable link targets (including a
  decoded NUL byte) instead of raising, and accepts `<...>` and percent-encoded links;
  `scripts/install.py` names a damaged or unreadable host config instead of a traceback;
  `scripts/gen_docs.py` rejects unknown flags instead of writing.
- An interrupted font download no longer poisons the font cache: downloads and cache writes go
  through a temp file, a damaged family index or catalog cache is fetched again, and a cached
  file that is not a font is removed with a named error.
- A malformed font spec in `brief.toml` or `proposals.toml` is rejected before it is picked and
  saved to `ideation/fonts.json`; a picked font that cannot be resolved names the files to fix.
  `run.json` records one font asset per spec, so two weights of one family are both listed.
- Motif authoring rejects non-finite path numbers, stroke widths that are not above zero, and
  non-finite or non-positive `glyphs` sizes and positions; `plotter_lines` and
  `fontforge_glyphs` name the bad width or operation instead of raising bare errors.
- `logo-maker doctor` checks that the download cache (`LOGO_MAKER_CACHE`) is usable;
  `benchmark verify` rejects malformed cases and unreadable manifests with named errors;
  `run.json` seeds, stage statuses and jev telemetry are validated on load; and palette hex
  values accept one leading `#` and ASCII hex digits only.

## [0.1.0] - 2026-11-10

### Added

- `logo-maker` CLI with resumable stages: `new`, `intake`, `ideate`, `motifs`, `preview`, `finalize`,
  `export`, `run`, `improve`, `doctor`, and `mcp`.
- Concept model: a 2D motif (glyphs, authored paths, or a traced reference) plus a 3D treatment
  composed from shared components, with a catalog of 12 treatments, 19 materials, and lighting
  rigs. Motif layers carry palette roles; starter scenes give each role its own material and
  component, and `[mark] scale` sizes
  the mark inside plates, rims, and ring text.
- Jev judgments for intake, a three-stage concept chain to a shortlist of 8, image screening of previews
  (kept when P(at least Pleasant) >= 0.5), a five-check QA loop where a clear Jev fail (P < 0.3)
  — or a code-detected veil, cut-off, or aliasing — triggers that check's scene fix, and a final
  head-to-head asked in both orders; every request logged with images stored once by sha256.
- Blender Cycles rendering on the Metal GPU with OIDN and Poly Haven studio lighting, plus
  Mitsuba 3 and three.js renderers. LuxCoreRender is wired up but reported unavailable on macOS
  arm64, where its OpenMP runtime deadlocks.
- Export set: transparent hero, hero on paper, circle-safe avatar, favicons and .ico, color and
  mono SVG,
  PWA icons and splash screens, Draco-compressed glTF, .blend, and a contact sheet.
- Agent skill, MCP server, and plugin manifests for Claude Code, Codex, and omp.
