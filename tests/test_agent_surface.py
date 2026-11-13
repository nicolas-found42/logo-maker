"""The CLI and MCP surfaces an agent drives: shared guards, actionable errors, a clean stdout."""

from __future__ import annotations

import sys
import threading
import time

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError as McpToolError

from logo_maker import mcp_server, pipeline
from logo_maker.cli import main
from logo_maker.paths import LogoDir


def test_overlapping_mcp_stages_never_write_progress_to_the_transport(tmp_path, capsys):
    (tmp_path / "brief.toml").write_text("")
    original = sys.stdout
    first_in, second_in, first_done = threading.Event(), threading.Event(), threading.Event()

    def first(_logo):
        first_in.set()
        assert second_in.wait(5)
        first_done.set()
        return {}

    def second(_logo):
        assert first_in.wait(5)
        second_in.set()
        assert first_done.wait(5)
        time.sleep(0.2)  # the first call has now left its redirect while this one still prints
        print("second stage progress")
        return {}

    async def run_both():
        async with anyio.create_task_group() as group:
            group.start_soon(mcp_server._stage, first, "x", str(tmp_path))
            group.start_soon(mcp_server._stage, second, "x", str(tmp_path))

    anyio.run(run_both)
    assert sys.stdout is original
    assert "second stage progress" not in capsys.readouterr().out


def test_mcp_stage_on_a_missing_logo_fails_with_the_cli_message_and_creates_nothing(tmp_path):
    ghost = tmp_path / "ghost"
    for tool in (mcp_server.logo_status, mcp_server.logo_finalize, mcp_server.logo_export):
        with pytest.raises(McpToolError, match=r"no brief at .*logo-maker new"):
            anyio.run(tool, "ghost", str(ghost))
    assert not ghost.exists()


@pytest.mark.parametrize("target", ["", "my logo", "!!!"])
def test_missing_brief_hint_is_a_command_that_creates_the_missing_brief(tmp_path, target):
    import re
    import shlex

    ghost = tmp_path / "ghost dir"
    with pytest.raises(McpToolError) as raised:
        anyio.run(mcp_server.logo_status, target, str(ghost))
    hint = re.search(r"run `([^`]+)` first", str(raised.value))
    assert hint is not None
    argv = shlex.split(hint.group(1))
    assert argv[0] == "logo-maker"
    assert main(argv[1:]) == 0
    assert (ghost / "brief.toml").is_file()


def test_mcp_stage_failure_reaches_the_agent_with_its_message(tmp_path):
    (tmp_path / "brief.toml").write_text("")

    def failing(_logo):
        raise RuntimeError("no winner; run `logo-maker finalize x`")

    with pytest.raises(McpToolError, match="no winner; run"):
        anyio.run(mcp_server._stage, failing, "x", str(tmp_path))


def test_mcp_new_on_an_existing_logo_names_the_conflict(tmp_path):
    anyio.run(mcp_server.logo_new, "sample", "Sample", str(tmp_path))
    with pytest.raises(McpToolError, match="already exists"):
        anyio.run(mcp_server.logo_new, "sample", "Sample", str(tmp_path))


def test_cli_new_reports_an_existing_logo_or_unusable_slug_without_a_traceback(tmp_path, capsys):
    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["new", "sample", "--out", str(tmp_path)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert main(["new", "!!!"]) == 2
    assert "cannot make a slug" in capsys.readouterr().err
    assert main(["status", "!!!"]) == 2
    assert "cannot make a slug" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("relative", "content", "named"),
    [
        ("qa/comparisons.json", "not json", "comparisons.json"),
        ("ideation/shortlist.json", "[]", "shortlist.json"),
        ("ideation/shortlist.json", '{"ids": [1]}', "shortlist.json"),
        ("ideation/shortlist.json", '{"ids": [""]}', "shortlist.json"),
        ("qa/revisions/a/0001/revision.json", "{}", "revision.json"),
    ],
)
def test_cli_stage_errors_are_one_named_line_not_a_traceback(
    tmp_path, capsys, relative, content, named
):
    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    (tmp_path / "ideation").mkdir(exist_ok=True)
    (tmp_path / "ideation" / "shortlist.json").write_text('{"ids": ["a"]}')
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    capsys.readouterr()
    assert main(["status", "sample", "--out", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert named in err
    assert "Traceback" not in err


@pytest.mark.parametrize("content", ["", "x = ["])
def test_brief_problems_name_brief_toml_not_the_evidence_file(tmp_path, content):
    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    if content:
        (tmp_path / "brief.toml").write_text(content)
    logo = LogoDir(tmp_path)
    with pytest.raises(pipeline.AuthoringNeeded) as caught:
        pipeline.review_brief(logo)
    assert caught.value.files == [logo.brief]
    assert str(caught.value).startswith("fix brief.toml:")


@pytest.mark.parametrize(
    ("key", "line"),
    [
        ("tone", 'tone = "abc"'),
        ("uses", "uses = 3"),
        ("name", "name = 5"),
        ("palette", "palette = 1"),
    ],
)
def test_brief_field_types_are_a_brief_error(tmp_path, key, line):
    from logo_maker.brief import BriefError, load

    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    path = LogoDir(tmp_path).brief
    lines = [row for row in path.read_text().splitlines() if not row.startswith(f"{key} =")]
    path.write_text("\n".join([*lines, line]) + "\n")
    with pytest.raises(BriefError, match=key):
        load(path)


@pytest.mark.parametrize("content", ["", "[]", "{}", '{"stages": 1}', "not json"])
def test_corrupt_run_record_is_a_runtime_error_naming_the_file(tmp_path, content):
    from logo_maker.runlog import RunLog

    path = tmp_path / "run.json"
    path.write_text(content)
    if content == "{}":
        RunLog(path)  # a partial record is completed, not rejected
        return
    with pytest.raises(RuntimeError, match=r"run\.json"):
        RunLog(path)


def test_authored_files_with_wrong_shapes_name_the_file(tmp_path):
    from logo_maker.ideate import load_metaphors
    from logo_maker.palette import normalize

    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    logo = LogoDir(tmp_path)
    logo.metaphors.write_text('metaphor = "x"\n')
    with pytest.raises(ValueError, match=r"metaphors\.toml"):
        load_metaphors(logo)
    with pytest.raises(ValueError, match="not a hex color"):
        normalize(5)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("body", ['palette = "x"\n', "[[palette]]\nprimary = 5\n"])
def test_proposals_with_wrong_shapes_ask_the_agent_to_rewrite_the_file(tmp_path, body):
    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    logo = LogoDir(tmp_path)
    logo.ideation.mkdir(parents=True, exist_ok=True)
    (logo.ideation / "proposals.toml").write_text(body)
    with pytest.raises(pipeline.AuthoringNeeded, match=r"proposals\.toml") as caught:
        pipeline._proposals(logo, "palette")
    assert caught.value.files == [logo.ideation / "proposals.toml"]


def test_empty_proposal_tables_ask_for_authoring_instead_of_crashing(tmp_path):
    from logo_maker.pipeline import AuthoringNeeded, _proposals

    logo = LogoDir(tmp_path / "logo")
    (logo.ideation / "proposals.toml").write_text("[[font]]\n")
    with pytest.raises(AuthoringNeeded, match="non-empty"):
        _proposals(logo, "font")


def test_eligibility_stop_names_the_recorded_reasons():
    from logo_maker.judging import _eligibility_detail

    detail = _eligibility_detail(
        {
            "a": {"status": "missing_evidence", "missing": ["candidate pixels missing"]},
            "b": {"status": "fail"},
        }
    )
    assert detail == "a: missing_evidence (candidate pixels missing); b: fail"


def test_visual_gate_stop_exposes_checks_and_both_orders(tmp_path):
    from logo_maker.judging import EligibilityStop

    logo = LogoDir(tmp_path)
    cid = "cup|extruded_solid|porcelain"
    orders = [["candidate", "reference"], ["reference", "candidate"]]
    record = {
        "status": "unsettled",
        "fit": {"appearance": "unsettled", "symbol": "pass"},
        "technical": {"aliasing_free": "unsettled"},
        "craft": [
            {
                "order": order,
                "status": "unsettled",
                "reference_sha256": "digest",
                "checks": {"surface_finish": "unsettled", "detail_finish": "pass"},
            }
            for order in orders
        ],
    }
    details = EligibilityStop("no eligible candidate", {cid: record}).authoring_details(
        logo, "final"
    )
    candidate = details["candidates"][cid]
    assert details["journal"] == str(logo.qa / "eligibility.jsonl")
    assert candidate["artifact"] == "concepts/cup--extruded-solid--porcelain/final.png"
    assert candidate["fit"] == {"appearance": "unsettled"}
    assert candidate["technical"] == {"aliasing_free": "unsettled"}
    assert [row["order"] for row in candidate["craft"]] == orders
    assert all(row["checks"] == {"surface_finish": "unsettled"} for row in candidate["craft"])


def test_mcp_authoring_stop_survives_a_damaged_state_file(tmp_path):
    (tmp_path / "brief.toml").write_text("")
    (tmp_path / "ideation").mkdir()
    (tmp_path / "ideation" / "shortlist.json").write_text("{bad")

    def needs_authoring(logo):
        raise pipeline.AuthoringNeeded("fix brief.toml: name is required", [logo.brief])

    result = anyio.run(mcp_server._stage, needs_authoring, "x", str(tmp_path))
    assert result["status"] == "authoring_needed"
    assert result["files"] == [str(tmp_path / "brief.toml")]
    assert "shortlist.json" in result["counts"]["unavailable"]


def test_os_errors_reach_the_agent_with_their_path(tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("")
    with pytest.raises(McpToolError, match="a-file"):
        anyio.run(mcp_server.logo_new, "x", "X", str(blocker))
    with pytest.raises(McpToolError, match="a-file"):
        anyio.run(mcp_server.logo_new, "x", "X", str(blocker / "logo"))
    with pytest.raises(McpToolError, match="too long"):
        anyio.run(mcp_server.logo_status, "a" * 5000, str(tmp_path / ("a" * 5000)))
    assert main(["new", "x", "--out", str(blocker)]) == 2
    assert capsys.readouterr().err.startswith("error: ")


def test_mcp_new_rejects_a_blank_out_and_names_a_blank_logo_from_its_slug(tmp_path):
    with pytest.raises(McpToolError, match="out must be a folder path"):
        anyio.run(mcp_server.logo_new, "x", "X", " ")
    anyio.run(mcp_server.logo_new, "repair-shop", "  ", str(tmp_path / "l"))
    assert 'name = "Repair Shop"' in (tmp_path / "l" / "brief.toml").read_text()


def test_invalid_brief_stops_export_as_authoring_work(tmp_path):
    (tmp_path / "brief.toml").write_text('name = "N"\n')
    result = anyio.run(mcp_server.logo_export, "x", str(tmp_path))
    assert result["status"] == "authoring_needed"
    assert result["files"] == [str(tmp_path / "brief.toml")]


def test_cli_new_handoff_quotes_the_absolute_output_target(tmp_path, capsys):
    import re
    import shlex

    out = tmp_path / "Logo & owner's files"
    assert main(["new", "sample", "--out", str(out)]) == 0
    commands = re.findall(r"`(logo-maker [^`]+)`", capsys.readouterr().out)
    assert [shlex.split(command) for command in commands] == [
        ["logo-maker", "brief", str(out.resolve())],
        ["logo-maker", "run", str(out.resolve())],
    ]
    assert main(shlex.split(commands[0])[1:]) == 3
    assert "AUTHORING NEEDED" in capsys.readouterr().err


def test_mcp_instructions_route_flat_work_and_resume_through_the_skill():
    instructions = mcp_server.server.instructions
    assert instructions is not None
    assert "flat asset recipe" in instructions
    assert "absolute logo_dir as target" in instructions
    assert "logo_status on the folder containing brief.toml" in instructions
    assert "logo_brief, logo_intake and logo_ideate" in instructions
    assert "publish only through logo_improve" in instructions
