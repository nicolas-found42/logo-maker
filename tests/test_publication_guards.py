"""Changed approval inputs must recover prior selections and exports in the real worker."""

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from logo_maker import pipeline, refinement, render
from logo_maker.sampling import Budget, SamplingLimit


def edit_during_publication(tmp_path, monkeypatch, target, source, phase, mutation="inspection"):
    hooks = tmp_path / "guard-hooks"
    hooks.mkdir()
    marker = tmp_path / "changed-input"
    (hooks / "sitecustomize.py").write_text(
        "import json,pathlib\n"
        f"marker=pathlib.Path({str(marker)!r}); source=pathlib.Path({str(source)!r})\n"
        f"target={target!r}; phase={phase!r}; mutation={mutation!r}\n"
        "write=pathlib.Path.write_text; rename=pathlib.Path.rename\n"
        "def change():\n"
        " if marker.exists(): return\n"
        " write(marker,'reached')\n"
        " data=json.loads(source.read_text())\n"
        " if mutation=='inspection': data['observations']='changed during publication'\n"
        " elif mutation=='sampling': data['profile']['state']='profile_unqualified'\n"
        " else: data['winner']='changed by author'\n"
        " write(source,json.dumps(data))\n"
        "def staged(self,*args,**kwargs):\n"
        " if phase=='staging' and target!='exports' and self.name.startswith('.publishing-') and self.name.endswith(target): change()\n"
        " return write(self,*args,**kwargs)\n"
        "def moved(self,dest,*args,**kwargs):\n"
        " if phase=='staging' and target=='exports' and self.name.startswith('.export-pending-'): change()\n"
        " result=rename(self,dest,*args,**kwargs)\n"
        " if phase=='renamed' and self.name.startswith('.publishing-') and self.name.endswith(target): change()\n"
        " return result\n"
        "pathlib.Path.write_text=staged; pathlib.Path.rename=moved\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(hooks) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return marker


@pytest.mark.parametrize("phase", ["staging", "renamed"])
def test_final_publication_input_edit_restores_prior_winner_and_run(tmp_path, monkeypatch, phase):
    from test_eligibility import EligibilityClient, finalize_logo

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    result = pipeline.qa_concept(logo, cid, EligibilityClient(), pipeline.brand(logo))
    monkeypatch.setattr(pipeline, "qa_concept", lambda *a, **k: result)
    winner = logo.ideation / "winner.json"
    winner.write_text('{"winner":"approved prior"}')
    previous_run = logo.run_json.read_bytes()
    marker = edit_during_publication(
        tmp_path, monkeypatch, "winner.json", logo.concept(cid) / "inspection-final.json", phase
    )
    with pytest.raises(pipeline.AuthoringNeeded, match="publication"):
        pipeline.finalize(logo, EligibilityClient(), budget=Budget(wall_seconds=30))
    assert marker.exists()
    assert winner.read_bytes() == b'{"winner":"approved prior"}'
    assert logo.run_json.read_bytes() == previous_run


def prepare_preview(logo, cid):
    from test_eligibility import attest

    folder = logo.concept(cid)
    build = folder / ".build"
    attest(folder, "preview")
    staged = refinement._archive(
        logo,
        cid,
        "preview",
        refinement.source_hashes(logo, folder),
        folder / "preview.png",
        build / "preview.execution.json",
        build / "preview.sampling.json",
        0,
    )
    for entry in staged["entries"]:
        if "source" in entry:
            Path(entry["source"]).rename(entry["target"])
        else:
            Path(entry["target"]).write_text(entry["text"])
    record = staged["record"]
    (folder / "inspection.json").write_text(
        json.dumps(
            {
                "revision": record["revision"],
                "observations": "Synthetic retained preview",
                "critiques": [],
            }
        )
    )
    from test_eligibility import EligibilityClient

    inspection = refinement.inspected(logo, cid, record)
    refinement.judge_revision(logo, cid, record, inspection, EligibilityClient())
    proof = {key: record[key] for key in ("revision", "image_sha256", "evidence")} | {
        "inspection_sha256": refinement.digest(folder / "inspection.json"),
        "judgment_sha256": refinement.digest(logo.root / record["evidence"] / "judgment.json"),
    }
    return {
        "selection": {"binding": refinement.campaign_key(logo, [cid]), "creative": {cid: proof}}
    }


@pytest.mark.parametrize("phase", ["staging", "renamed"])
def test_preview_publication_input_edit_restores_prior_finalists_and_run(
    tmp_path, monkeypatch, phase
):
    from test_eligibility import EligibilityClient, finalize_logo

    from logo_maker import judging
    from logo_maker.brief import load
    from logo_maker.eligibility import assess

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    completed_refine = prepare_preview(logo, cid)
    proof = assess(
        logo,
        load(logo.brief),
        cid,
        logo.concept(cid) / "preview.png",
        EligibilityClient(),
        stage="preview",
    )
    assert proof["status"] == "pass"
    monkeypatch.setattr(refinement, "prepare", lambda *a: [cid])
    monkeypatch.setattr(pipeline, "refine", lambda *a, **k: completed_refine)
    monkeypatch.setattr(
        judging,
        "screen_previews_record",
        lambda *a, **k: {"ids": [cid], "eligibility": {cid: proof}},
    )
    finalists = logo.ideation / "finalists.json"
    finalists.write_text('{"ids":["approved prior"]}')
    previous_run = logo.run_json.read_bytes()
    marker = edit_during_publication(
        tmp_path, monkeypatch, "finalists.json", logo.concept(cid) / "inspection.json", phase
    )
    with pytest.raises(pipeline.AuthoringNeeded, match="publication"):
        pipeline.preview(logo, EligibilityClient(), budget=Budget(wall_seconds=30))
    assert marker.exists()
    assert finalists.read_bytes() == b'{"ids":["approved prior"]}'
    assert logo.run_json.read_bytes() == previous_run


@pytest.mark.parametrize("phase", ["staging", "renamed"])
@pytest.mark.parametrize("mutation", ["inspection", "sampling", "winner"])
def test_export_publication_input_edit_restores_prior_exports_and_run(
    tmp_path, monkeypatch, phase, mutation
):
    from test_eligibility import EligibilityClient, finalize_logo

    from logo_maker import owned_process
    from logo_maker.refinement import digest

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    pipeline.finalize(logo, EligibilityClient(), budget=Budget(wall_seconds=30))
    original = owned_process.run

    def synthetic_export(*args, **kwargs):
        if kwargs.get("label") != "export":
            return original(*args, **kwargs)
        payload = json.loads(kwargs["input_text"])
        folder = Path(payload["out_dir"])
        folder.mkdir()
        image = folder / "hero-transparent.png"
        image.write_bytes(b"synthetic new export")
        record = {"files": {"hero": {"path": image.name, "sha256": digest(image)}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(record), stderr="")

    monkeypatch.setattr(owned_process, "run", synthetic_export)
    prior = logo.exports / "approved.txt"
    prior.write_bytes(b"approved prior exports")
    previous_run = logo.run_json.read_bytes()
    folder = logo.concept(cid)
    source = {
        "inspection": folder / "inspection-final.json",
        "sampling": folder / ".build/final.sampling.json",
        "winner": logo.ideation / "winner.json",
    }[mutation]
    marker = edit_during_publication(tmp_path, monkeypatch, "exports", source, phase, mutation)
    with pytest.raises(pipeline.AuthoringNeeded, match="publication"):
        pipeline.export(logo, budget=Budget(wall_seconds=30))
    assert marker.exists()
    assert prior.read_bytes() == b"approved prior exports"
    assert {p.name for p in logo.exports.iterdir()} == {"approved.txt"}
    assert logo.run_json.read_bytes() == previous_run


def test_publication_guard_read_uses_same_deadline_and_recovers(tmp_path, monkeypatch):
    from test_publication import inject_stall

    from logo_maker.publication import publish
    from logo_maker.refinement import digest

    target = tmp_path / "prior.txt"
    target.write_text("approved prior")
    sampling = tmp_path / "guard-sampling.json"
    sampling.write_text(
        '{"profile":{"state":"qualified"},"outcomes":{"sampling":"profile_baseline"}}'
    )
    expected = digest(sampling)
    marker = inject_stall(tmp_path, monkeypatch, "read_bytes", sampling.name)
    started = time.monotonic()
    with pytest.raises(SamplingLimit, match="time_limit"):
        publish(
            [{"target": str(target), "text": "next"}],
            tmp_path / "journal.json",
            Budget(wall_seconds=5),
            [],
            preconditions=[
                {
                    "operation": "export_guard",
                    "sampling_path": str(sampling),
                    "sampling_sha256": expected,
                    "eligibility": None,
                }
            ],
        )
    assert marker.exists()
    assert time.monotonic() - started < 10
    assert target.read_text() == "approved prior"


def test_preview_never_rebinds_edited_inspection_after_refinement(tmp_path, monkeypatch):
    from test_eligibility import EligibilityClient, finalize_logo

    from logo_maker import judging
    from logo_maker.brief import load
    from logo_maker.eligibility import assess

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    completed = prepare_preview(logo, cid)
    craft = assess(
        logo,
        load(logo.brief),
        cid,
        logo.concept(cid) / "preview.png",
        EligibilityClient(),
        stage="preview",
    )
    assert craft["status"] == "pass"
    monkeypatch.setattr(refinement, "prepare", lambda *a: [cid])

    def edited_after_refine(*args, **kwargs):
        path = logo.concept(cid) / "inspection.json"
        data = json.loads(path.read_text())
        data["critiques"] = [
            {
                "kind": "preference",
                "dimension": "finish",
                "artifact": "preview.png",
                "evidence": "New direction",
                "action": "Review",
                "comparison": "Compare",
                "resolved": False,
            }
        ]
        path.write_text(json.dumps(data))
        return completed

    monkeypatch.setattr(pipeline, "refine", edited_after_refine)
    monkeypatch.setattr(
        judging,
        "screen_previews_record",
        lambda *a, **k: {"ids": [cid], "eligibility": {cid: craft}},
    )
    finalists = logo.ideation / "finalists.json"
    finalists.write_text('{"ids":["approved prior"]}')
    previous_run = logo.run_json.read_bytes()
    with pytest.raises(pipeline.AuthoringNeeded, match="stale preview"):
        pipeline.preview(logo, EligibilityClient(), budget=Budget(wall_seconds=30))
    assert finalists.read_bytes() == b'{"ids":["approved prior"]}'
    assert logo.run_json.read_bytes() == previous_run
