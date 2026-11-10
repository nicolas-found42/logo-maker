#!/usr/bin/env python3
"""Install the logo-maker plugin into an agent host, or print a preview.

Hosts:
  claude  Claude Code plugin CLI (marketplace add + install); the plugin's .mcp.json starts the MCP server
  codex   Codex plugin CLI (marketplace add + install); .codex-plugin/plugin.json declares skill + MCP server
  omp     link the skill into ~/.omp/agent/skills and register the MCP server in ~/.omp/agent/mcp.json
  skills  copy the bare skill folder to a destination for any Agent Skills host

Every host also gets the `logo-maker` command via `uv tool install --editable <repo>`.
Run `just setup` first so the renderers, fonts tooling, and npm packages exist.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "logo-maker"
MARKETPLACE = "logo-maker-plugins"
OMP_MCP = Path.home() / ".omp/agent/mcp.json"


def plugin_commands(agent: str) -> list[list[str]]:
    if agent == "codex":
        return [
            ["codex", "plugin", "marketplace", "add", str(ROOT)],
            ["codex", "plugin", "add", f"{NAME}@{MARKETPLACE}"],
        ]
    if agent == "claude":
        return [
            ["claude", "plugin", "marketplace", "add", str(ROOT)],
            ["claude", "plugin", "install", f"{NAME}@{MARKETPLACE}"],
        ]
    raise ValueError(agent)


def run(cmd: list[str], *, dry_run: bool) -> None:
    print(shlex.join(cmd), flush=True)
    if not dry_run:
        subprocess.run(cmd, check=True)


def install_cli(*, dry_run: bool) -> None:
    run(
        ["uv", "tool", "install", "--force", "--python", "3.13", "--editable", str(ROOT)],
        dry_run=dry_run,
    )


def link_skill(destination: Path, *, dry_run: bool) -> None:
    source = ROOT / "skills" / NAME
    if destination.is_symlink():
        if destination.resolve() == source.resolve():
            print(f"already installed: {destination} -> {source}")
            return
        destination.unlink()
    if destination.exists():
        raise ValueError(f"destination exists and is not a link to this plugin: {destination}")
    print(shlex.join(["ln", "-s", str(source), str(destination)]), flush=True)
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source)


def register_omp_mcp(*, dry_run: bool) -> None:
    data = json.loads(OMP_MCP.read_text()) if OMP_MCP.exists() else {"mcpServers": {}}
    entry = {
        "type": "stdio",
        "command": shutil.which(NAME) or NAME,
        "args": ["mcp"],
        "timeout": 3_600_000,
    }
    if data.get("mcpServers", {}).get(NAME) == entry:
        print(f"already registered: {NAME} in {OMP_MCP}")
        return
    print(f"register {NAME} MCP server in {OMP_MCP}", flush=True)
    if dry_run:
        return
    if OMP_MCP.exists():
        shutil.copy2(OMP_MCP, OMP_MCP.with_name(OMP_MCP.name + ".bak-logo-maker"))
    data.setdefault("mcpServers", {})[NAME] = entry
    OMP_MCP.parent.mkdir(parents=True, exist_ok=True)
    OMP_MCP.write_text(json.dumps(data, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--agent", required=True, choices=("codex", "claude", "omp", "skills"))
    parser.add_argument(
        "--destination",
        type=Path,
        help="for --agent skills only: the full destination skill folder",
    )
    parser.add_argument("--dry-run", action="store_true", help="print actions without running them")
    parser.add_argument(
        "--copy", action="store_true", help="with --agent omp: copy the skill instead of linking it"
    )
    args = parser.parse_args(argv)

    try:
        install_cli(dry_run=args.dry_run)
        if args.agent == "omp":
            target = Path.home() / ".omp/agent/skills" / NAME
            if args.copy:
                if target.is_symlink():
                    target.unlink()
                print(
                    shlex.join(["cp", "-R", str(ROOT / "skills" / NAME), str(target)]), flush=True
                )
                if not args.dry_run:
                    shutil.copytree(ROOT / "skills" / NAME, target, dirs_exist_ok=True)
            else:
                link_skill(target, dry_run=args.dry_run)
            register_omp_mcp(dry_run=args.dry_run)
        elif args.agent == "skills":
            if args.destination is None:
                parser.error("--agent skills requires --destination /path/to/skills/logo-maker")
            if args.destination.name != NAME:
                parser.error(f"the destination skill folder must be named {NAME}")
            print(
                shlex.join(["cp", "-R", str(ROOT / "skills" / NAME), str(args.destination)]),
                flush=True,
            )
            if not args.dry_run:
                shutil.copytree(
                    ROOT / "skills" / NAME,
                    args.destination,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
        else:
            if not args.dry_run and shutil.which(args.agent) is None:
                raise ValueError(
                    f"{args.agent} is not on PATH; install the host first, or use --dry-run"
                )
            for command in plugin_commands(args.agent):
                run(command, dry_run=args.dry_run)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 1
    print("Installed. Check the toolchain with `logo-maker doctor`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
