# logo-maker

Turn an idea, a reference image, a repository, or a brainstorm into a rendered 3D logo and a complete
export set. An agent writes the brief, metaphors, and each concept's motif;
logo-maker builds up to 1000
concepts, judges them with [Jev](https://docs.typesafe.ai), renders the best on the GPU with Blender Cycles,
runs a QA loop, and exports everything a brand needs. No AI image generation: every pixel comes from
geometry, fonts, materials, and light.

## Install

Requires macOS on Apple silicon (Metal GPU), [uv](https://docs.astral.sh/uv/), Node 24, and Homebrew.

```sh
just setup                                  # go, fontforge, primitive, Python env, npm, Metal kernels
uv run python scripts/install.py --agent claude   # or codex | omp | skills --destination DIR
logo-maker doctor
export OPENROUTER_API_KEY=...               # Jev via OpenRouter (or TYPESAFE_API_KEY)
```

## Use

```sh
logo-maker new acme --name "Acme"   # writes logos/acme/brief.toml and templates
logo-maker brief acme               # review supplied evidence and freeze requirements
logo-maker run acme                 # runs every stage; stops where the agent must author files
logo-maker improve acme             # new round; replaces the logo only if it wins head-to-head
```

Fill `brief.toml` and `brief-evidence.toml` from project/owner sources before review. Keep business
facts, mandates and assumptions separate. Each shortlisted concept gets a `plan.toml` for its visual
hypothesis and purposeful detail; `logo-maker plan acme` reviews intent before preview rendering.
Actual pixels still require independent craft, fit and technical passes.

Stages: `brief`, `intake`, `ideate`, `plan`, `motifs`, `refine`, `status`, `preview`, `finalize`,
`export` (each resumable), `run`, `improve`, `doctor`,
`mcp`. The skill in [skills/logo-maker/SKILL.md](skills/logo-maker/SKILL.md) walks an agent through the
authoring steps.

## Exports

`exports/`: transparent hero (2000 px), hero on paper, 1024 px circle-safe avatar, favicons
16/32/48/180/512 + `.ico`, color and mono SVG, PWA icons (no splash screens), Draco-compressed `.glb`,
`.blend`, and a contact sheet.

## Docs

- [Architecture and contracts](docs/architecture.md)
- [Adapters (every tool and its license)](docs/adapters.md)
- [Rendering, pixel QA, export set, tool notes](docs/render-export.md)
- [Jev questions and truth tables](docs/jev-questions.md)
- [ADR 0001: motif + treatment model](docs/adr/0001-motif-plus-treatment.md)

## License

MIT. Some dependencies carry other licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
