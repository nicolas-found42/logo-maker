"""Host render boundary: failures preserve published work; outputs bind to inputs."""

import json
from pathlib import Path

import pytest
from PIL import Image

from logo_maker import render, scene
from logo_maker.sampling import Budget


def compiled(tmp_path):
    build = tmp_path / ".build"
    build.mkdir()
    source = build / "scene.json"
    source.write_text(
        json.dumps(
            {
                "quality": {
                    "name": "final",
                    "resolution": 4000,
                    "samples": 4096,
                    "adaptive": True,
                    "adaptive_threshold": 0.01,
                    "seed": 42,
                    "overrides": {},
                },
                "render": {"renderer": "cycles"},
                "sampling": {"diagnostic_bytes": 0},
            }
        )
    )
    return source


def test_failed_builder_keeps_prior_final_and_records_operational_failure(tmp_path, monkeypatch):
    source = compiled(tmp_path)
    prior = tmp_path / "final.png"
    prior.write_bytes(b"usable prior result")
    monkeypatch.setattr(scene, "compile", lambda *a, **k: source)
    monkeypatch.setattr(render, "machine_context", lambda *a: {"machine": "test"})

    def fail(*args, **kwargs):
        raise RuntimeError("GPU-only denoising unverified")

    monkeypatch.setattr(render, "_run_builder", fail)
    with pytest.raises(RuntimeError, match="GPU-only"):
        render.render(tmp_path, "final", budget=Budget())
    assert prior.read_bytes() == b"usable prior result"
    report = json.loads((tmp_path / ".build/final.sampling.json").read_text())
    assert report["outcomes"]["device"] == "failed"
    assert report["published"] is False


def test_budget_exhausted_before_compile_cannot_replace_output(tmp_path):
    clock = [0]
    budget = Budget(wall_seconds=1, clock=lambda: clock[0])
    clock[0] = 2
    with pytest.raises(RuntimeError, match="time_limit"):
        render.render(tmp_path, "final", budget=budget)


def test_successful_final_binds_delivered_hash_after_real_downsample(tmp_path, monkeypatch):
    from logo_maker.sampling_diagnostics import sha256

    source = compiled(tmp_path)
    monkeypatch.setattr(scene, "compile", lambda *a, **k: source)
    monkeypatch.setattr(render, "machine_context", lambda *a: {"machine": "test"})

    def builder(path, *args, budget):
        budget.begin_attempt()
        spec = json.loads(path.read_text())
        folder = Path(spec["output_dir"])
        Image.new("RGBA", (4000, 4000), (30, 40, 50, 255)).save(folder / "final.png")
        (folder / "final.execution.json").write_text(json.dumps({"status": "verified"}))

    monkeypatch.setattr(render, "_run_builder", builder)
    result = render.render(tmp_path, "final", budget=Budget())
    assert Image.open(result.png).size == (2000, 2000)
    assert result.sampling is not None
    report = json.loads(result.sampling.read_text())
    assert report["delivered_sha256"] == sha256(result.png)
    assert report["profile"]["state"] == "profile_unqualified"
    assert report["outcomes"]["noise"] == "unknown"
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    (tmp_path / "scene.py").write_text("# new authored source\n")
    assert not render.artifact_current(tmp_path, "final", check_machine=False)
    (tmp_path / "scene.py").unlink()
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    result.png.write_bytes(b"changed exported image")
    assert not render.artifact_current(tmp_path, "final", check_machine=False)


def test_generic_edge_failure_returns_scoped_refinement_without_changing_sampling(
    tmp_path, monkeypatch
):
    import tomlkit
    from test_refinement import Judge, construction, fake_gpu, job

    from logo_maker import pipeline

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    doc = tomlkit.parse((folder / "scene.toml").read_text())
    doc["render"]["max_samples"] = 128
    doc["render"]["adaptive_threshold"] = 0.02
    (folder / "scene.toml").write_text(tomlkit.dumps(doc))
    before = (folder / "scene.toml").read_bytes()
    with pytest.raises(pipeline.AuthoringNeeded, match="diagnosis") as stop:
        pipeline.qa_concept(logo, cid, Judge(0.1), pipeline.Brand({"primary": "#123456"}, {}))
    assert "clean_edges" in stop.value.details["failures"]
    assert stop.value.details["diagnosis"]["sampling_action"] == "none"
    assert (folder / "scene.toml").read_bytes() == before


def test_override_keeps_values_but_cannot_inherit_unmatched_profile_acceptance(
    tmp_path, monkeypatch
):
    source = compiled(tmp_path)
    data = json.loads(source.read_text())
    data["quality"].update(samples=1, overrides={"max_samples": 1})
    source.write_text(json.dumps(data))
    monkeypatch.setattr(scene, "compile", lambda *a, **k: source)
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    monkeypatch.setattr(
        render, "qualify_profile", lambda *a: ("qualified", "test reviewed profile")
    )
    profile = {
        "settings": {
            "samples": 4096,
            "adaptive_threshold": 0.01,
            "min_samples": 0,
            "adaptive": True,
        }
    }
    monkeypatch.setattr(
        render, "_load_optional", lambda folder, name: profile if name == "profile" else None
    )
    review = tmp_path / "owner-reviewed-case.json"
    review.write_text('{"sampling":"approved"}')
    profile["cases"] = [{"evidence": {"path": str(review)}}]
    data["sampling"]["profile"] = "profile"
    source.write_text(json.dumps(data))
    (tmp_path / "profile").write_text("test profile")

    def builder(path, *args, budget):
        budget.begin_attempt()
        spec = json.loads(path.read_text())
        assert spec["quality"]["samples"] == 1
        folder = Path(spec["output_dir"])
        Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(folder / "final.png")
        (folder / "final.execution.json").write_text('{"status":"verified"}')

    monkeypatch.setattr(render, "_run_builder", builder)
    result = render.render(tmp_path, "final", budget=Budget())
    assert result.sampling is not None
    report = json.loads(result.sampling.read_text())
    assert report["profile"]["state"] == "override_conflict"
    assert report["outcomes"]["sampling"] == "review_needed"
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    review.unlink()
    assert not render.artifact_current(tmp_path, "final", check_machine=False)


def test_deadline_during_publication_keeps_prior_final(tmp_path, monkeypatch):
    source = compiled(tmp_path)
    clock = [0.0]
    budget = Budget(wall_seconds=10, clock=lambda: clock[0])
    prior = tmp_path / "final.png"
    prior.write_bytes(b"approved prior image")
    monkeypatch.setattr(scene, "compile", lambda *a, **k: source)
    monkeypatch.setattr(render, "machine_context", lambda *a: {})

    def builder(path, *args, budget):
        budget.begin_attempt()
        spec = json.loads(path.read_text())
        folder = Path(spec["output_dir"])
        Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(folder / "final.png")
        (folder / "final.execution.json").write_text('{"status":"verified"}')

    monkeypatch.setattr(render, "_run_builder", builder)
    copy = render.shutil.copyfile

    def slow_copy(src, dst, *args, **kwargs):
        result = copy(src, dst, *args, **kwargs)
        clock[0] = 11
        return result

    monkeypatch.setattr(render.shutil, "copyfile", slow_copy)
    with pytest.raises(RuntimeError, match="time_limit"):
        render.render(tmp_path, "final", budget=budget)
    assert prior.read_bytes() == b"approved prior image"


def test_finalize_sampling_stop_names_evidence_and_preserves_existing_winner(tmp_path, monkeypatch):
    import shutil

    from test_refinement import Judge, construction, fake_gpu, job

    from logo_maker import pipeline, refinement
    from logo_maker.paths import REPO_ROOT

    logo, cid, folder = job(tmp_path)
    with logo.brief.open("a") as stream:
        stream.write('\n[palette]\nprimary="#123456"\n[fonts]\ndisplay="Manrope:wght=700"\n')
    construction(folder)
    pipeline.motifs(logo)
    shutil.copyfile(REPO_ROOT / "examples/chief-of-staff/reference-256.png", folder / "preview.png")
    (logo.ideation / "finalists.json").write_text(
        json.dumps({"ids": [cid], "binding": refinement.campaign_key(logo, [cid])})
    )
    prior = logo.ideation / "winner.json"
    prior.write_text('{"winner":"approved-prior"}')
    fake_gpu(
        monkeypatch,
        REPO_ROOT / "examples/chief-of-staff/reference-256.png",
        sampling_qualified=False,
    )
    with pytest.raises(pipeline.AuthoringNeeded, match="sampling qualification") as stop:
        pipeline.finalize(logo, client=Judge())
    assert folder / ".build/final.sampling.json" in stop.value.files
    assert prior.read_text() == '{"winner":"approved-prior"}'
