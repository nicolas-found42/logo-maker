"""Host render boundary: failures preserve published work; outputs bind to inputs."""

import json
from pathlib import Path

import pytest
from PIL import Image

from logo_maker import render
from logo_maker.sampling import Budget


def compiled(tmp_path):
    (tmp_path / "scene.toml").write_text(
        '[meta]\nconcept="test|plate|wax"\ntreatment="embossed_plate"\nseed=42\n'
        '[lighting]\nhdri="none"\n[sampling]\ndiagnostic_bytes=0\n'
        '[materials.surface]\npreset="wax"\n'
        '[[components]]\nkind="plate"\nmaterial="surface"\n'
    )
    (tmp_path / "motif.json").write_text('{"layers":[]}')


def test_failed_builder_keeps_prior_final_and_records_operational_failure(tmp_path, monkeypatch):
    compiled(tmp_path)
    prior = tmp_path / "final.png"
    prior.write_bytes(b"usable prior result")
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


@pytest.mark.parametrize("explicit_budget", [True, False])
def test_stalled_compilation_stops_at_wall_budget_and_keeps_prior_final(
    tmp_path, monkeypatch, explicit_budget
):
    """A blocked source read cannot keep the render caller waiting indefinitely."""
    import contextlib
    import os
    import threading
    import time

    from logo_maker.sampling import SamplingLimit

    if os.name != "posix":
        pytest.skip("bounded host workers target macOS/Linux")
    (tmp_path / "scene.toml").write_text(
        '[meta]\nconcept="test|plate|wax"\ntreatment="embossed_plate"\nseed=0\n'
        '[lighting]\nhdri="none"\n[sampling]\nwall_seconds=6\n'
        '[materials.surface]\npreset="wax"\n'
        '[[components]]\nkind="plate"\nmaterial="surface"\n'
    )
    source = tmp_path / "motif.json"
    os.mkfifo(source)
    prior = tmp_path / "final.png"
    prior.write_bytes(b"approved prior final")
    stop = threading.Event()

    def release_old_unbounded_call():
        descriptor = None
        try:
            while not stop.is_set():
                try:
                    descriptor = os.open(source, os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError:
                    stop.wait(0.01)
            if descriptor is not None and not stop.wait(10):
                with contextlib.suppress(BrokenPipeError):
                    os.write(descriptor, b'{"layers":[]}')
        finally:
            if descriptor is not None:
                os.close(descriptor)

    releaser = threading.Thread(target=release_old_unbounded_call, daemon=True)
    releaser.start()
    monkeypatch.setattr(
        render,
        "machine_context",
        lambda *args: pytest.fail("GPU preflight started after compilation exhausted the budget"),
    )
    started = time.monotonic()
    try:
        with pytest.raises(SamplingLimit, match="time_limit"):
            render.render(
                tmp_path, "final", budget=Budget(wall_seconds=6) if explicit_budget else None
            )
        assert time.monotonic() - started < 9, "compile overran the caller's wall budget"
        assert prior.read_bytes() == b"approved prior final"
        report = json.loads((tmp_path / ".build/final.sampling.json").read_text())
        assert report["published"] is False
        assert report["outcomes"]["time"] == "time_limit"
        assert not report["attempts"], "host timeout must not start a GPU attempt"
    finally:
        stop.set()
        releaser.join(timeout=1)


@pytest.mark.parametrize("control", ["profile", "diagnosis"])
def test_stalled_sampling_control_read_keeps_prior_final_within_deadline(
    tmp_path, monkeypatch, control
):
    import contextlib
    import os
    import threading
    import time

    from logo_maker.sampling import SamplingLimit

    if os.name != "posix":
        pytest.skip("bounded host workers target macOS/Linux")
    compiled(tmp_path)
    recipe = tmp_path / "scene.toml"
    recipe.write_text(
        recipe.read_text().replace(
            "diagnostic_bytes=0", f'diagnostic_bytes=0\n{control}="blocked-control.json"'
        )
    )
    source = tmp_path / "blocked-control.json"
    os.mkfifo(source)
    prior = tmp_path / "final.png"
    prior.write_bytes(b"approved prior final")
    stop = threading.Event()

    def release_old_unbounded_call():
        delayed = False
        while not stop.is_set():
            try:
                descriptor = os.open(source, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                stop.wait(0.01)
                continue
            try:
                if not delayed:
                    delayed = True
                    if stop.wait(10):
                        return
                with contextlib.suppress(BrokenPipeError):
                    os.write(descriptor, b"{}")
            finally:
                os.close(descriptor)
            stop.wait(0.01)

    releaser = threading.Thread(target=release_old_unbounded_call, daemon=True)
    releaser.start()
    monkeypatch.setattr(render, "machine_context", lambda *args: {"machine": "test"})
    monkeypatch.setattr(render, "_run_builder", lambda *a, **kw: pytest.fail("GPU attempt started"))
    started = time.monotonic()
    try:
        with pytest.raises(SamplingLimit, match="time_limit"):
            render.render(tmp_path, "final", budget=Budget(wall_seconds=6))
        assert time.monotonic() - started < 9, "sampling control read overran the wall budget"
        assert prior.read_bytes() == b"approved prior final"
        report = json.loads((tmp_path / ".build/final.sampling.json").read_text())
        assert report["outcomes"]["time"] == "time_limit"
        assert report["published"] is False
        assert not report["attempts"]
    finally:
        stop.set()
        releaser.join(timeout=1)


def test_successful_final_binds_delivered_hash_after_real_downsample(tmp_path, monkeypatch):
    from logo_maker.sampling_diagnostics import sha256

    compiled(tmp_path)
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
    assert not render.inspection_artifact_current(tmp_path, "final", budget=Budget())
    (tmp_path / "scene.py").unlink()
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    result.png.write_bytes(b"changed exported image")
    assert not render.artifact_current(tmp_path, "final", check_machine=False)


def test_stalled_image_hash_stops_at_wall_budget_and_keeps_prior_result(tmp_path, monkeypatch):
    import contextlib
    import os
    import threading
    import time

    from logo_maker.sampling import SamplingLimit

    if os.name != "posix":
        pytest.skip("bounded host workers target macOS/Linux")
    compiled(tmp_path)
    prior = tmp_path / "preview.png"
    prior.write_bytes(b"approved prior preview")
    stop = threading.Event()
    writers = []
    monkeypatch.setattr(render, "machine_context", lambda *a: {})

    def builder(path, *args, budget):
        budget.begin_attempt()
        folder = Path(json.loads(path.read_text())["output_dir"])
        image = folder / "preview.png"
        os.mkfifo(image)
        (folder / "preview.execution.json").write_text('{"status":"verified"}')

        def release_old_unbounded_call():
            descriptor = None
            try:
                while not stop.is_set():
                    try:
                        descriptor = os.open(image, os.O_WRONLY | os.O_NONBLOCK)
                        break
                    except OSError:
                        stop.wait(0.01)
                if descriptor is not None and not stop.wait(10):
                    with contextlib.suppress(BrokenPipeError):
                        os.write(descriptor, b"rendered preview bytes")
            finally:
                if descriptor is not None:
                    os.close(descriptor)

        writer = threading.Thread(target=release_old_unbounded_call, daemon=True)
        writer.start()
        writers.append(writer)

    monkeypatch.setattr(render, "_run_builder", builder)
    started = time.monotonic()
    try:
        with pytest.raises(SamplingLimit, match="time_limit"):
            render.render(tmp_path, "preview", budget=Budget(wall_seconds=6))
        assert time.monotonic() - started < 9, "image hash overran the wall budget"
        assert prior.read_bytes() == b"approved prior preview"
        report = json.loads((tmp_path / ".build/preview.sampling.json").read_text())
        assert report["published"] is False
        assert report["outcomes"]["time"] == "time_limit"
        assert report["budget"]["attempts"] == 1
        execution = Path(report["active_attempt"]["execution"])
        assert json.loads(execution.read_text())["status"] == "verified"
    finally:
        stop.set()
        for writer in writers:
            writer.join(timeout=1)


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
    compiled(tmp_path)
    recipe = tmp_path / "scene.toml"
    recipe.write_text(
        recipe.read_text().replace("diagnostic_bytes=0", 'diagnostic_bytes=0\nprofile="profile"')
        + "\n[render]\nmax_samples=1\n"
    )
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    (tmp_path / "profile").write_text("{}")
    review = tmp_path / "owner-reviewed-case.json"
    review.write_text('{"sampling":"approved synthetic test fixture"}')

    def builder(path, *args, budget):
        budget.begin_attempt()
        spec = json.loads(path.read_text())
        assert spec["quality"]["samples"] == 1
        folder = Path(spec["output_dir"])
        Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(folder / "final.png")
        (folder / "final.execution.json").write_text('{"status":"verified"}')

    monkeypatch.setattr(render, "_run_builder", builder)
    first = render.render(tmp_path, "final", budget=Budget())
    assert first.sampling is not None
    context = json.loads(first.sampling.read_text())["context"]
    from logo_maker.sampling_diagnostics import sha256

    evidence = {"path": str(review), "sha256": sha256(review)}
    profile = {
        "schema": 1,
        "context": {k: v for k, v in context.items() if k != "material_presets"},
        "material_presets": ["wax"],
        "owner_review": "approved",
        "coverage": ["matte", "metal", "glass", "dark", "typography", "alpha"],
        "cases": [
            {"role": role, "evidence": evidence} for role in ("positive", "degraded", "held_out")
        ],
        "job_costs": [{"baseline_seconds": 40, "candidate_seconds": 35}],
        "settings": {
            "samples": 4096,
            "adaptive_threshold": 0.01,
            "min_samples": 0,
            "adaptive": True,
        },
    }
    (tmp_path / "profile").write_text(json.dumps(profile))
    result = render.render(tmp_path, "final", budget=Budget())
    assert result.sampling is not None
    report = json.loads(result.sampling.read_text())
    assert report["profile"]["state"] == "override_conflict"
    assert report["outcomes"]["sampling"] == "review_needed"
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    review.unlink()
    assert not render.artifact_current(tmp_path, "final", check_machine=False)


def test_deadline_during_publication_keeps_prior_final(tmp_path, monkeypatch):
    compiled(tmp_path)
    clock = [0.0]
    budget = Budget(wall_seconds=10, clock=lambda: clock[0])
    prior = tmp_path / "final.png"
    prior.write_bytes(b"approved prior image")
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


def test_creative_sources_join_sampling_keys_without_diagnosis_self_dependency(tmp_path):
    import tomlkit
    from test_refinement import construction, job

    logo, _, folder = job(tmp_path)
    construction(folder)
    geometry = folder / "fold-geometry.json"
    geometry.write_text('{"crease":12}')
    diagnosis = folder / "sampling-diagnosis.json"
    diagnosis.write_text('{"kind":"sampling_noise","source_key":"bind-to-output"}')
    profile = folder / "machine-profile.json"
    profile.write_text('{"schema":1}')
    doc = tomlkit.parse((folder / "scene.toml").read_text())
    doc["sampling"] = {"diagnosis": str(diagnosis), "profile": str(profile)}
    (folder / "scene.toml").write_text(tomlkit.dumps(doc))
    deps = render.dependency_hashes(folder, {"sampling": dict(doc["sampling"])})
    assert str(geometry.resolve()) in deps
    assert str(logo.brief.resolve()) in deps
    assert str(diagnosis.resolve()) not in deps
    assert str(profile.resolve()) not in deps


def test_custom_bpy_cache_without_dependency_inventory_is_unknown(tmp_path, monkeypatch):
    compiled(tmp_path)
    monkeypatch.setattr(render, "machine_context", lambda *a: {})

    def builder(path, *args, budget):
        budget.begin_attempt()
        spec = json.loads(path.read_text())
        folder = Path(spec["output_dir"])
        Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(folder / "final.png")
        (folder / "final.execution.json").write_text('{"status":"verified"}')

    monkeypatch.setattr(render, "_run_builder", builder)
    result = render.render(tmp_path, "final", budget=Budget())
    assert result.sampling is not None
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    record = json.loads(result.sampling.read_text())
    record["context"]["custom_scene_sha256"] = "custom source can read unlisted files"
    result.sampling.write_text(json.dumps(record))
    assert not render.artifact_current(tmp_path, "final", check_machine=False)


@pytest.mark.render
def test_actual_machine_profile_identifies_final_image_processing_libraries():
    from importlib.metadata import version

    context = render.machine_context(Budget(wall_seconds=30))
    assert context["render_stack"]["OpenImageIO"] == version("OpenImageIO")
    assert context["render_stack"]["Pillow"] == version("Pillow")
    assert context["render_stack"]["numpy"] == version("numpy")


def test_stalled_cached_image_check_stops_at_its_shared_budget(tmp_path):
    import contextlib
    import hashlib
    import os
    import threading
    import time

    from logo_maker.sampling import SamplingLimit

    if os.name != "posix":
        pytest.skip("bounded host workers target macOS/Linux")
    build = tmp_path / ".build"
    build.mkdir()
    record = build / "final.sampling.json"
    record.write_text(
        json.dumps(
            {
                "published": True,
                "context": {},
                "dependencies": {},
                "delivered_sha256": hashlib.sha256(b"prior image bytes").hexdigest(),
            }
        )
    )
    prior_record = record.read_bytes()
    image = tmp_path / "final.png"
    os.mkfifo(image)
    stop = threading.Event()

    def release_old_unbounded_call():
        descriptor = None
        try:
            while not stop.is_set():
                try:
                    descriptor = os.open(image, os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError:
                    stop.wait(0.01)
            if descriptor is not None and not stop.wait(10):
                with contextlib.suppress(BrokenPipeError):
                    os.write(descriptor, b"prior image bytes")
        finally:
            if descriptor is not None:
                os.close(descriptor)

    releaser = threading.Thread(target=release_old_unbounded_call, daemon=True)
    releaser.start()
    started = time.monotonic()
    try:
        with pytest.raises(SamplingLimit, match="time_limit"):
            render.artifact_current(
                tmp_path, "final", check_machine=False, budget=Budget(wall_seconds=6)
            )
        assert time.monotonic() - started < 9
        assert record.read_bytes() == prior_record
    finally:
        stop.set()
        releaser.join(timeout=1)


def test_unbounded_asset_callback_is_an_explicit_budget_conflict(tmp_path, monkeypatch):
    from logo_maker.proc import ToolError

    compiled(tmp_path)
    prior = tmp_path / "final.png"
    prior.write_bytes(b"approved prior final")
    called = []
    monkeypatch.setattr(
        render, "machine_context", lambda *args: pytest.fail("callback conflict started GPU work")
    )
    with pytest.raises(ToolError, match="budget_conflict"):
        render.render(
            tmp_path, "final", on_asset=lambda *args: called.append(args), budget=Budget()
        )
    assert not called
    assert prior.read_bytes() == b"approved prior final"
    report = json.loads((tmp_path / ".build/final.sampling.json").read_text())
    assert report["published"] is False
    assert report["outcomes"]["time"] == "budget_conflict"
