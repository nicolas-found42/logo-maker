# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
