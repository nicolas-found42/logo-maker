#!/usr/bin/env python3
"""Install the logo-maker plugin into an agent host, or print a preview.

Hosts:
  claude  link the skill into ~/.claude/skills and register a user-scope MCP server (claude mcp add-json)
  codex   Codex plugin CLI (a cached copy of the skill) and an [mcp_servers.logo-maker] entry in
          ~/.codex/config.toml
  omp     link the skill into ~/.omp/agent/skills and register the MCP server in ~/.omp/agent/mcp.json
  skills  copy the bare skill folder to a destination for any Agent Skills host

Every host runs the MCP server as `uv run --quiet --project <this checkout> logo-maker mcp`, so a
restart of the server picks up source edits with no reinstall (dependency edits re-sync on start).
Every host also gets the `logo-maker` command via `uv tool install --editable <repo>`.
Run `just setup` first so the renderers, fonts tooling, and npm packages exist.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import tomlkit

ROOT = Path(__file__).resolve().parents[1]
NAME = "logo-maker"
REPO_URL = "https://github.com/nicolas-found42/logo-maker"
MARKETPLACE = "logo-maker-plugins"
OMP_MCP = Path.home() / ".omp/agent/mcp.json"
CLAUDE_JSON = Path.home() / ".claude.json"
CODEX_CONFIG = Path.home() / ".codex/config.toml"
# omp and Claude read a linked skill folder directly, so skill edits are live there too.
SKILL_DIRS = {
    "omp": Path.home() / ".omp/agent/skills",
    "claude": Path.home() / ".claude/skills",
}
# A render can spend minutes compiling Metal kernels; the hosts' default tool timeouts are shorter.
TOOL_TIMEOUT_S = 3600


def mcp_command() -> list[str]:
    return ["uv", "run", "--quiet", "--project", str(ROOT), NAME, "mcp"]


def plugin_commands(agent: str) -> list[list[str]]:
    if agent == "codex":
        return [
            ["codex", "plugin", "marketplace", "add", str(ROOT)],
            ["codex", "plugin", "add", f"{NAME}@{MARKETPLACE}"],
        ]
    raise ValueError(agent)


def run(cmd: list[str], *, dry_run: bool) -> None:
    print(shlex.join(cmd), flush=True)
    if not dry_run:
        subprocess.run(cmd, check=True)


def copy_skill(destination: Path, *, source_root: Path = ROOT) -> None:
    """Copy the skill folder and make its links to `docs/` resolve without the checkout.

    Skill files reach the sampling policy through `../../docs/automatic-sampling.md`, which only
    resolves beside the repo (or through a symlink). A copy ships the policy inside the skill
    and re-points those links; the policy's own link to a benchmark file becomes a repo URL.
    """
    source = source_root / "skills" / NAME
    if destination.is_symlink():
        destination.unlink()  # a prior linked install; the copy replaces it
    if destination.resolve() == source.resolve():
        raise ValueError(f"destination {destination} is the plugin's own skill folder")
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    bundled = destination / "references" / "automatic-sampling.md"
    text = (source_root / "docs" / "automatic-sampling.md").read_text()
    bundled.write_text(text.replace("(../benchmarks/", f"({REPO_URL}/blob/main/benchmarks/"))
    for markdown in destination.rglob("*.md"):
        if markdown == bundled:
            continue
        depth = len(markdown.relative_to(destination).parts) - 1
        target = "/".join([*([".."] * depth), "references/automatic-sampling.md"])
        body = markdown.read_text()
        updated = re.sub(r"(?:\.\./)+docs/automatic-sampling\.md", target, body)
        if updated != body:
            markdown.write_text(updated)


def install_cli(*, dry_run: bool) -> None:
    run(
        ["uv", "tool", "install", "--force", "--python", "3.13", "--editable", str(ROOT)],
        dry_run=dry_run,
    )


def link_skill(destination: Path, *, dry_run: bool) -> None:
    source = ROOT / "skills" / NAME
    replace_link = destination.is_symlink()
    if replace_link and destination.resolve() == source.resolve():
        print(f"already installed: {destination} -> {source}")
        return
    if not replace_link and destination.exists():
        raise ValueError(f"destination exists and is not a link to this plugin: {destination}")
    print(shlex.join(["ln", "-s", str(source), str(destination)]), flush=True)
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if replace_link:
        destination.unlink()
    destination.symlink_to(source)


def mcp_entry() -> dict:
    command, *args = mcp_command()
    return {"type": "stdio", "command": command, "args": args, "timeout": TOOL_TIMEOUT_S * 1000}


def _host_config(path: Path, parse, servers_key: str) -> tuple[dict, dict]:
    """A host config mapping and its MCP server table; damage names the file, not a traceback."""
    if not path.exists():
        return {}, {}
    try:
        data = parse(path.read_text())
    except (OSError, UnicodeDecodeError, ValueError) as exc:  # unreadable, or JSON/TOML errors
        raise ValueError(f"{path}: cannot read ({exc}); fix or move it") from exc
    servers = data.get(servers_key, {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict) or not isinstance(servers.get(NAME, {}), dict):
        raise ValueError(f"{path}: expected an object of {servers_key} entries; fix or move it")
    return data, servers


def register_omp_mcp(*, dry_run: bool) -> None:
    data, servers = _host_config(OMP_MCP, json.loads, "mcpServers")
    entry = mcp_entry()
    if servers.get(NAME) == entry:
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


def register_claude_mcp(*, dry_run: bool) -> None:
    """User-scope entry via the CLI (~/.claude.json is live host state; never edit it directly).

    User scope, not the plugin's .mcp.json: a plugin install is a cached copy of the repo and
    Claude loads it as a second server (doubled tools) rather than deduplicating it.
    """
    entry = mcp_entry()
    _data, servers = _host_config(CLAUDE_JSON, json.loads, "mcpServers")
    if servers.get(NAME) == entry:
        print(f"already registered: {NAME} in {CLAUDE_JSON}")
        return
    print(f"register {NAME} MCP server in {CLAUDE_JSON}", flush=True)
    if dry_run:
        return
    subprocess.run(["claude", "mcp", "remove", "--scope", "user", NAME], capture_output=True)
    run(["claude", "mcp", "add-json", "--scope", "user", NAME, json.dumps(entry)], dry_run=False)


def register_codex_mcp(*, dry_run: bool) -> None:
    command, *args = mcp_command()
    doc, servers = _host_config(CODEX_CONFIG, tomlkit.parse, "mcp_servers")
    doc = doc or tomlkit.document()
    want = {
        "command": command,
        "args": args,
        "startup_timeout_sec": 120,
        "tool_timeout_sec": TOOL_TIMEOUT_S,
        # Codex starts MCP servers with a scrubbed environment; jev judgments need the key.
        "env_vars": ["OPENROUTER_API_KEY", "TYPESAFE_API_KEY"],
    }
    if NAME in servers and all(servers[NAME].get(k) == v for k, v in want.items()):
        print(f"already registered: {NAME} in {CODEX_CONFIG}")
        return
    print(f"register {NAME} MCP server in {CODEX_CONFIG}", flush=True)
    if dry_run:
        return
    if CODEX_CONFIG.exists():
        shutil.copy2(CODEX_CONFIG, CODEX_CONFIG.with_name(CODEX_CONFIG.name + ".bak-logo-maker"))
    doc.setdefault("mcp_servers", tomlkit.table(is_super_table=True))[NAME] = want
    CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CODEX_CONFIG.write_text(tomlkit.dumps(doc))


def install_codex_project(project: Path, *, dry_run: bool, upgrade: bool = False) -> None:
    """Install a project-scoped skill and locked server from one source snapshot."""
    project = project.resolve()
    tool = project / ".codex" / "logo-maker"
    skill = project / ".agents" / "skills" / NAME
    config = project / ".codex" / "config.toml"
    if upgrade:
        if not (tool / "install.json").is_file() or not (skill / "SKILL.md").is_file():
            raise ValueError("upgrade requires a project-scoped logo-maker installation")
    elif tool.exists() or skill.exists() or skill.is_symlink():
        raise ValueError("project already has logo-maker; use --upgrade for a scoped install")
    print(f"install logo-maker snapshot in {tool} and skill in {skill}")
    if dry_run:
        return
    doc, servers = _host_config(config, tomlkit.parse, "mcp_servers")
    if NAME in servers and not upgrade:
        raise ValueError(f"project already configures {NAME}: {config}")
    if upgrade:
        _upgrade_codex_project(project, tool, skill)
    else:
        _install_snapshot(tool)
        copy_skill(skill, source_root=tool)
    doc = doc or tomlkit.document()
    doc.setdefault("mcp_servers", tomlkit.table(is_super_table=True))[NAME] = {
        "command": str(tool / ".venv/bin/logo-maker"),
        "args": ["mcp"],
        "startup_timeout_sec": 120,
        "tool_timeout_sec": TOOL_TIMEOUT_S,
        "env_vars": ["OPENROUTER_API_KEY"],
    }
    with TemporaryDirectory(prefix=".logo-maker-config-", dir=config.parent) as temporary:
        staged = Path(temporary) / "config.toml"
        staged.write_text(tomlkit.dumps(doc))
        staged.replace(config)


def _install_snapshot(tool: Path) -> None:
    tool.mkdir(parents=True)
    for directory in ("logo_maker", "js", "skills", "docs"):
        shutil.copytree(
            ROOT / directory,
            tool / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"),
        )
    for name in ("uv.lock", "pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(ROOT / name, tool / name)
    revision = {
        p.relative_to(tool).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted(tool.rglob("*"))
        if p.is_file()
    }
    (tool / "install.json").write_text(json.dumps(revision, indent=2) + "\n")
    subprocess.run(["npm", "ci", "--prefix", str(tool / "js")], check=True)
    subprocess.run(["uv", "sync", "--locked", "--project", str(tool)], check=True)


def _upgrade_codex_project(project: Path, tool: Path, skill: Path) -> None:
    # Keep the environment at its original path because venv launchers contain absolute paths.
    backup = tool.parent / (
        "logo-maker-backup-" + sha256((tool / "install.json").read_bytes()).hexdigest()[:12]
    )
    if backup.exists():
        raise ValueError(f"preserve or move the existing upgrade backup: {backup}")
    backup.mkdir()
    tool.rename(backup / "tool")
    try:
        skill.rename(backup / "skill")
        _install_snapshot(tool)
        copy_skill(skill, source_root=tool)
        if (project / ".codex/logo-maker-runtime").is_dir():
            with TemporaryDirectory(prefix=".logo-maker-upgrade-", dir=project) as temporary:
                probe = Path(temporary)
                (probe / "brief.toml").write_text(
                    'name = "Runtime preflight"\nsummary = "Upgrade verification."\n'
                )
                record = probe / "preflight.json"
                record.write_text('{"refresh": true}\n')
                subprocess.run(
                    [
                        str(tool / ".venv/bin/logo-maker"),
                        "campaign",
                        str(probe),
                        "preflight",
                        "--record",
                        str(record),
                    ],
                    check=True,
                    cwd=project,
                    timeout=930,
                )
    except BaseException:
        if (backup / "skill").exists():
            if skill.exists():
                skill.rename(backup / "failed-skill")
            (backup / "skill").rename(skill)
        if tool.exists():
            tool.rename(backup / "failed-tool")
        (backup / "tool").rename(tool)
        raise
    print(f"Prior tool and skill retained in {backup}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--agent", required=True, choices=("codex", "claude", "omp", "skills"))
    parser.add_argument(
        "--destination",
        type=Path,
        help="skill folder for --agent skills, or project root for a scoped Codex install",
    )
    parser.add_argument("--dry-run", action="store_true", help="print actions without running them")
    parser.add_argument(
        "--upgrade", action="store_true", help="upgrade a scoped Codex installation"
    )
    parser.add_argument(
        "--metal-runtime",
        type=Path,
        help="install the verified patched Codex binary in the scoped project",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="with --agent omp|claude: copy the skill instead of linking it",
    )
    args = parser.parse_args(argv)

    try:
        if args.agent == "codex" and args.destination is not None:
            if args.metal_runtime and not args.dry_run:
                sys.path.insert(0, str(ROOT))
                from logo_maker.campaign_runtime import install_runtime

                print(install_runtime(args.destination, args.metal_runtime), flush=True)
            install_codex_project(args.destination, dry_run=args.dry_run, upgrade=args.upgrade)
            return 0
        install_cli(dry_run=args.dry_run)
        if args.agent in SKILL_DIRS:
            if not args.dry_run and args.agent == "claude" and shutil.which("claude") is None:
                raise ValueError("claude is not on PATH; install the host first, or use --dry-run")
            target = SKILL_DIRS[args.agent] / NAME
            if args.copy:
                print(
                    shlex.join(["cp", "-R", str(ROOT / "skills" / NAME), str(target)]), flush=True
                )
                if not args.dry_run:
                    copy_skill(target)
            else:
                link_skill(target, dry_run=args.dry_run)
            if args.agent == "omp":
                register_omp_mcp(dry_run=args.dry_run)
            else:
                register_claude_mcp(dry_run=args.dry_run)
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
                copy_skill(args.destination)
        else:
            if not args.dry_run and shutil.which(args.agent) is None:
                raise ValueError(
                    f"{args.agent} is not on PATH; install the host first, or use --dry-run"
                )
            for command in plugin_commands(args.agent):
                run(command, dry_run=args.dry_run)
            register_codex_mcp(dry_run=args.dry_run)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print("Dry run complete.")
    else:
        print("Installed. Check the toolchain with `logo-maker doctor`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
