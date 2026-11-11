"""Real owned CPU workers: refinement IO cannot outlive the shared caller budget."""

import json
import time

import pytest

from logo_maker import refinement
from logo_maker.sampling import Budget, SamplingLimit


@pytest.mark.parametrize("phase", ["hash", "archive", "comparison"])
def test_refinement_blocking_io_is_owned_and_preserves_active_evidence(
    tmp_path, monkeypatch, phase
):
    from test_eligibility import finalize_logo
    from test_publication import inject_stall

    logo, cid = finalize_logo(tmp_path / "logo")
    folder = logo.concept(cid)
    record = refinement.read(folder / "render-state.json")["final"]
    state = (folder / "render-state.json").read_bytes()
    image = (folder / "final.png").read_bytes()
    history = list((logo.qa / "revisions").glob("*/[0-9]*/revision.json"))
    original = {p: p.read_bytes() for p in history}
    selector = (
        "motif.svg" if phase == "hash" else "render.png" if phase == "comparison" else "brief.toml"
    )
    marker = inject_stall(
        tmp_path, monkeypatch, "copyfile" if phase == "archive" else "read_bytes", selector
    )
    started = time.monotonic()

    def invoke():
        with refinement.owned_scope(Budget(wall_seconds=4)):
            if phase == "hash":
                refinement.source_hashes(logo, folder)
            elif phase == "archive":
                refinement._archive(
                    logo,
                    cid,
                    "final",
                    record["source_sha256"],
                    folder / "final.png",
                    folder / ".build/final.execution.json",
                    folder / ".build/final.sampling.json",
                    0,
                )
            else:
                refinement._comparison_inputs(logo, record, record, ["test", "local"])

    with pytest.raises(SamplingLimit, match="time_limit"):
        invoke()
    assert marker.exists(), "did not reach the selected IO operation in the child"
    assert time.monotonic() - started < 6
    assert (folder / "render-state.json").read_bytes() == state
    assert (folder / "final.png").read_bytes() == image
    assert {p: p.read_bytes() for p in history} == original
    assert list((logo.qa / "revisions").glob("*/[0-9]*/revision.json")) == history


def test_owned_refinement_transfers_structured_authoring_stop(tmp_path):
    from test_refinement import job

    logo, _, folder = job(tmp_path)
    with refinement.owned_scope(Budget(wall_seconds=8)):
        from logo_maker.pipeline import AuthoringNeeded

        with pytest.raises(AuthoringNeeded, match="construction") as stop:
            refinement.prepare(logo)
    assert stop.value.files == [folder / "construction.json"]


def test_frozen_requirements_and_plan_are_archived_with_creative_sources(tmp_path):
    from test_eligibility import finalize_logo

    logo, cid = finalize_logo(tmp_path)
    folder = logo.concept(cid)
    record = json.loads((folder / "render-state.json").read_text())["final"]
    evidence = logo.root / record["evidence"] / "sources"
    for name in (
        "ideation/requirements.json",
        "brief-evidence.toml",
        "concept/plan.toml",
        "concept/plan-review.json",
    ):
        assert name in record["source_sha256"]
        assert refinement.digest(evidence / name) == record["source_sha256"][name]
    assert any(name.startswith("requirements_source/") for name in record["source_sha256"])


def test_unpublished_archive_stages_never_enter_revision_history(tmp_path):
    from logo_maker.paths import LogoDir, concept_slug

    logo = LogoDir(tmp_path)
    cid = "test|paper|paper"
    root = logo.qa / "revisions" / concept_slug(cid)
    for name in ("0001-published-preview", ".archiving-interrupted", ".publishing-interrupted"):
        path = root / name / "revision.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"revision": name}))
    assert refinement.history(logo, cid) == [{"revision": "0001-published-preview"}]
