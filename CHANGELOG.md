# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
