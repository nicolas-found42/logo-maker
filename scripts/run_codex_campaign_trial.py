"""Run one fresh Codex trial against an installed campaign MCP server."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from logo_maker.campaign_runtime import CODE_MODE_HOST_SHA256, _installation
from logo_maker.sampling_diagnostics import sha256


def _filesystem(policy: str) -> str:
    return (
        f'{policy}.filesystem={{":root"="read",":workspace_roots"="write",'
        '"/Applications/Blender.app"="deny",'
        '"/opt/homebrew/Caskroom/blender"="deny",'
        '"/**/bpy/__init__.so"="deny"}'
    )


def run(project: Path, trial: Path, request: Path, events: Path) -> int:
    """Keep trial-shell access narrow. The MCP server owns the separate Metal worker."""
    project, trial = project.resolve(), trial.resolve()
    if not trial.is_relative_to(project) or trial == project:
        raise ValueError("use a dedicated trial folder inside the installed project")
    _, codex = _installation(project)
    host = codex.with_name("codex-code-mode-host")
    if not host.is_file() or sha256(host) != CODE_MODE_HOST_SHA256:
        raise ValueError("install the matching Codex code-mode host before starting a trial")
    tool = project / ".codex" / "logo-maker" / ".venv" / "bin" / "logo-maker"
    skill = project / ".agents" / "skills" / "logo-maker" / "SKILL.md"
    if not tool.is_file() or not skill.is_file():
        raise ValueError("install the scoped campaign tool and skill before starting a trial")
    installed = project / ".codex" / "logo-maker" / "install.json"
    receipt = {
        "codex_sha256": sha256(codex),
        "code_mode_host_sha256": sha256(host),
        "install_manifest_sha256": sha256(installed),
        "skill_sha256": sha256(skill),
        "request_sha256": sha256(request),
    }
    policy = "permissions.logo-maker-trial"
    settings = [
        'approval_policy="never"',
        'default_permissions="logo-maker-trial"',
        "features.code_mode=false",
        "features.code_mode_only=false",
        _filesystem(policy),
        f"{policy}.network.enabled=false",
        f"mcp_servers.logo-maker.command={json.dumps(str(tool))}",
        'mcp_servers.logo-maker.args=["mcp"]',
        'mcp_servers.logo-maker.enabled_tools=["logo_new","logo_campaign"]',
        'mcp_servers.logo-maker.tools.logo_new.approval_mode="approve"',
        'mcp_servers.logo-maker.tools.logo_campaign.approval_mode="approve"',
        'mcp_servers.logo-maker.env_vars=["OPENROUTER_API_KEY"]',
        "mcp_servers.logo-maker.tool_timeout_sec=3600",
    ]
    command = [
        str(codex),
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(trial),
        "--json",
    ]
    for setting in settings:
        command.extend(("-c", setting))
    prompt = (
        request.read_text()
        + f"""

Use the installed logo-maker skill at {skill}. Keep outputs under {trial}.
Use the configured logo-maker MCP tools for campaign operations and absolute logo paths.
Run preflight before 3D work, and stop modeled work if it fails.
Run scene generators through campaign author. Present exact artifacts for owner review.
"""
    )
    with events.with_suffix(".inputs.json").open("x") as file:
        json.dump(receipt, file, indent=2)
        file.write("\n")
    with events.open("x") as log:
        scratch = trial / ".trial-tmp"
        scratch.mkdir(exist_ok=True)
        if scratch.resolve() != scratch:
            raise ValueError("trial temporary directory must stay inside the trial")
        return subprocess.run(
            [*command, "-"],
            input=prompt,
            stdout=log,
            text=True,
            env={**os.environ, "TMPDIR": str(scratch)},
        ).returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("trial", type=Path)
    parser.add_argument("request", type=Path)
    parser.add_argument("events", type=Path)
    args = parser.parse_args()
    raise SystemExit(run(args.project, args.trial, args.request, args.events))
