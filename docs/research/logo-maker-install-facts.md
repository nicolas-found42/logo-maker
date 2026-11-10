# logo-maker — verified install facts (2026-11-10)

Target machine: macOS 27.0.1 arm64 (Apple M5 Pro), Homebrew `/opt/homebrew`.
All tests run under `/tmp/lm-facts/` (`uv venv -p 3.13 /tmp/lm-facts/venv313`, CPython 3.13.16 brew; `bun install` in `/tmp/lm-facts/js-node`). No existing repos modified; no secrets printed.

## Toolchain (verified)

| Tool | Version | Source |
|---|---|---|
| Python | 3.13.16 (brew `python3.13`); system `python3` is 3.15.0 — pin `uv venv -p 3.13` | `uv python list`, `python3 --version` |
| uv | 0.13.6 | `uv --version` |
| Node | v24.22.2 | `node --version` |
| npm | 11.19.1 | `npm --version` |
| Bun | 1.4.3 (`bunx --version` works identically) | `bun --version` |
| Go | **not installed** — `brew info go` = 1.27.3 bottled, BSD-3-Clause | `brew info go` |
| Google Chrome | present at `/Applications/Google Chrome.app` → `playwright-core` `channel: "chrome"` works | `ls /Applications/` |
| claude CLI | present (`~/.local/bin/claude`, `claude plugin --help` OK) | `which claude` |
| codex CLI | present (`/opt/homebrew/bin/codex`, `codex plugin --help` OK) | `which codex` |
| omp | v18.18.6, supports `omp plugin …` incl. `marketplace` action | `omp --help`, `omp plugin --help` |

**JS runtime preference (evidence):** `skeleton-maker` pins Playwright via **npm** (`package-lock.json`, `devDependencies.playwright 1.63.0`, CONTRIBUTING: "Node/npm and ffmpeg available"). `deckgen` has **no `package.json`** (Rust + Python only). `~/.omp/plugins/` itself is npm+bun: `package.json` + `bun.lock` with `pi-warden` installed at `~/.omp/plugins/node_modules/` (npm-style). → **Recommended: npm/Node for the Node side (matches skeleton-maker); bun acceptable except `trianglify` (below).**

## Python (Python 3.13, macOS arm64)

Venv totals: 110M after pure wheels (0.8s), 423M after binary wheels (1.5s), 884M after vpype+build123d (1.8s), **1.2G final** after mitsuba+pyluxcore (3.5s) + sdf (2.1s). All times are wheel-cache-warm `uv pip install`; cold installs dominated by download.

| Package | Route | Version | cp313 macOS arm64 wheel? | License | Smoke (`import`) |
|---|---|---|---|---|---|
| bpy | `uv pip install bpy==5.2.3` | 5.2.3 | **yes** — `bpy-5.2.3-cp313-cp313-macosx_11_0_arm64.whl` (PyPI JSON `files` list) | GPL-3.0 | OK — pre-installed at `/tmp/logo3d/venv-bpy`, `bpy.app.version_string` = `5.2.3 LTS`, 764MB total; not re-downloaded |
| fonttools | PyPI | 4.68.0 | yes (`-cp313-…-macosx_10_13_universal2.whl`) | MIT | `fontTools` OK |
| skia-pathops | PyPI | 0.9.2 | yes via **abi3**: `cp310-abi3-macosx_10_9_universal2.whl` (forward-compatible with cp313, verified by install) | BSD-3 | **import name is `pathops`, not `skia_pathops`** — OK |
| drawsvg | PyPI | 2.4.2 | yes (`py3-none-any`) | MIT (classifier; license field blank) | OK |
| resvg-py | PyPI | 0.5.0 | yes via abi3: `cp310-abi3-macosx_11_0_arm64.whl` | MPL-2.0 (upstream resvg; PyPI metadata blank) | `resvg_py` OK |
| pillow | PyPI | 13.0.0 | yes (`-cp313-…-macosx_11_0_arm64.whl`) | MIT-CMU (`license_expression`) | `PIL` OK |
| vtracer | PyPI | 0.6.15 | yes (`-cp313-…-macosx_11_0_arm64.whl`) | MIT (`license_expression`) | OK |
| sdf (fogleman/sdf) | git | 0.1 | n/a (pure Python; deps numpy/scikit-image/meshio all have cp313 arm64 wheels — numpy 2.5.4, scikit-image 0.26.0, meshio 5.3.5 py3) | MIT | OK; `uv pip install "sdf @ git+https://github.com/fogleman/sdf"` (pulled matplotlib, scipy, Pillow deps from `setup.py`) — repo pushed 2026-09-30 (GitHub API) |
| manifold3d | PyPI | 3.5.4 | yes (`-cp313-…-macosx_11_0_arm64.whl` + universal2) | Apache-2.0 (classifier) | OK |
| trimesh | PyPI | 5.2.0 | yes (`py3-none-any`) | MIT | OK |
| pymeshlab | PyPI | 2025.7.post1 | yes (`-cp313-…-macosx_11_0_arm64.whl`) | GPL3 | OK |
| mitsuba | PyPI | 3.9.1 | yes (`-cp313-…-macosx_11_0_arm64.whl`) | BSD (classifier) | OK (prints nvrtc warning on import, harmless) |
| pyluxcore | PyPI | 2.11.2 | yes (`-cp313-…-macosx_14_0_arm64.whl`) | Apache-2.0 (classifier) | OK |
| OpenImageIO | PyPI (name `OpenImageIO`) | 3.2.2.0 | yes (`-cp313-…-macosx_11_0_arm64.whl`) | Apache-2.0 | OK |
| coloraide | PyPI | 8.14.1 | yes (`py3-none-any`) | MIT | OK |
| vpype | PyPI | 1.15.0 | yes (`py3-none-any`) | MIT | OK |
| build123d | PyPI (+ cadquery-ocp) | build123d 0.13.0 + cadquery-ocp 8.0.1.1.0 | yes (`py3-none-any` wrapper; **`cadquery-ocp` ships `-cp313-…-macosx_11_0_arm64.whl`**, so 3.13 works — the "needs 3.12" concern is outdated) | Apache-2.0 (both) | OK (0.13.0) |
| httpx | PyPI | 0.28.1 | yes (`py3-none-any`) | BSD-3 | OK |
| pytest | PyPI | 9.2.0 | yes (`py3-none-any`) | MIT (`license_expression`) | OK |
| ruff | PyPI | 0.17.4 | yes (`py3-none-macosx_11_0_arm64.whl`) | MIT (`license_expression`) | `ruff --version` 0.17.4 OK |
| ty | PyPI | 0.0.100 | yes (`py3-none-macosx_11_0_arm64.whl`) | MIT (classifier) | `ty --version` OK |

**FontForge (python bindings): NOT installed via brew** (`brew info fontforge`: stable 20251009 bottled, GPL-3.0-or-later, "only installs the command line utilities", 17 deps incl. `python@3.15`). From the formula (`https://raw.githubusercontent.com/Homebrew/homebrew-core/HEAD/Formula/f/fontforge.rb`): the `import fontforge` module is installed into brew `python@3.15`'s site-packages (`-DPYHOOK_INSTALL_DIR=#{Language::Python.site_packages(python3)}`, smoke-tested in the formula with `system python3 -c "import fontforge; fontforge.font()"`). A uv 3.13 venv **cannot** import that C extension (ABI mismatch 3.15 vs 3.13). Routes for the repo: (a) subprocess `fontforge -script <script.py>` with the **brew** `fontforge` CLI — recommended, no ABI coupling; (b) run a brew-python3.15 subprocess with `PYTHONPATH` to the brew site-packages. Not smoke-tested (would require `brew install fontforge`, system-wide — skipped per scratch-install constraint).

**pybullet: BLOCKER.** PyPI 3.2.7 ships only `manylinux` x86_64 wheels + sdist — **no macOS wheels at all** (checked full `files` list via `https://pypi.org/pypi/pybullet/json`). On macOS arm64 it would need a from-source Bullet C++ build — not trivially available. License zlib. Not installed.

## Node / other (node v24.22.2, npm 11.19.1, bun 1.4.3)

`bun install` of all 16 non-native packages: 272 packages, 1.1s, 188MB `node_modules`. Import smoke under **bun**: all OK **except `trianglify`**. Versions/licenses via `npm view <pkg> version license`.

| Package | Version | License | Smoke |
|---|---|---|---|
| three | 0.187.0 | MIT | OK |
| postprocessing (pmndrs) | 6.39.6 | Zlib | OK |
| n8ao | 2.0.1 | ISC | OK |
| playwright-core | 1.65.0 | Apache-2.0 | OK; `channel: "chrome"` usable — Chrome present (see toolchain) |
| perfect-freehand | 1.2.3 | MIT | OK |
| roughjs | 4.6.6 | MIT | OK |
| svg2roughjs | 3.2.3 | MIT | OK |
| d3-delaunay | 6.0.6 | ISC | OK |
| trianglify | 4.1.1 | GPL-3.0 | **FAILS under bun**: `The module 'canvas' was compiled against a different Node.js ABI version (NODE_MODULE_VERSION 137)` — prebuilt `canvas` targets Node 24. **OK under node** (`import('trianglify')` verified with `node --input-type=module`). → use npm/Node for this one (or isolate in an npm-only step) |
| heerich | 0.21.0 | MIT | OK |
| culori | 4.0.2 | MIT | OK |
| @adobe/leonardo-contrast-colors | 1.1.0 | Apache-2.0 | OK |
| svgo | 4.1.0 | MIT | OK (`svgo --version` 4.1.0) |
| favicons | 7.3.1 | MIT | OK (pulls `sharp`/libvips; one harmless macOS duplicate-class warning) |
| pwa-asset-generator | 8.1.7 | MIT | OK |
| @gltf-transform/cli | 4.5.1 | MIT | OK (`gltf-transform --version` 4.5.1) |
| draco3dgltf | 1.5.9 | Apache-2.0 | OK |

## Go

`func fogleman/primitive`: `go install github.com/fogleman/primitive@latest`. **Go is not installed**; route: `brew install go` (1.27.3, BSD-3-Clause). Not installed per scratch-install constraint — `go install` itself untested.

## Blockers (explicit)

1. **pybullet — no macOS wheels (any arch/any CPython), only manylinux + sdist.** Would require building Bullet C++ from source. Drop or vendor.
2. **trianglify native canvas breaks under bun** (Node-ABI prebuild). Works under npm/Node 24. If the repo standardizes on bun, quarantine trianglify to an npm-installed step or replace it.
3. **fontforge `import fontforge` is bound to brew python@3.15**, not importable from a 3.13 uv venv. Use `fontforge -script` subprocess (recommended) and accept "brew install fontforge" as a host prerequisite.
4. **Go not installed** — `brew install go` is a host prerequisite; `go install github.com/fogleman/primitive@latest` is then one command.
5. **bpy mismatch of venvs**: `bpy 5.2.3` wheel exists for cp313 but the existing 764MB `/tmp/logo3d/venv-bpy` has **no pip** (uv-managed venv). Fine for `uv pip install` flows, but don't `pip install` into it.

## Plugin packaging: one repo → omp + Claude Code + Codex

**deckgen layout (cited files, `/Users/nicolas/Documents/github/deckgen/`):**
- `.claude-plugin/plugin.json` — Claude-native plugin manifest (`name: deckgen`, `version: 1.0.0`).
- `.claude-plugin/marketplace.json` — Claude marketplace (`name: deckgen-plugins`, plugin `source: "."`).
- `.agents/plugins/marketplace.json` — Codex marketplace (`source: {source: local, path: "."}`, `policy.installation: AVAILABLE`, `interface.displayName`).
- `plugin.json` at repo **root** — cross-host manifest (`$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) — the `.claude-plugin/plugin.json` content differs (root copy has the `$schema` field; `.claude-plugin/` copy does not). Both exist; keep both in sync.
- `skills/deckgen/SKILL.md` (+ `scripts/`, `references/`, `assets/`, `agents/`), `commands/deckgen.md` (Claude slash command), `scripts/install.py` — the host installer: `codex plugin marketplace add <root>` + `codex plugin add deckgen@deckgen-plugins`; `claude plugin marketplace add <root>` + `claude plugin install deckgen@deckgen-plugins`; **omp → symlink `skills/deckgen` into `~/.omp/agent/skills/`** (per-session discovery). The Rust renderer is deliberately **not** built at install time — the skill builds on first use (`cargo build` + Python venv for PyMuPDF).

**omp (cited):** omp v18.18.6 has `omp plugin` with `install|uninstall|list|link|doctor|features|config|enable|disable|marketplace|discover|upgrade` (`omp plugin --help`), plus `--plugin-dir <path>` ("Load plugin from directory") in `omp --help`. **omp does NOT load Claude-format plugins or marketplaces** — its plugin system is npm-based: `omp plugin list --json` shows installed plugins as npm packages with a manifest of `extensions: ["./extensions/index.js"]` (live example: `pi-warden@2.5.0` at `~/.omp/plugins/node_modules/pi-warden`, whose `package.json` has `"bin"`, `"engines": {node: >=22.19.0}`, `"keywords": ["pi-package","pi-extension"]`). `omp plugin marketplace list` → "No marketplaces configured". deckgen's own omp route is **skill symlinking** (`~/.omp/agent/skills/<name>`, which this machine already shows: `deckgen`, `deckgen-loop`, … — confirming per-session skill discovery works). → For logo-maker: ship `skills/logo-maker/SKILL.md` + a `scripts/install.py` mirroring deckgen's (`--agent omp` symlink/copy mode), OR additionally ship an npm plugin dir with a `pi-package`-style `package.json` if programmatic omp behavior (extensions) is wanted.

**Codex (cited):** `codex plugin marketplace add <root>` is the CLI path (deckgen `scripts/install.py`: `["codex","plugin","marketplace","add",root]` + `["codex","plugin","add","deckgen@deckgen-plugins"]`). Marketplace discovery: `https://github.com/shanraisshan/codex-cli-best-practice/blob/main/best-practice/codex-marketplace.md` — Codex looks for `marketplace.json` at **`.agents/plugins/marketplace.json` (Codex-native)** or **`.claude-plugin/…`** — so one file covers both; deckgen chose `.agents/plugins/marketplace.json`. Plugin manifest for Codex is **`.codex-plugin/plugin.json`** per `https://github.com/openai/plugins` ("Each plugin lives under `plugins/<name>/` with a required `.codex-plugin/plugin.json` manifest and optional companion surfaces such as `skills/`, `.app.json`, `.mcp.json`, plugin-level `agents/`, `commands/`, `hooks.json`, `assets/`"). deckgen itself has **no `.codex-plugin/` dir** — it relies on the `.agents/plugins/marketplace.json` + root `plugin.json` (agent-plugins.org schema) pair. → Logo-maker recommendation: mirror deckgen exactly (`.claude-plugin/{plugin,marketplace}.json` + `.agents/plugins/marketplace.json` + root `plugin.json`), and consider adding `.codex-plugin/plugin.json` for openai/plugins-style distribution.

**Can the plugin register the CLI?** Not directly in any of the three manifests: plugin manifests (Claude/Codex/omp-npm) expose **skills, slash commands (`commands/`), hooks, MCP servers (`.mcp.json`), agents, and npm `bin`/extensions** — no PATH-installed CLI. deckgen's answer: `scripts/install.py` per-host install step + the skill builds the binary on first use (deckgen's renderer is `cargo build` + venv created by the skill, per its install.py docstring). Logo-maker equivalent: `uv sync`/`uv tool install` (or `cargo build`) inside the skill's first run, with `scripts/install.py --agent {omp|claude|codex|skills}` doing the symlink/marketplace-add wiring; document `logo-maker` CLI invocation as a skill step rather than a manifest field.

## Sources

PyPI JSON: `https://pypi.org/pypi/<pkg>/json` (files list + `license_expression`/classifiers) for bpy, fonttools, skia-pathops, drawsvg, resvg-py, pillow, vtracer, manifold3d, trimesh, pymeshlab, mitsuba, pyluxcore, OpenImageIO, coloraide, vpype, build123d, cadquery-ocp, httpx, pytest, ruff, ty, pybullet, numpy, scikit-image, meshio; `https://pypi.org/pypi/fontforge/json` → 404 (no such package). npm: `npm view <pkg> version license` (all 17). fogleman/sdf: `setup.py` + repo metadata via raw.githubusercontent.com / api.github.com. brew: `brew info fontforge|go` + formula `https://raw.githubusercontent.com/Homebrew/homebrew-core/HEAD/Formula/f/fontforge.rb`. omp: `omp --help`, `omp plugin --help`, `omp plugin list --json`, `~/.omp/plugins/{package.json,node_modules/pi-warden/package.json}`. deckgen: files listed above under `/Users/nicolas/Documents/github/deckgen/`. Codex plugin format: github.com/openai/plugins + best-practice marketplace doc; `codex plugin --help`. Entrypoint scripts: `/tmp/lm-facts/venv313/bin/{ruff,ty}`, `/tmp/lm-facts/js-node/node_modules/.bin/{svgo,gltf-transform}`.
