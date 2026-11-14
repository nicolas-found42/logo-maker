"""Authored and tool-written files: malformed input fails with a named, actionable error."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from logo_maker import brief as brief_mod
from logo_maker import export, refinement, runlog
from logo_maker.fonts import FontSpecError, _pick_file, parse_spec
from logo_maker.imageops import pad_square
from logo_maker.paths import LogoDir
from logo_maker.pipeline import AuthoringNeeded


@pytest.mark.parametrize("name", ['Acme "Labs"', "C:\\tools", "Café ☕", "a\\b"])
def test_new_brief_round_trips_any_printable_name(tmp_path, name):
    path = tmp_path / "brief.toml"
    brief_mod.write_template(path, name)
    text = path.read_text().replace('summary = ""', 'summary = "S"', 1)
    path.write_text(text.replace("tone = []", 'tone = ["calm"]', 1))
    assert brief_mod.load(path).name == name


@pytest.mark.parametrize("name", ["a\nb", "a\x00b", "tab\there"])
def test_new_brief_rejects_control_characters_before_writing(tmp_path, name):
    path = tmp_path / "logo" / "brief.toml"
    with pytest.raises(brief_mod.BriefError, match="control character"):
        brief_mod.write_template(path, name)
    assert not path.exists()


@pytest.mark.parametrize(
    ("extra", "match"),
    [
        ('palette = { primary = "#abcdef\\n" }', "not #RRGGBB"),
        ("", "tone entries must not be blank"),
        ('[[references]]\npath = "a\\u0000b"\nuse = "craft"', "must name a file"),
        ('[[references]]\npath = ""\nuse = "craft"', "must name a file"),
    ],
)
def test_brief_rejects_blank_or_malformed_values(tmp_path, extra, match):
    tone = '[" "]' if "tone" in match else '["calm"]'
    path = tmp_path / "brief.toml"
    path.write_text(f'name = "N"\nsummary = "S"\ntone = {tone}\n{extra}\n')
    with pytest.raises(brief_mod.BriefError, match=match):
        brief_mod.load(path)


def test_brief_that_is_not_utf8_is_a_brief_error(tmp_path):
    path = tmp_path / "brief.toml"
    path.write_bytes(b'name = "\xff"\n')
    with pytest.raises(brief_mod.BriefError, match="UTF-8"):
        brief_mod.load(path)


def test_unreadable_brief_path_is_a_brief_error(tmp_path):
    with pytest.raises(brief_mod.BriefError, match="cannot read"):
        brief_mod.load(tmp_path)


@pytest.mark.parametrize("name", ["Cafe\udcff", "x\ud800y"])
def test_name_that_is_not_unicode_text_writes_nothing(tmp_path, name):
    path = tmp_path / "logo" / "brief.toml"
    with pytest.raises(brief_mod.BriefError, match="not valid Unicode"):
        brief_mod.write_template(path, name)
    assert not path.parent.exists()
    brief_mod.write_template(path, "Retry")


def test_runlog_does_not_resurrect_state_after_its_file_is_removed(tmp_path):
    path = tmp_path / "logo" / "run.json"
    path.parent.mkdir()
    runlog.runlog(path).stage("ideate", "done")
    shutil.rmtree(path.parent)
    path.parent.mkdir()
    fresh = runlog.runlog(path)
    assert fresh.stage_status("ideate") is None
    fresh.stage("new", "done")
    assert "ideate" not in json.loads(path.read_text())["stages"]


@pytest.mark.parametrize(
    "data",
    [
        {"stages": {"preview": "done"}},
        {"stages": {"preview": None}},
        {"stages": {"preview": {"status": 1}}},
        {"jev": {"requests": None}},
        {"jev": {"reported_cost_usd": 0.0}},  # telemetry without its other subtotals
        {"jev": {"request_usage": []}},
        {"seeds": {"motif": "x"}},
        {"seeds": {"motif": 1.5}},
    ],
)
def test_runlog_rejects_malformed_inner_entries(tmp_path, data):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match="not a valid run record"):
        runlog.RunLog(path)


def test_run_record_with_unknown_jev_totals_reloads(tmp_path):
    path = tmp_path / "run.json"
    runlog.RunLog(path).jev_usage({"input_tokens": 7})  # cost and output telemetry missing
    reloaded = runlog.RunLog(path)
    assert reloaded.data["jev"]["cost_usd"] is None
    assert reloaded.data["jev"]["reported_input_tokens"] == 7


def _concept(tmp_path) -> Path:
    folder = tmp_path / "concept"
    folder.mkdir()
    return folder


@pytest.mark.parametrize("content", ["[]", "null", '"s"'])
def test_construction_that_is_not_an_object_asks_for_authoring(tmp_path, content):
    folder = _concept(tmp_path)
    (folder / "construction.json").write_text(content)
    with pytest.raises(AuthoringNeeded, match="construction"):
        refinement.construction(folder)
    assert "concept/construction.json" in refinement.concept_sources(folder)


@pytest.mark.parametrize(
    ("content", "match"),
    [(b'{"current_description": ', "not valid JSON"), (b'{"a": "\xff"}', "not valid UTF-8")],
)
def test_unreadable_concept_json_names_its_file(tmp_path, content, match):
    folder = _concept(tmp_path)
    (folder / "construction.json").write_bytes(content)
    with pytest.raises(ValueError, match=rf"construction\.json: {match}"):
        refinement.construction(folder)


def test_non_string_dependencies_are_skipped_by_the_inventory(tmp_path):
    folder = _concept(tmp_path)
    (folder / "construction.json").write_text(json.dumps({"dependencies": [5, None]}))
    assert set(refinement.concept_sources(folder)) == {"concept/construction.json"}


@pytest.mark.parametrize("content", [b"[]", b"null", b'{"revision": '])
def test_unreadable_inspection_asks_for_authoring(tmp_path, content):
    logo = LogoDir(tmp_path / "logo")
    cid = "m|t|mat"
    logo.concept(cid).mkdir(parents=True, exist_ok=True)
    (logo.concept(cid) / "inspection.json").write_bytes(content)
    record = {"quality": "preview", "revision": "0001-x-preview", "image": "x.png"}
    with pytest.raises(AuthoringNeeded, match="inspection"):
        refinement.inspection_snapshot(logo, cid, record)


def test_failed_archive_removes_its_staging_copy(tmp_path, monkeypatch):
    from test_eligibility import attest, finalize_logo

    logo, cid = finalize_logo(tmp_path / "logo")
    folder = logo.concept(cid)
    attest(folder, "preview")

    def boom(*args, dest, **kwargs):
        (dest / "partial").write_text("copied")
        raise OSError("disk full")

    monkeypatch.setattr(refinement, "_fill_archive", boom)
    build = folder / ".build"
    with pytest.raises(OSError, match="disk full"):
        refinement._archive(
            logo,
            cid,
            "preview",
            refinement.source_hashes(logo, folder),
            folder / "preview.png",
            build / "preview.execution.json",
            build / "preview.sampling.json",
            0,
        )
    revisions = logo.qa / "revisions"
    assert not list(revisions.rglob(".archiving-*"))


def test_italic_request_without_an_italic_file_is_an_error():
    files = [{"name": "Example", "style": "normal", "filename": "Example[wght].ttf"}]
    with pytest.raises(FontSpecError, match="no italic"):
        _pick_file(files, parse_spec("Example:ital=1"))


def _mark(path: Path, size=200, box=(80, 80, 120, 120)) -> Path:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.paste((10, 20, 30, 255), box)
    image.save(path)
    return path


def test_paper_shadow_is_offset_once(tmp_path):
    hero = _mark(tmp_path / "hero.png")  # opaque mark at y 80..119, shadow offset 18 px down
    out = export._hero_on_paper(hero, tmp_path, "#FFFFFF", shadow=True)
    with Image.open(out) as paper:
        gray = paper.convert("L")
        column = [int(gray.getpixel((100, y)) or 0) for y in range(120, 200)]  # ty: ignore[invalid-argument-type]
    # The silhouette shifted 18 px is centred at y 117, so the darkest uncovered row is the first
    # one below the mark; a second 18 px shift would move the darkest row to about y 135.
    assert min(column) < 255
    assert column.index(min(column)) == 0


def test_avatar_rejects_a_speck_instead_of_resizing_without_bound(tmp_path):
    hero = _mark(tmp_path / "hero.png", size=2000, box=(1000, 1000, 1001, 1001))
    with pytest.raises(export.ExportError, match="too small"):
        export._avatar(hero, tmp_path, "#FFFFFF")


def test_missing_final_render_is_an_export_error(tmp_path):
    folder = tmp_path / "concept"
    folder.mkdir()
    with pytest.raises(export.ExportError, match="no final render"):
        export._export_all(
            folder, tmp_path / "out", name="N", palette={}, motif_svg=folder / "motif.svg"
        )


def test_pad_square_rejects_a_non_positive_size(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        pad_square(_mark(tmp_path / "m.png"), tmp_path / "o.png", 0)


def _reviewed_logo(tmp_path):
    from test_brief_workflow import business_brief, evidence_record

    logo = business_brief(tmp_path)
    evidence_record(logo)
    return logo


def test_missing_craft_reference_is_reported_as_a_brief_problem(tmp_path):
    from test_brief_workflow import BriefJudge

    from logo_maker.pipeline import review_brief

    logo = _reviewed_logo(tmp_path)
    logo.brief.write_text(
        logo.brief.read_text() + '[[references]]\npath = "inputs/none.png"\nuse = "craft"\n'
    )
    with pytest.raises(AuthoringNeeded, match=r"fix brief\.toml: .*none\.png") as raised:
        review_brief(logo, BriefJudge())
    assert logo.brief in raised.value.files


def test_missing_evidence_field_names_its_row(tmp_path):
    from test_brief_workflow import BriefJudge

    from logo_maker.pipeline import review_brief

    logo = _reviewed_logo(tmp_path)
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text().replace('excerpt = "neighbors mend their household objects"\n', "")
    )
    with pytest.raises(AuthoringNeeded, match="source project: missing 'excerpt'"):
        review_brief(logo, BriefJudge())


def test_primitive_is_found_in_any_gopath_entry_and_gobin(tmp_path, monkeypatch):
    import subprocess

    from logo_maker import twod_tools

    second = tmp_path / "second" / "bin"
    second.mkdir(parents=True)
    binary = second / "primitive"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    gopath = f"{tmp_path / 'first'}:{tmp_path / 'second'}"
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, f"\n{gopath}\n", "")
    )
    assert twod_tools.primitive_path() == str(binary)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, f"{second}\n\n", "")
    )
    assert twod_tools.primitive_path() == str(binary)


def test_copy_install_replaces_a_leftover_link_without_touching_the_checkout(tmp_path):
    import scripts.install as install

    destination = tmp_path / "logo-maker"
    destination.symlink_to(install.ROOT / "skills" / "logo-maker")
    install.copy_skill(destination)
    assert not destination.is_symlink()
    assert (destination / "references" / "automatic-sampling.md").is_file()
    assert not (
        install.ROOT / "skills" / "logo-maker" / "references" / "automatic-sampling.md"
    ).exists()


def test_interrupted_hdri_download_leaves_no_cached_file(tmp_path, monkeypatch):
    import contextlib

    import httpx

    from logo_maker import hdri

    class Stream:
        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"#?RADIANCE partial"
            raise KeyboardInterrupt

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: contextlib.nullcontext(Stream()))
    dest = tmp_path / "studio.hdr"
    with pytest.raises(KeyboardInterrupt):
        hdri._download("https://example.invalid/studio.hdr", dest, 5)
    assert not dest.exists()


class _NoJudge:
    def ask(self, state, questions, *, label) -> dict[str, dict]:
        raise AssertionError("judged an input that should have been rejected first")

    def ask_many(self, jobs) -> list[dict[str, dict]]:
        raise AssertionError("judged an input that should have been rejected first")


def test_palette_proposal_with_an_unknown_role_is_rejected_before_judging(tmp_path):
    from logo_maker.brief import Brief
    from logo_maker.intake import pick_palette

    logo = LogoDir(tmp_path / "logo")
    proposals = [
        {"background": "#FFFFFF", "primray": "#101010"},
        {"background": "#000000", "ink": "#FFFFFF", "primary": "#FF0000"},
    ]
    with pytest.raises(ValueError, match="palette proposal 0: role 'primray' is not one of"):
        pick_palette(logo, Brief(name="N", summary="S", tone=("calm",)), proposals, _NoJudge())


def test_style_reference_that_is_not_an_image_names_the_reference(tmp_path):
    from logo_maker.brief import Brief, Reference
    from logo_maker.intake import judge_references

    fake = tmp_path / "not-an-image.png"
    fake.write_text("this is not a PNG")
    brief = Brief(name="N", summary="S", tone=("calm",), references=(Reference(fake, "style"),))
    with pytest.raises(
        brief_mod.BriefError, match=r"not-an-image\.png \(use=style\) is not a readable"
    ):
        judge_references(LogoDir(tmp_path / "logo"), brief, _NoJudge())


@pytest.mark.parametrize(
    "content",
    [
        '{"palettee": {}}',
        "[]",
        '{"palette": ["#FFFFFF"]}',
        '{"palette": ',
        "\udcff",
        '{"palette": {"primary": "red", "background": "#FFFFFF"}}',
    ],
)
def test_malformed_intake_pick_names_the_file_and_the_fix(tmp_path, content):
    from logo_maker.pipeline import brand

    logo = LogoDir(tmp_path / "logo")
    logo.root.mkdir(parents=True, exist_ok=True)
    logo.brief.write_text(
        'name = "N"\nsummary = "S"\ntone = ["calm"]\n[fonts]\ndisplay = "Inter"\n'
    )
    logo.ideation.mkdir(parents=True, exist_ok=True)
    (logo.ideation / "palette.json").write_bytes(content.encode("utf-8", "surrogateescape"))
    with pytest.raises(RuntimeError, match=r"palette\.json: .*delete it and rerun"):
        brand(logo)


def test_cache_location_expands_home_and_relative_paths(tmp_path, monkeypatch):
    from logo_maker.paths import cache_dir

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGO_MAKER_CACHE", "~/cache")
    assert cache_dir("fonts") == tmp_path / "home" / "cache" / "fonts"
    monkeypatch.setenv("LOGO_MAKER_CACHE", "rel")
    assert cache_dir("fonts") == (tmp_path / "rel" / "fonts").resolve()
    assert not (tmp_path / "~").exists()


@pytest.mark.parametrize("configured", ["afile", "~nouserxyz-logo-maker/c"])
def test_unusable_cache_setting_names_the_variable(tmp_path, monkeypatch, configured):
    from logo_maker.paths import cache_dir

    (tmp_path / "afile").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGO_MAKER_CACHE", configured)
    with pytest.raises(RuntimeError, match=r"LOGO_MAKER_CACHE='.*' as the download cache"):
        cache_dir("fonts")


@pytest.mark.parametrize("receipt", [b"", b'{"sources": ', b"[]", b"null", b'{"sources": "x"}'])
def test_torn_or_wrong_motif_receipt_reruns_the_motif(tmp_path, receipt):
    from logo_maker.pipeline import prepare_motif

    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text(
        "from logo_maker.motif import Motif\nm = Motif()\n"
        "m.add('disc', Motif.circle(500, 500, 300), fill='#123456')\nm.save('.')\n"
    )
    prepare_motif(concept)
    (concept / ".motif-state.json").write_bytes(receipt)
    assert prepare_motif(concept) == concept / "motif.json"
    assert json.loads((concept / ".motif-state.json").read_text())["sources"]


def test_scene_type_errors_name_the_types_in_words():
    from logo_maker.scene import SceneError, _field

    with pytest.raises(SceneError, match=r"roughness=True must be int or float$"):
        _field("material", {"roughness": True}, "roughness", (int, float))


@pytest.mark.parametrize(
    "body",
    [
        [],
        "s",
        None,
        {"revision": "0001-x-preview", "cause": ["design"], "evidence": [{}]},
        {"revision": "0001-x-preview", "cause": "design", "evidence": [{"artifact": 5}]},
        {"revision": "0001-x-preview", "cause": "design", "evidence": [{"artifact": None}]},
    ],
)
def test_wrong_shaped_diagnosis_is_reported_as_invalid(tmp_path, body):
    logo = LogoDir(tmp_path / "logo")
    cid = "m|t|mat"
    (logo.concept(cid) / "diagnosis.json").write_text(json.dumps(body))
    record = {"revision": "0001-x-preview", "evidence": "qa/revisions/m--t--mat/0001"}
    result = refinement.diagnosis(logo, cid, record, {"cause": "unknown"})
    assert result["cause"] == "unknown"
    assert "invalid_diagnosis" in result


def test_critique_with_a_non_string_kind_asks_for_authoring(tmp_path):
    logo = LogoDir(tmp_path / "logo")
    cid = "m|t|mat"
    data = {"revision": "0001-x-preview", "observations": "o", "critiques": [{"kind": ["a"]}]}
    (logo.concept(cid) / "inspection.json").write_text(json.dumps(data))
    record = {
        "quality": "preview",
        "revision": "0001-x-preview",
        "image": "x.png",
        "evidence": "qa/revisions/m--t--mat/0001",
    }
    with pytest.raises(AuthoringNeeded, match="resolve critique"):
        refinement.inspection_snapshot(logo, cid, record)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"answers": {"critique_resolved": {}}},
        {"answers": {"critique_resolved": {"noul": "x"}}},
        [],
    ],
)
def test_damaged_comparison_does_not_count_as_resolved(tmp_path, body):
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(body))
    assert refinement.comparison_complete(path) is False


def test_host_worker_errors_reach_the_caller_as_one_message(tmp_path):
    from logo_maker import host
    from logo_maker.proc import ToolError
    from logo_maker.sampling import Budget

    with pytest.raises(ToolError) as caught:
        host.run({"operation": "nope"}, Budget(), [])
    assert str(caught.value) == "host nope failed: ValueError: unknown host operation 'nope'"


def _worker_failure(message: str) -> str:
    import subprocess
    import sys

    from logo_maker.host import failure

    code = (
        "import json, sys\nfrom logo_maker.host import serve\n"
        "def work(payload):\n    raise ValueError(payload['message'])\nserve(work)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"message": message}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    return failure(proc.stderr)


@pytest.mark.parametrize(
    "message",
    [
        "bad name: logo-maker worker error: pwned",
        "ends with the marker logo-maker worker error: ",
        'two lines\nlogo-maker worker error: "fake"',
    ],
)
def test_worker_failure_is_the_exact_message_whatever_it_contains(message):
    assert _worker_failure(message) == f"ValueError: {message}"


def test_long_worker_failure_keeps_the_tool_and_the_cause():
    from logo_maker.host import MESSAGE_LIMIT

    message = "blender scene.py failed (exit 1): " + "x" * 5000 + "\nBlenderError: missing HDRI"
    reported = _worker_failure(message)
    assert len(reported) == MESSAGE_LIMIT
    assert reported.startswith("ValueError: blender scene.py failed (exit 1): ")
    assert reported.endswith("BlenderError: missing HDRI")


@pytest.mark.parametrize("record", [b"[]", b'"s"', b'{"context": 5}'])
def test_wrong_shaped_sampling_record_reads_as_stale(tmp_path, record):
    from logo_maker import render
    from logo_maker.proc import ToolError

    (tmp_path / ".build").mkdir()
    (tmp_path / ".build" / "preview.sampling.json").write_bytes(record)
    assert render._artifact_current_local(tmp_path, "preview") is False
    with pytest.raises(ToolError, match="stale render provenance"):
        render.verify_execution(tmp_path, "preview")


def test_torn_sampling_record_names_the_file(tmp_path):
    from logo_maker import render
    from logo_maker.proc import ToolError

    (tmp_path / ".build").mkdir()
    (tmp_path / ".build" / "preview.sampling.json").write_text("{")
    with pytest.raises(ToolError, match=r"preview\.sampling\.json"):
        render.verify_execution(tmp_path, "preview")


def test_profile_preflight_timeout_is_a_budget_limit(monkeypatch):
    import subprocess

    from logo_maker import render
    from logo_maker.sampling import Budget, SamplingLimit

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(render.subprocess, "run", slow)
    with pytest.raises(SamplingLimit, match="time_limit"):
        render.machine_context(Budget(wall_seconds=5))


class _CountingJudge:
    model, url = "stub", None

    def __init__(self):
        self.asked = 0

    def ask(self, state, questions, *, label):
        self.asked += 1
        return {name: {"noul": 0.9, "reason": "r"} for name in questions}


def _revision_logo(tmp_path):
    from logo_maker import pipeline

    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Commons")
    logo.brief.write_text('name = "Commons"\nsummary = "Exchange skills"\ntone = ["welcoming"]\n')
    cid = "exchange|paper|paper"
    logo.concept(cid).mkdir(parents=True, exist_ok=True)

    def record(n: int) -> dict:
        folder = logo.qa / "revisions" / "exchange--paper--paper" / f"{n:04d}-r-preview"
        folder.mkdir(parents=True)
        for name in ("preview.png", "motif-sizes.png"):
            Image.new("RGB", (8, 8), "red").save(folder / name)
        image = folder / "preview.png"
        return {
            "revision": folder.name,
            "quality": "preview",
            "concept": cid,
            "image": str(image.relative_to(logo.root)),
            "image_sha256": refinement.digest(image),
            "evidence": str(folder.relative_to(logo.root)),
            "source_sha256": {},
            "construction": {},
        }

    return logo, cid, record


@pytest.mark.parametrize("cached", ["[]", '"x"', "null", "{binding}", "{empty-answer}"])
def test_wrong_shaped_cached_judgment_is_judged_again(tmp_path, cached):
    logo, cid, record = _revision_logo(tmp_path)
    first = record(1)
    inspection = {"revision": first["revision"], "observations": "o", "critiques": []}
    binding = refinement._judge_inputs(logo, first, inspection, ["stub", None])["binding"]
    content = {
        "{binding}": json.dumps({"binding": binding}),
        "{empty-answer}": json.dumps({"binding": binding, "answers": {"craftsmanship": {}}}),
    }.get(cached, cached)
    path = logo.root / first["evidence"] / "judgment.json"
    path.write_text(content)
    judge = _CountingJudge()
    answers = refinement.judge_revision(logo, cid, first, inspection, judge)
    assert judge.asked == 1
    assert json.loads(path.read_text())["answers"] == answers


@pytest.mark.parametrize(("rows", "reused"), [("[1]", False), ('[{"a": 1}]', False), ("{}", None)])
def test_comparison_rows_are_checked_before_reuse(tmp_path, rows, reused):
    logo, _cid, record = _revision_logo(tmp_path)
    before, after = record(1), record(2)
    (logo.qa / "comparisons.json").write_text(rows)
    judge = _CountingJudge()
    if reused is None:
        with pytest.raises(ValueError, match=r"comparisons\.json: expected a list"):
            refinement.compare(logo, before, after, judge)
        return
    result = refinement.compare(logo, before, after, judge)
    assert judge.asked == 1
    assert json.loads((logo.qa / "comparisons.json").read_text())[-1] == result


@pytest.mark.parametrize("state", ["[]", "null", '{"preview": "x"}', '{"preview": {"a": 1}}'])
def test_wrong_shaped_render_state_is_not_current(tmp_path, state):
    logo, cid, _record = _revision_logo(tmp_path)
    (logo.concept(cid) / "render-state.json").write_text(state)
    assert refinement.current(logo, cid) is None


@pytest.mark.parametrize("body", ["[1]", '"x"', "{}", '{"winner": ["a"]}', '{"winner": ""}'])
def test_wrong_shaped_winner_names_winner_json(tmp_path, body):
    from logo_maker import pipeline

    logo = LogoDir(tmp_path / "logo")
    (logo.ideation / "winner.json").write_text(body)
    with pytest.raises(RuntimeError, match=r"winner\.json: 'winner' must be a concept id"):
        pipeline.winner(logo)
    with pytest.raises(AuthoringNeeded, match="stale creative winner proof") as caught:
        refinement.verify_winner(logo, json.loads(body))
    assert caught.value.files == [logo.root / "ideation/winner.json"]


@pytest.mark.parametrize("body", ["[]", "{}", "{", '{"ids": [1]}', '{"ids": "x"}'])
def test_wrong_shaped_finalists_name_the_file(tmp_path, body):
    from logo_maker import host

    logo, _cid, _record = _revision_logo(tmp_path)
    (logo.ideation / "finalists.json").write_text(body)
    with pytest.raises(RuntimeError, match=r"finalists\.json: .*rerun `logo-maker preview"):
        host.main({"operation": "pipeline_inputs", "root": str(logo.root), "finalists": True})


def test_export_worker_failure_is_one_message():
    import subprocess
    import sys

    from logo_maker.host import failure

    proc = subprocess.run(
        [sys.executable, "-m", "logo_maker.export"],
        input="{}",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "Traceback" in proc.stderr  # kept for debugging
    message = failure(proc.stderr)
    assert message.startswith("TypeError: _export_all() missing")
    assert "Traceback" not in message


def _metaphor_rows(first: str) -> str:
    rest = "".join(f'[[metaphor]]\nid = "m{i}"\ntext = "t{i}"\n' for i in range(1, 8))
    return f"[[metaphor]]\n{first}\n" + rest


@pytest.mark.parametrize(
    ("content", "match"),
    [
        (b"x = [", "cannot read"),
        (b"\xff\xfe", "cannot read"),
        (_metaphor_rows('id = 7\ntext = "t"').encode(), "must be strings"),
        (_metaphor_rows('id = "m0"\ntext = ["a", "b"]').encode(), "must be strings"),
        (_metaphor_rows('id = "m0"\ntext = {a = 1}').encode(), "must be strings"),
        (None, "cannot read"),  # a directory where the file belongs
    ],
)
def test_unusable_metaphors_name_the_file(tmp_path, content, match):
    from logo_maker.ideate import load_metaphors

    logo = LogoDir(tmp_path / "logo")
    if content is None:
        logo.metaphors.mkdir(parents=True)
    else:
        logo.metaphors.write_bytes(content)
    with pytest.raises(ValueError, match=rf"metaphors\.toml: .*{match}"):
        load_metaphors(logo)


@pytest.mark.parametrize("content", [b"x = [", b"\xff\xfe"])
def test_unreadable_proposals_ask_for_a_rewrite(tmp_path, content):
    from logo_maker.pipeline import _proposals

    logo = LogoDir(tmp_path / "logo")
    (logo.ideation / "proposals.toml").write_bytes(content)
    with pytest.raises(AuthoringNeeded, match=r"proposals\.toml: cannot read") as caught:
        _proposals(logo, "palette")
    assert caught.value.files == [logo.ideation / "proposals.toml"]


def test_held_floor_without_a_recorded_winner_restores_that_state(tmp_path, monkeypatch):
    from logo_maker import judging, pipeline

    logo = LogoDir(tmp_path / "logo")
    logo.root.mkdir()
    logo.brief.write_text('name = "N"\nsummary = "S"\ntone = ["calm"]\n')
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(logo.exports / "hero-transparent.png")

    def challenger_round(target, _client):
        Image.new("RGBA", (64, 64), (0, 255, 0, 255)).save(target.concept("n|t|m") / "final.png")
        (target.ideation / "winner.json").write_text(json.dumps({"winner": "n|t|m"}))

    monkeypatch.setattr(pipeline, "_require_brief", lambda _logo: None)
    for stage in ("ideate", "preview", "finalize"):
        monkeypatch.setattr(pipeline, stage, challenger_round)
    monkeypatch.setattr(judging, "beats_floor", lambda *args: (False, "split"))
    assert pipeline.improve(logo, client=object())["result"] == "floor_held"
    assert not (logo.ideation / "winner.json").exists()
    (archive,) = (logo.root / "history").iterdir()
    assert json.loads((archive / "challenger-winner.json").read_text())["winner"] == "n|t|m"
    assert not (logo.root / "floor").exists()


@pytest.mark.parametrize(
    "content",
    [
        '{"id": "x"}',
        "[1]",
        "null",
        "{oops",
        '{"treatment": 5, "material": "x"}',
        '{"treatment": ["a"], "material": "x"}',
        '{"treatment": "no-such-treatment", "material": "no-such-material"}',
    ],
)
def test_damaged_concept_json_names_itself(tmp_path, content):
    from logo_maker import pipeline

    logo = LogoDir(tmp_path)
    folder = logo.concept("a|b|c")
    (folder / "concept.json").write_text(content)
    with pytest.raises(ValueError, match=r"concept\.json: "):
        pipeline._starter_scene(logo, "a|b|c", folder)
    assert not (folder / "scene.toml").exists()


def test_non_utf8_scene_names_the_scene(tmp_path):
    from logo_maker.scene import SceneError, load_scene

    path = tmp_path / "scene.toml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(SceneError, match=r"scene\.toml: cannot parse .*scene\.toml"):
        load_scene(path)


@pytest.mark.parametrize("ids", [["a|b|c", "a|b|c"], ["a|b|c", "A|b|C"]])
def test_shortlist_ids_sharing_a_folder_are_rejected(tmp_path, ids):
    from logo_maker.pipeline import concept_ids

    path = tmp_path / "shortlist.json"
    path.write_text(json.dumps({"ids": ids}))
    with pytest.raises(RuntimeError, match=r"shortlist\.json: 'ids' name the same concept folder"):
        concept_ids(path, "rerun")


def _font_logo(tmp_path: Path, monkeypatch, brief_fonts: str = "") -> LogoDir:
    from logo_maker import fonts, pipeline

    monkeypatch.setattr(pipeline, "review_brief", lambda logo, client=None: {})
    monkeypatch.setattr(fonts, "families", lambda category=None: ["Roboto", "Lora", "Inter"])
    root = tmp_path / "acme"
    (root / "ideation").mkdir(parents=True)
    (root / "brief.toml").write_text(
        'name = "Acme"\nsummary = "A thing."\ntone = ["calm"]\n'
        '[palette]\nprimary = "#000000"\nbackground = "#FFFFFF"\n' + brief_fonts
    )
    return LogoDir(root)


def test_malformed_proposed_font_is_not_picked_or_persisted(tmp_path, monkeypatch):
    from logo_maker import pipeline

    logo = _font_logo(tmp_path, monkeypatch)
    (logo.ideation / "proposals.toml").write_text(
        '[[fonts]]\ndisplay = "Roboto:wght=abc"\ntext = "Lora"\n'
        '[[fonts]]\ndisplay = "Inter"\ntext = "Lora"\n'
    )
    with pytest.raises(AuthoringNeeded, match="bad axis value") as raised:
        pipeline.intake(logo, client=object())
    assert raised.value.files == [logo.ideation / "proposals.toml"]
    assert not (logo.ideation / "fonts.json").exists()


def test_brief_font_that_cannot_resolve_names_brief_toml(tmp_path, monkeypatch):
    from logo_maker import fonts, pipeline

    logo = _font_logo(tmp_path, monkeypatch, '[fonts]\ndisplay = "Roboto:wght=2000"\n')

    def out_of_range(spec, on_asset=None):
        raise FontSpecError("Roboto wght=2000 outside [100, 900]")

    monkeypatch.setattr(fonts, "resolve", out_of_range)
    with pytest.raises(AuthoringNeeded, match=r"brief.toml \[fonts\].display") as raised:
        pipeline.intake(logo, client=object())
    assert raised.value.files == [logo.brief]


def test_brief_rejects_a_malformed_font_spec(tmp_path):
    path = tmp_path / "brief.toml"
    path.write_text('name = "Acme"\nsummary = "A thing."\n[fonts]\ndisplay = "Roboto:wght=abc"\n')
    with pytest.raises(brief_mod.BriefError, match=r"fonts\.display: bad axis value"):
        brief_mod.load(path)
