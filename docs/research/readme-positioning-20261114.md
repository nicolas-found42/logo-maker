# README positioning research (2026-11-14)

Scope: primary-source facts for a screenshot-led root README. Every factual claim cites a
repository file with line numbers (`file:lines`) or a URL. No claim below should be lifted
into the README without its qualifier. Visual selection is out of scope here.

## 1. One-sentence positioning (substantiated)

- logo-maker is "a Python 3.13 (uv) CLI, agent skill, and MCP server that turns a brief
  into a judged, rendered 3D logo and export set" (`AGENTS.md:3-5`). The same sentence
  appears in the package description (`pyproject.toml:8`) and plugin manifests
  (`plugin.json:5`, `.claude-plugin/plugin.json:4`, `.codex-plugin/plugin.json:4`).
- The differentiator that is safe to state: "No stage generates images with an AI model.
  Every pixel comes from geometry, fonts, materials, and renderers" (`docs/architecture.md:18-19`,
  `AGENTS.md:9`, `pyproject.toml:8`). Jev only judges: "Jev (TypeSafe's System One model)
  answers typed questions about text and images. It never decides; code turns its answers
  into actions through truth tables" (`docs/architecture.md:12-14`).
- Suggested headline shape (fact-checked against the above):
  "Turn a brief into a rendered 3D logo and a complete brand export set — every pixel from
  geometry, fonts, materials and light, no AI-generated images."
- The "up to 1000 concepts" figure is the size of the text-combination pool the judged
  pipeline screens down (`logo_maker/mcp_server.py:163-167`); do not present it as 1000
  rendered logos. The shortlist it produces is 8 (`docs/architecture.md:26`).

## 2. Platform and hardware matrix

| Capability | Platform | Source |
|---|---|---|
| Full 3D rendering (Blender Cycles on Metal GPU) | macOS on Apple silicon only, verified | `README.md:12`, `docs/architecture.md:59`, `skills/logo-maker/references/setup.md:66`, `docs/adapters.md:61` |
| Python | `>=3.13,<3.14` exactly (bpy ships cp313 wheels only) | `pyproject.toml:10-11` |
| Node | 24+ | `skills/logo-maker/references/setup.md:66`, `logo_maker/doctor.py:91` |
| uv dependency resolution | `sys_platform == 'darwin' and platform_machine == 'arm64'` plus `linux` (CI/offline only; render tests run locally) | `pyproject.toml:64-66`, `.github/workflows/ci.yml:3,56` |
| Flat logos/favicons/avatars | No GPU, no Jev key; minimal Python env skips the 3D deps | `skills/logo-maker/references/setup.md:42-43,54-64`, `skills/logo-maker/references/flat-assets.md:18-20` |
| 3D studies (compare named designs, package a ZIP) | Works without Jev credentials or production qualification | `docs/architecture.md:59-63`, `skills/logo-maker/references/studies.md:3-6` |

Do not claim Windows or Intel Mac support for rendering. Do not claim Linux rendering:
the `linux` environment entry exists for CI, and CI runs only offline checks — "no GPU,
no jev key. The render tests run locally" (`.github/workflows/ci.yml:3`).

## 3. Installation (verified commands)

From a checkout (there is no PyPI release to `pip install`; the PyPI JSON endpoint for
`logo-maker` returned 404 on 2026-11-14 — https://pypi.org/pypi/logo-maker/json):

```sh
just setup                                  # go, fontforge, primitive, Python env, npm, Metal kernels
logo-maker doctor
```

- Prerequisites: macOS on Apple silicon (Metal GPU), uv, Node 24, Homebrew (`README.md:12`);
  `just setup` runs `scripts/setup.py` (`justfile:9-11`).
- First Metal kernel compile takes 1.5–5 min with no output; renders allow up to 900 s
  (`AGENTS.md:17-18`, `skills/logo-maker/references/setup.md:74-75`, `scripts/install.py:44-45`).
- `logo-maker doctor` is the health check: it verifies the Jev key, Node, Metal GPU,
  kernel cache, download cache and every adapter (`scripts/install.py:14`,
  `logo_maker/doctor.py:89-99`, `docs/adapters.md:3-4`). A missing Jev key is a failed
  check row with a fix (`logo_maker/doctor.py:51-54`) — but 3D studies proceed without it
  (`skills/logo-maker/references/setup.md:76-80`).
- Chrome is required for the PWA icon generator and the three.js renderer
  (`docs/adapters.md:71,84`).

## 4. First success paths (recommended order for the README)

### A. Flat assets — fastest first success, no Apple GPU needed

Python-only recipe: author `motif.py` (or supply `motif.svg`), run the motif script,
validate, write a size sheet and rasterize favicons at 16/32/48/180/512 plus
`favicon.ico` (`skills/logo-maker/references/flat-assets.md:42-76`). Use this as the
"works on any machine" path; it carries no GPU/Jev requirement (`setup.md:42-43`).

### B. 3D study — the screenshot-led demo path (Apple silicon)

```sh
logo-maker new acme --name "Acme"
logo-maker study acme --concept first --concept second --preview
logo-maker study acme --concept first --concept second
logo-maker review-study acme <study-id>
```

(`README.md:25-30`.) A study packages "each selected transparent hero, editable `.blend`,
full and compact flat assets, favicons, survey views, and available reference evidence"
(`skills/logo-maker/references/studies.md:78-81`). Review needs Jev and reference photos
(`skills/logo-maker/references/studies.md:97-106`); without them delivery still works and
review stays pending (`skills/logo-maker/references/studies.md:103-104`).

### C. Judged production pipeline — the full claim

`brief → intake → ideate → plan → motifs → refine → preview → finalize → export`, each
stage resumable, with `run` chaining them and stopping where the agent must author files
(`docs/architecture.md:21-34,53-55`, `logo_maker/cli.py:16-32`). Requires
`OPENROUTER_API_KEY` or `TYPESAFE_API_KEY` (`docs/architecture.md:12`,
`docs/adapters.md:10`, `skills/logo-maker/references/setup.md:76-77`). The skill at
`skills/logo-maker/SKILL.md` walks an agent through the authoring steps (`README.md:60-63`).

### D. Codex branding campaign — modeled production

Runs in a project-local pinned Codex runtime on Apple silicon, retains approval/budget/
render/review state across sessions, and requires a preflight pass (Seatbelt, Cycles
Metal, GPU OIDN) before modeled work (`docs/campaigns.md:36-40`,
`skills/logo-maker/references/setup.md:5-25`). Modeled review needs 40 distinct
photographs per selected design (`docs/campaigns.md:17-26`).

## 5. Agent / MCP / plugin entry points

- Installer: `uv run --locked python scripts/install.py --agent claude|codex|omp|skills
  [--destination DIR]` (`README.md:16,41-45`). Host behavior: Claude links the skill and
  registers a user-scope MCP server; Codex uses the plugin CLI plus a
  `[mcp_servers.logo-maker]` entry; omp links the skill and registers the MCP server in
  `~/.omp/agent/mcp.json` (`scripts/install.py:4-13`). Every host also gets the
  `logo-maker` command via `uv tool install --editable` (`scripts/install.py:13,99-103`).
- MCP server: `logo-maker mcp`, and root `.mcp.json` runs it as
  `uv run --quiet --project <checkout> logo-maker mcp` (`.mcp.json:2-14`,
  `scripts/install.py:11-12`). Tools: `logo_new`, `logo_doctor`, `logo_status`,
  `logo_brief`, `logo_intake`, `logo_ideate`, `logo_plan`, `logo_motifs`, `logo_refine`,
  `logo_preview`, `logo_finalize`, `logo_export`, `logo_study`, `logo_review_study`,
  `logo_campaign`, `logo_run`, `logo_improve` (`logo_maker/mcp_server.py:126-315`).
  `logo_doctor` mirrors the CLI doctor rows plus passed/failed counts
  (`CHANGELOG.md:25-28`).
- Plugin manifests exist at the root (`plugin.json`), `.claude-plugin/` (with a
  marketplace listing it as `source: "."`, `.claude-plugin/marketplace.json:7-12`) and
  `.codex-plugin/` (which ships the skill only, `CHANGELOG.md:19-24`).

## 6. Output / export capabilities (exact)

`export_all` writes exactly (`docs/render-export.md:73-91`):

- `hero-transparent.png` (2000², veil/margin-checked, else `ExportError`),
  `hero-paper.png` (paper bg + soft shadow), `avatar-1024.png` (88% inscribed-circle fit),
  `favicon-16/32/48/180/512.png`, `favicon.ico`, `mark-color.svg` + `mark-mono.svg`
  (SVGO-optimized), `pwa/` icons only (no splash screens), `manifest.webmanifest` +
  `browserconfig.xml` + android/mstile sets, `model.glb` (Draco-compressed, when present),
  `scene.blend` (when present), `contact-sheet.png`, and `exports/manifest.json`
  (sizes + sha256).

Campaign shareable packages add construction inputs, comparison sheets and usage guidance;
private research/photos/raw Jev payloads stay in a separate archive (`docs/campaigns.md:65-72`).

## 7. Caveats and do-not-claim list

- **No "one command to a finished logo."** The pipeline stops for agent authoring
  (`AUTHORING NEEDED`, CLI exit 3 / MCP `authoring_needed`) and the agent writes briefs,
  metaphors, motifs and scenes (`docs/architecture.md:10-16`, `skills/logo-maker/SKILL.md:10-14`).
- **No AI image generation** — safe and central (`docs/architecture.md:18-19`). Say "no AI
  image generation," not "no AI" (Jev judges).
- **Not production-qualified by default.** Campaign trials to date are review handoffs:
  "The campaign maintains the production gate while evidence is outstanding"
  (`docs/research/codex-branding-campaign-validation-20261113.md:55-63`); Field Kettle
  production export remains open (`docs/research/beginner-workflow-validation-20261113.md:40-50`).
- **Specific tool limits** (only if the README goes deep): Cycles glare needs a compositor
  tree headless pip `bpy` lacks (`docs/render-export.md:95-96`); `primitive` is
  nondeterministic (`docs/render-export.md:105-106`); HDRI downloads need network, with
  `hdri = "none"` as the offline fallback (`docs/adapters.md:54-55`).
- **License of logo-maker itself:** MIT (`LICENSE:1-3`, `pyproject.toml:12`); third-party
  components keep their own licenses, including GPL-3.0 entries (bpy, PyMeshLab, FontForge,
  trianglify) and the proprietary Jev API (`THIRD_PARTY_NOTICES.md:3-20`). Exports belong
  to the brief's owner (`THIRD_PARTY_NOTICES.md:22-23`).
- Version is `0.1.0` (`pyproject.toml:7`, `plugin.json:4`); changelog head is
  `[Unreleased]` (`CHANGELOG.md:7`). Do not imply a stable release.

## 8. Screenshot / output provenance (for the README)

- `logos/` is **gitignored per-user work, not source** (`.gitignore:1-2`). Existing
  renders — e.g. `logos/logo-maker/exports/hero-transparent.png`,
  `logos/logo-maker/exports/contact-sheet.png`,
  `logos/chief-of-staff/exports/hero-transparent.png`, and the Found42/Field Kettle study
  heroes under `logos/*/studies/` — are real tool outputs but are **not tracked**, so a
  GitHub README cannot hotlink them. They must be copied into a tracked assets directory
  (e.g. `docs/assets/`) before use; the main agent judges the visuals.
- The only tracked image is `examples/chief-of-staff/reference-256.png`
  (`git ls-files examples/`), a regression-fixture reference (256 px) for the bundled
  Chief of Staff brief (`examples/chief-of-staff/brief.toml:1-8`; fixtures are "never a
  design reference", `AGENTS.md:12-14`). Do not present it as a rendered result.
- Recommended provenance for a README hero shot: a fresh `logo-maker study` run (path B
  above) on the reporter's machine, exported to a tracked folder, with the study ID and
  manifest retained. Study manifests bind delivered files to their bytes
  (`docs/architecture.md:86-91`), so the image can be traced to its run.

## 9. Method and limits

- Behavioral discovery started with `jg` rooted at
  `/Users/nicolas/Documents/github/logo-maker` (bounded `--max-requests`); Jevgrep
  returned incomplete, locations-only results, so every claim above was verified by direct
  reads of the cited files.
- Web use: one Keenable fetch of the PyPI JSON endpoint (404, i.e. no PyPI release).
  No upstream docs were needed beyond the repo's own first-party docs.
- No builds, tests, linters or formatters were run; no product files were modified.
  Existing-note convention followed: kebab-case name under `docs/research/`, following
  the index in `docs/research/README.md:6-29`.

## 10. Strongest substantiated claims for the README

1. "Every pixel from geometry, fonts, materials and light — no AI-generated images; the
   model only judges." (`docs/architecture.md:12-19`)
2. "From a brief to a full export set: transparent hero, color/mono SVG, favicons,
   avatar, PWA icons, Draco `.glb`, editable `.blend`, contact sheet — with a sha256
   manifest." (`docs/render-export.md:73-91`)
3. "Works as a CLI, an agent skill, and an MCP server (Claude, Codex, omp)." (`AGENTS.md:3`,
   `scripts/install.py:4-13`, `logo_maker/mcp_server.py:126-315`)
4. "Flat favicons and marks need no GPU; the 3D pipeline runs on Apple silicon Metal."
   (`skills/logo-maker/references/setup.md:42-43,66`, `docs/adapters.md:61`)
5. "`logo-maker doctor` checks every tool, the GPU and your API key before you start."
   (`logo_maker/doctor.py:89-99`)

## 11. README image selection and provenance

The README uses existing logo-maker renders, not generated marketing mockups. The new
`docs/assets/readme/showcase.png` joins three complete images side by side, resized to 480 px
each. Transparent pixels in the mug preview are composited over a neutral background; the
geometry and artwork are unchanged. Sources, left to right:

- `logos/logo-maker/exports/hero-paper.png` — the tool's geometric identity.
- `logos/found42-realism/iterations/M/08-notebook/handoff/hero-paper.png` — Found42 notebook.
- `logos/field-kettle/walkthrough/fillet-terrain-mug-smooth/preview.png` — Field Kettle mug.

`docs/assets/readme/seedwell-contact-sheet.png` is a losslessly re-encoded copy of
`logos/campaign-release-development/seedwell/studies/study-d243ae3556f1/sill-basin/contact-sheet.png`.
It shows the delivered study's hero, flat mark, monochrome mark, and compact icon. These local
source paths establish provenance, not production qualification.

Selection used a frozen Jev rubric before viewing candidates. The deterministic prefilter
excluded 699,184 non-image files, 745 cache/dependency/evidence images, and 2,692 small icons.
Of the remaining 21,956 images, filename and newest-per-project rules removed 21,424
intermediates and 508 older duplicates, leaving 24 representative candidates.
Jev classified 13 as hero candidates, 10 as workflow candidates, and 1 as other. No errors or
truncations occurred. All 23 hero/workflow flags were visually inspected together; their
categories were confirmed as renders or contact/comparison sheets. The four selected source
images were additionally opened individually before preparing the README assets. No confidently
excluded image was inspected.

The documented first-run commands were exercised in a temporary folder: `new` created the brief,
and `study --concept cairn --concept trail --preview` returned the expected authoring stop
(exit 3), naming the missing concept descriptions and motifs. No GPU render or provider review
was claimed by that check. The temporary folder was removed afterward.
