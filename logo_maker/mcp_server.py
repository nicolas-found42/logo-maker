"""`logo-maker mcp`: each pipeline stage as a typed MCP tool over stdio.

Tools return {"status": "done", "result": ...} or {"status": "authoring_needed", "message", "files"} so the
calling agent knows exactly which files to write before calling the stage again.
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer

from logo_maker import __version__
from logo_maker.cli import resolve_logo

INSTRUCTIONS = (
    "logo-maker turns a brief into a judged, rendered 3D logo and export set. Read the logo-maker skill "
    "first. Order: logo_new -> gather project/owner evidence into brief.toml and brief-evidence.toml -> "
    "logo_brief freezes reviewed requirements -> write ideation/metaphors.toml -> logo_run. "
    "Before previews, author each concept's plan.toml, motif and scene; logo_plan reviews intent. "
    "When a tool returns authoring_needed, consult evidence first, resolve consequential unknowns, "
    "write the listed files and call again. Plan approval never establishes actual-image quality."
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


async def _stage(fn: Callable[..., Any], target: str, out: str | None) -> dict[str, Any]:
    from logo_maker.pipeline import AuthoringNeeded, status

    logo = resolve_logo(target, Path(out) if out else None)

    def call() -> Any:
        # Stage code prints progress; stdout belongs to the MCP transport.
        with contextlib.redirect_stdout(io.StringIO()):
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
            "counts": {
                k: v for k, v in status(logo).items() if k not in {"revisions", "comparisons"}
            },
        }
    return {"status": "done", "result": _jsonable(result), "logo_dir": str(logo.root)}


@server.tool()
async def logo_new(slug: str, name: str, out: str | None = None) -> dict[str, Any]:
    """Create a logo folder with brief.toml, metaphors and proposals templates."""
    from logo_maker import pipeline

    logo = resolve_logo(slug, Path(out) if out else None)
    await anyio.to_thread.run_sync(lambda: pipeline.new(logo, name))
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
    """Check the jev API key, Node, the Metal GPU and kernel cache, and every adapter; same rows as `logo-maker doctor`."""
    from logo_maker.doctor import checks

    rows = await anyio.to_thread.run_sync(checks)
    failed = sum(not row["ok"] for row in rows)
    return {"passed": len(rows) - failed, "failed": failed, "checks": rows}


def serve() -> None:
    server.run("stdio")
