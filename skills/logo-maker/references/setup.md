# Tool setup

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
A missing Jev key requires `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY` in the process that runs the
pipeline. If a user must supply a key, name the variable and the local environment or host settings
where it goes. Keep credentials out of chat and job files. Restart the MCP host after changing its
environment. Doctor checks key presence. A real `brief` call checks provider access.

The project-local CLI works without registering an MCP server. For a permanent host install, use
the project's `uv run --locked python scripts/install.py --help`, then its `--agent codex`,
`--agent claude`, `--agent omp`, or `--agent skills --destination /path/to/skills/logo-maker`
option as appropriate. Use `--dry-run` to inspect the planned changes. Hosts that cache skills
may need a refresh to pick up source edits. Run doctor in the environment that will do the work.

If full 3D setup or qualification cannot proceed, deliver the requested flat files or a flat
concept study while preserving the source for continuation. Use the matching Metal/Cycles and
GPU OIDN host for production renders. See [recovery](recovery.md) for technical stops.
