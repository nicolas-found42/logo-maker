# Dev tasks. `uv run --locked` also fails if uv.lock is stale.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the recipes.
default:
    @just --list

# Install every tool: Homebrew go + fontforge, primitive, Python env, npm packages, Metal kernels.
setup:
    python3 scripts/setup.py

# Compile Cycles Metal kernels once (1.5-5 min on first run, cached in ~/.cache/cycles).
warm-gpu:
    uv run --locked python scripts/warm_gpu.py

# Check every adapter, the GPU, Node, and the jev API key.
doctor:
    uv run --locked logo-maker doctor

# Ruff check and format check.
lint:
    uv run --locked ruff check .
    uv run --locked ruff format --check .
    uv run --locked python scripts/skill_check.py

# Apply ruff formatting and fixes.
fmt:
    uv run --locked ruff check --fix .
    uv run --locked ruff format .

# Type check with ty.
type:
    uv run --locked ty check

# Offline tests (no renders, no jev). Extra pytest arguments pass through.
test *args:
    uv run --locked python -m pytest -q -m "not render and not live" {{ args }}

# The regression render of the bundled example (GPU; about a minute after kernels are warm).
render-example:
    uv run --locked python -m pytest -q -m render

# Every local hook over all files.
hooks:
    uvx prek run --all-files

# Everything CI runs, plus the regression render.
check: hooks lint type test render-example
