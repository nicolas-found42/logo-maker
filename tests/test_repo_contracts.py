"""Repository contracts: generated docs, adapter licenses, installed skill copies, doctor checks."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import scripts.gen_docs as gen_docs
import scripts.install as install
import scripts.skill_check as skill_check
from logo_maker import doctor
from logo_maker.adapters import NodePackage, all_adapters

ROOT = Path(__file__).resolve().parents[1]


def test_generated_docs_are_current() -> None:
    assert gen_docs.main(["--check"]) == 0


def test_adapter_licenses_match_the_installed_npm_manifests() -> None:
    checked = 0
    for adapter in all_adapters():
        if not isinstance(adapter.check, NodePackage):
            continue
        manifest = adapter.check.manifest()
        if not manifest.exists():
            continue
        declared = json.loads(manifest.read_text())["license"]
        assert declared in adapter.license, f"{adapter.name}: package declares {declared}"
        checked += 1
    if not checked:
        pytest.skip("js dependencies not installed")


def test_copy_install_bundles_the_linked_sampling_policy(tmp_path: Path) -> None:
    destination = tmp_path / "logo-maker"
    install.copy_skill(destination)
    assert skill_check.validate_skill(destination / "SKILL.md") == []
    for markdown in destination.rglob("*.md"):
        for target in re.findall(r"\]\(([^)#]+\.md)", markdown.read_text()):
            if "://" not in target:
                assert (markdown.parent / target).resolve().exists(), (markdown.name, target)
    assert not any("docs/automatic-sampling" in p.read_text() for p in destination.rglob("*.md"))


def test_node_check_is_bounded_and_names_unreadable_versions(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/node")
    seen = {}

    def fake(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="not a version\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    assert "cannot read a node version" in str(doctor._node())
    assert seen["timeout"] > 0

    def hang(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    assert "timed out" in str(doctor._node())


def test_gen_docs_rejects_a_mistyped_flag_without_writing(capsys) -> None:
    docs = {path: path.read_text() for path in (ROOT / "docs").glob("*.md")}
    with pytest.raises(SystemExit) as raised:
        gen_docs.main(["--unknown-option"])
    assert raised.value.code == 2
    assert {path: path.read_text() for path in docs} == docs
    assert "unrecognized arguments: --unknown-option" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("attribute", "register", "content"),
    [
        ("OMP_MCP", "register_omp_mcp", "[]"),
        ("OMP_MCP", "register_omp_mcp", '{"mcpServers": null}'),
        ("OMP_MCP", "register_omp_mcp", "{bad"),
        ("CLAUDE_JSON", "register_claude_mcp", "[]"),
        ("CODEX_CONFIG", "register_codex_mcp", "mcp_servers = 3\n"),
        ("CODEX_CONFIG", "register_codex_mcp", '[mcp_servers]\n"logo-maker" = 5\n'),
    ],
)
def test_damaged_host_config_names_the_file(tmp_path, monkeypatch, attribute, register, content):
    config = tmp_path / "host-config"
    config.write_text(content)
    monkeypatch.setattr(install, attribute, config)
    with pytest.raises(ValueError, match="host-config"):
        getattr(install, register)(dry_run=True)
    assert config.read_text() == content


def test_unreadable_host_config_names_the_file(tmp_path, monkeypatch) -> None:
    config = tmp_path / "mcp.json"
    config.mkdir()
    monkeypatch.setattr(install, "OMP_MCP", config)
    with pytest.raises(ValueError, match=r"mcp\.json: cannot read"):
        install.register_omp_mcp(dry_run=True)


def test_doctor_flags_an_unusable_download_cache(tmp_path, monkeypatch) -> None:
    blocker = tmp_path / "cache-file"
    blocker.write_text("not a folder")
    monkeypatch.setenv("LOGO_MAKER_CACHE", str(blocker))
    assert "as the download cache" in str(doctor._cache())
    monkeypatch.setenv("LOGO_MAKER_CACHE", str(tmp_path / "cache"))
    assert doctor._cache() is None


def test_copy_install_dry_run_preserves_host_symlink(tmp_path, monkeypatch, capsys):
    target = tmp_path / "logo-maker"
    source = ROOT / "skills/logo-maker"
    target.symlink_to(source, target_is_directory=True)
    config = tmp_path / "mcp.json"
    monkeypatch.setitem(install.SKILL_DIRS, "omp", target)
    monkeypatch.setattr(install, "OMP_MCP", config)

    assert install.main(["--agent", "omp", "--copy", "--dry-run"]) == 0

    assert target.is_symlink()
    assert target.resolve() == source
    assert not config.exists()
    assert "Dry run complete." in capsys.readouterr().out


@pytest.mark.parametrize("previous_exists", [False, True])
def test_link_install_dry_run_preserves_previous_checkout_link(
    tmp_path, monkeypatch, previous_exists
):
    target = tmp_path / "logo-maker"
    previous = tmp_path / "previous"
    if previous_exists:
        previous.mkdir()
    target.symlink_to(previous, target_is_directory=True)
    config = tmp_path / "mcp.json"
    monkeypatch.setitem(install.SKILL_DIRS, "omp", target)
    monkeypatch.setattr(install, "OMP_MCP", config)

    assert install.main(["--agent", "omp", "--dry-run"]) == 0

    assert target.readlink() == previous
    assert not config.exists()
