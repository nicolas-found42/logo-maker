"""`logo-maker mcp`: each pipeline stage as a typed MCP tool over stdio.

Tools return {"status": "done", "result": ...} or {"status": "authoring_needed", "message", "files"} so the
calling agent knows exactly which files to write before calling the stage again.
"""

from __future__ import annotations

import contextlib
import io
import sys
import threading
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError

from logo_maker import __version__
from logo_maker.cli import require_brief
from logo_maker.paths import resolve_logo

INSTRUCTIONS = (
    "Read the logo-maker skill first. For flat logos, icons and favicon-only work, "
    "use its flat asset recipe. These tools run the full 3D pipeline. "
    "Start new work with logo_doctor and logo_new. Reuse the returned absolute logo_dir as target. "
    "For existing work, start with logo_status on the folder containing brief.toml. "
    "Author the brief and its evidence, then use logo_brief, logo_intake and logo_ideate. "
    "Follow the skill through concept authoring, inspection, selection and export. "
    "When a stage returns authoring_needed, open the named files or artifacts, do the requested "
    "work, and rerun that stage or the prerequisite it names. For an active improvement, "
    "publish only through logo_improve so the challenger is compared with the current floor."
)

server = MCPServer(name="logo-maker", version=__version__, instructions=INSTRUCTIONS)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


class _StdoutToBuffer:
    """Keep stage progress off the MCP transport while any stage thread runs.

    `sys.stdout` is process-global, so overlapping tool calls share one redirect: the first
    entry installs it and the last exit restores the original stream.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._depth = 0
        self._saved: Any = None

    def __enter__(self) -> None:
        with self._lock:
            if self._depth == 0:
                self._saved, sys.stdout = sys.stdout, io.StringIO()
            self._depth += 1

    def __exit__(self, *_: object) -> None:
        with self._lock:
            self._depth -= 1
            if self._depth == 0:
                sys.stdout, self._saved = self._saved, None


_progress = _StdoutToBuffer()


@contextlib.contextmanager
def _agent_errors() -> Generator[None]:
    """The framework hides the text of unexpected exceptions; domain errors carry the fix."""
    try:
        yield
    except McpToolError:
        raise
    except (RuntimeError, ValueError, OSError) as exc:  # OSError text names the path
        raise McpToolError(str(exc)) from exc


def _out(out: str | None) -> Path | None:
    if out is None:
        return None
    if not out.strip():
        raise ValueError("out must be a folder path; omit it to use logos/<slug>")
    return Path(out)


async def _stage(fn: Callable[..., Any], target: str, out: str | None) -> dict[str, Any]:
    from logo_maker.pipeline import AuthoringNeeded, status_counts

    with _agent_errors():
        logo = require_brief(target, _out(out))

        def call() -> Any:
            # Stage code prints progress; stdout belongs to the MCP transport.
            with _progress:
                return fn(logo)

        try:
            result = await anyio.to_thread.run_sync(call)
        except AuthoringNeeded as exc:
            return {
                "status": "authoring_needed",
                "message": str(exc).splitlines()[0],
                "files": [str(f) for f in exc.files],
                "questions": exc.questions,
                "logo_dir": str(logo.root),
                "details": exc.details,
                "counts": status_counts(logo),
            }
        return {"status": "done", "result": _jsonable(result), "logo_dir": str(logo.root)}


@server.tool()
async def logo_new(slug: str, name: str, out: str | None = None) -> dict[str, Any]:
    """Create a logo folder with brief.toml, metaphors and proposals templates."""
    from logo_maker import pipeline

    with _agent_errors():
        logo = resolve_logo(slug, _out(out))
        title = name.strip() or slug.replace("-", " ").title()  # as the CLI does
        await anyio.to_thread.run_sync(lambda: pipeline.new(logo, title))
    return {
        "status": "done",
        "logo_dir": str(logo.root),
        "next": [str(logo.brief), str(logo.root / "brief-evidence.toml"), str(logo.metaphors)],
    }


@server.tool()
async def logo_brief(
    target: str, out: str | None = None, revision_reason: str = ""
) -> dict[str, Any]:
    """Review project/owner evidence and freeze requirements; name missing evidence before authoring."""
    from logo_maker import pipeline

    return await _stage(
        lambda logo: pipeline.review_brief(logo, revision_reason=revision_reason), target, out
    )


@server.tool()
async def logo_intake(target: str, out: str | None = None) -> dict[str, Any]:
    """Judge references; pick palette and fonts from ideation/proposals.toml when the brief lacks them."""
    from logo_maker import pipeline

    return await _stage(pipeline.intake, target, out)


@server.tool()
async def logo_ideate(target: str, out: str | None = None) -> dict[str, Any]:
    """Build up to 1000 concepts from the metaphors and run the jev chain to a shortlist of 8."""
    from logo_maker import pipeline

    return await _stage(pipeline.ideate, target, out)


@server.tool()
async def logo_plan(target: str, out: str | None = None) -> dict[str, Any]:
    """Review shortlisted concept hypotheses and purposeful detail plans before rendering."""
    from logo_maker import pipeline

    return await _stage(pipeline.review_plans, target, out)


@server.tool()
async def logo_motifs(target: str, out: str | None = None) -> dict[str, Any]:
    """Build each shortlisted motif.py into motif.svg/json and a size sheet; write starter scenes once."""
    from logo_maker import pipeline

    return await _stage(pipeline.motifs, target, out)


@server.tool()
async def logo_refine(target: str, out: str | None = None) -> dict[str, Any]:
    """Retain GPU previews; return inspection/creative authoring work and image comparisons."""
    from logo_maker import pipeline

    return await _stage(pipeline.refine, target, out)


@server.tool()
async def logo_status(target: str, out: str | None = None) -> dict[str, Any]:
    """Report text combinations, authored motifs, renders and completed refinement comparisons."""
    from logo_maker import pipeline

    return await _stage(pipeline.status, target, out)


@server.tool()
async def logo_preview(target: str, out: str | None = None) -> dict[str, Any]:
    """Render GPU previews of the shortlisted concepts and keep 3 finalists judged on the images."""
    from logo_maker import pipeline

    return await _stage(pipeline.preview, target, out)


@server.tool()
async def logo_finalize(target: str, out: str | None = None) -> dict[str, Any]:
    """Retained final renders with scoped technical/creative QA, then a head-to-head picks the winner."""
    from logo_maker import pipeline

    return await _stage(pipeline.finalize, target, out)


@server.tool()
async def logo_export(target: str, out: str | None = None) -> dict[str, Any]:
    """Write the export set (hero, avatar, favicons, SVGs, PWA, glb, blend, contact sheet) for the winner."""
    from logo_maker import pipeline

    return await _stage(pipeline.export, target, out)


@server.tool()
async def logo_run(target: str, out: str | None = None) -> dict[str, Any]:
    """Run every remaining stage; stops with authoring_needed where the agent must write files."""
    from logo_maker import pipeline

    return await _stage(pipeline.run, target, out)


@server.tool()
async def logo_improve(target: str, out: str | None = None) -> dict[str, Any]:
    """New round of ideas; the current logo stays unless the new winner beats it head-to-head."""
    from logo_maker import pipeline

    return await _stage(pipeline.improve, target, out)


@server.tool()
async def logo_doctor() -> dict[str, Any]:
    """Check the jev API key, Node, the Metal GPU and kernel cache, the download cache, and every adapter; same rows as `logo-maker doctor`."""
    from logo_maker.doctor import checks

    rows = await anyio.to_thread.run_sync(checks)
    failed = sum(not row["ok"] for row in rows)
    return {"passed": len(rows) - failed, "failed": failed, "checks": rows}


def serve() -> None:
    server.run("stdio")
