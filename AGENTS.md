# Agent instructions

logo-maker is a Python 3.13 (uv) CLI, agent skill, and MCP server that turns a brief into a judged,
rendered 3D logo and export set. Contracts between stages (logo folder, motif, scene, render, jev,
adapters) live in [docs/architecture.md](docs/architecture.md); change the contract there first.

## Ground rules

- Every image comes from geometry, fonts, materials, and renderers. Models only judge (Jev); code decides.
- Jev question wording, options, and thresholds live only in `logo_maker/jev/questions.py`; regenerate
  `docs/jev-questions.md` from `questions.describe()` after changing them.
- Catalog entries (treatments, materials, lighting) and every default stay brand-neutral: each logo's look
  comes from its own brief. `examples/` is a regression fixture, never a design reference for the skill.
- New external tools get an `Adapter` (stage, SPDX license, check, fix) in `logo_maker/adapters/` and a
  line in [docs/adapters.md](docs/adapters.md); GPL tools also go in THIRD_PARTY_NOTICES.md.
- GPU renders: a first Metal kernel compile takes 1.5-5 min with no output. Let a render run up to its
  900 s timeout; interrupting it discards the compile.

## Verification

- `just test`: offline tests (no GPU, no jev). `just render-example`: the regression render (SSIM >= 0.90
  against `examples/`). `just lint` and `just type` before committing.
- `logo-maker doctor` must be all `ok` after any dependency change.
- Live jev tests are marked `live` and run only with `-m live` and an API key.
