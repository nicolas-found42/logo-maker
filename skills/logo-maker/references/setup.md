# Tool setup

## Codex project installation

Use `uv run --locked python scripts/install.py --agent codex --destination /absolute/project`
from the tool checkout to install into a fresh Codex project. For modeled campaigns, add
`--metal-runtime /absolute/path/to/verified/patched/codex`. The installer checks the pinned
binary digest and stages the runtime inside the project. Start Codex in that project
so it loads `.agents/skills/logo-maker` and the MCP registration in `.codex/config.toml`.
These files come from one tool snapshot. Verify the server with `logo_doctor`. If using
the CLI in that project, run `uv run --locked --project "$PWD/.codex/logo-maker" logo-maker`
with the stage arguments. This selects the installed tool even if an older executable is
on PATH. Blender authoring can use that snapshot's Python environment and bundled `bpy`.
Use `--upgrade` with the same project destination to stage a new tool and skill. The installer
retains the prior snapshot and restores it if the new installation or Metal preflight fails.
Select the installed MCP server or the absolute project-local executable before any campaign
call. If a shell is already confined and cannot start the launcher, use the configured MCP
server. A preflight failure stops modeled work.
Run `logo_campaign` with action `preflight` on the logo folder, or use the installed CLI's
`campaign <logo-dir> preflight`. Proceed after it verifies Seatbelt, Cycles Metal and GPU OIDN.
Report a failing check and stop modeled work until preflight passes. The launcher applies the
verified binary archive workaround and confines its scratch and cache files to the project.
Run scene generators through the campaign's `author` action, using the locked `bpy` module.
It checks Metal before importing `bpy`. If preflight fails, stop before attempting any
Blender executable, alternate launch flags, or direct `bpy` imports. Retain the failing result.

If [Codex #16931](https://github.com/openai/codex/issues/16931) reproduces, consult
`docs/research/codex-metal-primary-sources-20261113.md` in the tool checkout for the local CLI
patch, build provenance and boundary checks. The patched runtime is installed alongside
the project and the installed Blender and Codex applications remain separate.

## Use what already works

- For full 3D, prefer MCP when `logo_doctor` is available and the server shares the files you can
  edit. Read its `failed` count and individual check rows. An MCP tool can return successfully
  with failed checks.
- Otherwise use `logo-maker --help` in the shell, then `logo-maker doctor` for 3D. From another
  project's directory, a working checkout can run the CLI as
  `uv run --locked --project "$maker_repo" logo-maker doctor`. Set `maker_repo` to the actual
  absolute logo-maker checkout. Use the same prefix for subsequent stages and replace
  `logo-maker` with `python` to run the flat recipe.
- For flat work, check the imports in [flat assets](flat-assets.md). This route needs a Python
  environment with the motif dependencies. It uses neither a Jev key nor a GPU render.

## When a working checkout is missing

Find the logo-maker checkout from the installed MCP command or the skill's resolved location.
If needed, set `maker_repo` to an unused absolute tools path outside the user's project and clone:

```sh
git clone https://github.com/nicolas-found42/logo-maker.git "$maker_repo"
```

For flat work without a working checkout environment, use a minimal Python environment from
the checkout. This skips the 3D dependencies, Node packages and kernel warm-up:

```sh
cd "$maker_repo"
uv run --no-project --python 3.13 --with drawsvg --with skia-pathops --with resvg-py --with pillow --with fonttools --with httpx --with vtracer python -c 'from logo_maker.motif import Motif; from PIL import Image'
```

To run either flat recipe this way, keep that working directory and replace the recipe's
`uv run --locked --project "$maker_repo" python` prefix with the minimal command through
`python`. Add adapter dependencies only when the chosen design uses them.

For full 3D, use Apple silicon macOS, `uv`, Node 24, Homebrew and `just`. From the checkout:

```sh
cd "$maker_repo"
just setup
uv run --locked logo-maker doctor
```

The first Metal kernel compilation can be quiet for 1.5–5 minutes. Allow up to 900 seconds for
that setup step. A failed check has a `problem` and suggested `fix`. Interpret them in context.
3D study rendering and packaging can proceed without Jev credentials. Jev review and the
qualified workflow require `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY` in the tool process. If the
user wants to configure access, name the variable and local environment or host settings where
it goes. Keep credentials out of chat and job files. Restart the MCP host after changing its
environment. Doctor checks key presence. A real `review-study` or `brief` call checks access.

The project-local CLI works without registering an MCP server. For a permanent host install, use
the project's `uv run --locked python scripts/install.py --help`, then its `--agent codex`,
`--agent claude`, `--agent omp`, or `--agent skills --destination /path/to/skills/logo-maker`
option as appropriate. Use `--dry-run` to inspect the planned changes. Hosts that cache skills
may need a refresh to pick up source edits. Run doctor in the environment that will do the work.

If full 3D setup or qualification cannot proceed, deliver the requested flat files or a flat
concept study while preserving the source for continuation. Use the matching Metal/Cycles and
GPU OIDN host for production renders. See [recovery](recovery.md) for technical stops.
