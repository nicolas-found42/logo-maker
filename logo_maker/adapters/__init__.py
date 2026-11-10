"""Adapter registry: every external tool logo-maker can use, with its stage, license, and health check.

Each slice declares its adapters in `logo_maker/adapters/<slice>.py` as a module-level `ADAPTERS` list.
`doctor()` runs every check; the pipeline and the agent only pick adapters whose check passes.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
from collections.abc import Callable
from dataclasses import dataclass

STAGES = (
    "judgment",
    "motif_2d",
    "color_type",
    "geometry_3d",
    "materials_lighting",
    "rendering",
    "post_export",
)
SLICES = ("jev", "twod", "threed", "render_export")


@dataclass(frozen=True)
class Adapter:
    name: str  # the tool's own name, e.g. "rough.js"
    stage: str  # one of STAGES
    license: str  # SPDX id where one exists
    summary: str  # one line: what logo-maker uses it for
    entry: str  # the logo_maker callable that runs it, "module:function"
    check: Callable[[], str | None]  # None when usable; otherwise the problem
    fix: str  # exact command that makes check pass
    required: bool = (
        True  # False: an alternate tool; doctor warns instead of failing when it is unusable
    )


def python_module(module: str) -> Callable[[], str | None]:
    def check() -> str | None:
        return None if importlib.util.find_spec(module) else f"python module {module} not installed"

    return check


def binary(name: str) -> Callable[[], str | None]:
    def check() -> str | None:
        return None if shutil.which(name) else f"{name} not on PATH"

    return check


def node_package(package: str) -> Callable[[], str | None]:
    def check() -> str | None:
        from logo_maker.paths import JS_DIR

        manifest = JS_DIR / "node_modules" / package / "package.json"
        if shutil.which("node") is None:
            return "node not on PATH"
        return None if manifest.exists() else f"js/node_modules/{package} missing"

    return check


def all_adapters() -> list[Adapter]:
    adapters: list[Adapter] = []
    for slice_name in SLICES:
        module = importlib.import_module(f"logo_maker.adapters.{slice_name}")
        adapters.extend(module.ADAPTERS)
    names = [a.name for a in adapters]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise RuntimeError(f"duplicate adapter names: {sorted(duplicates)}")
    bad = [a.name for a in adapters if a.stage not in STAGES]
    if bad:
        raise RuntimeError(f"adapters with unknown stage: {bad}")
    return adapters


def doctor() -> list[tuple[Adapter, str | None]]:
    """(adapter, problem) for every adapter; problem is None when the adapter is usable."""
    results = []
    for adapter in all_adapters():
        try:
            problem = adapter.check()
        except Exception as exc:  # a broken check is itself a problem worth showing
            problem = f"check raised {type(exc).__name__}: {exc}"
        results.append((adapter, problem))
    return results


def available(stage: str | None = None) -> list[Adapter]:
    return [a for a, problem in doctor() if problem is None and (stage is None or a.stage == stage)]
