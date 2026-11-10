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
    from types import SimpleNamespace

    from logo_maker import checks, judging, pipeline
    from logo_maker.paths import LogoDir

    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Test")
    logo.brief.write_text('name = "Test"\nsummary = "Test mark"\ntone = ["calm"]\n')
    folder = logo.concept("a|b|c")
    recipe = "[render]\nmax_samples = 128\nadaptive_threshold = 0.02\n"
    (folder / "scene.toml").write_text(recipe)
    Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(folder / "final.png")
    monkeypatch.setattr(render, "artifact_current", lambda *a, **k: True)
    monkeypatch.setattr(
        judging, "qa_judgments", lambda *a: {"clean_edges": SimpleNamespace(status="fail", p=0.1)}
    )
    monkeypatch.setattr(checks, "alpha_report", lambda *a: {"veil": False})
    monkeypatch.setattr(checks, "margin_report", lambda *a: {"cut_off": False})
    monkeypatch.setattr(checks, "edge_report", lambda *a: {"aliased": True})
    monkeypatch.setattr(checks, "color_report", lambda *a: {})
    result = pipeline.qa_concept(logo, "a|b|c", object(), pipeline.Brand({}, {}))
    assert result["result"] == "refinement_needed"
    assert result["refinement"]["dimension"] == "edges_unknown_cause"
    assert (folder / "scene.toml").read_text() == recipe
    assert result["round"] == 1


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
