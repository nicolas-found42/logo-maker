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
                if descriptor is not None and not stop.wait(35):
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
            render.render(tmp_path, "preview", budget=Budget(wall_seconds=20))
        assert time.monotonic() - started < 23, "image hash overran the wall budget"
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
    from types import SimpleNamespace

    from logo_maker import judging, pipeline
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
        judging,
        "qa_judgments",
        lambda *a, **kw: {"clean_edges": SimpleNamespace(status="fail", p=0.1)},
    )

    class ImmediateClient:
        def with_budget(self, budget):
            return self

    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, "a|b|c")
    result = pipeline.qa_concept(
        logo, "a|b|c", ImmediateClient(), pipeline.Brand({"primary": "#0A141E"}, {})
    )
    assert result["result"] == "refinement_needed"
    assert result["refinement"]["dimension"] == "edges_unknown_cause"
    assert (folder / "scene.toml").read_text() == recipe
    assert result["round"] == 1


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


@pytest.mark.parametrize(
    "failure",
    [
        "provider_retry",
        "provider_log",
        "qa_image_read",
        "image_encode",
        "tiny_image_read",
        "asset_corrupt",
    ],
)
def test_finalize_blocked_qa_cannot_overrun_budget_or_replace_prior_winner(
    tmp_path, monkeypatch, failure
):
    import base64
    import contextlib
    import hashlib
    import os
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from PIL import ImageDraw

    from logo_maker import pipeline
    from logo_maker.jev.client import JevClient
    from logo_maker.paths import LogoDir
    from logo_maker.sampling import SamplingLimit

    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Test")
    logo.brief.write_text(
        'name="Test"\nsummary="Test mark"\ntone=["calm"]\n'
        '[palette]\nprimary="#245846"\n[fonts]\ndisplay="Test font"\n'
    )
    concept_id = "a|b|c"
    folder = logo.concept(concept_id)
    compiled(folder)
    monkeypatch.setattr(render, "machine_context", lambda *a: {})

    def builder(path, *args, budget):
        budget.begin_attempt()
        target = Path(json.loads(path.read_text())["output_dir"])
        image = Image.new("RGBA", (4000, 4000))
        ImageDraw.Draw(image).ellipse((1000, 1000, 3000, 3000), fill=(36, 88, 70, 255))
        image.save(target / "final.png")
        (target / "final.execution.json").write_text('{"status":"verified"}')

    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, concept_id)
    monkeypatch.setattr(render, "_run_builder", builder)
    render.render(folder, "final")
    (logo.ideation / "finalists.json").write_text(json.dumps({"ids": [concept_id]}))
    prior = logo.ideation / "winner.json"
    prior.write_text('{"winner":"approved prior"}')
    seen = threading.Event()
    image_read_started = threading.Event()
    stop = threading.Event()
    image_bytes = (folder / "final.png").read_bytes()
    writers = []

    def release_old_unbounded_image_read():
        delayed = False
        while not stop.is_set():
            try:
                descriptor = os.open(folder / "final.png", os.O_WRONLY | os.O_NONBLOCK)
                image_read_started.set()
            except OSError:
                stop.wait(0.01)
                continue
            try:
                if not delayed:
                    delayed = True
                    if stop.wait(10):
                        return
                os.set_blocking(descriptor, True)
                remaining = memoryview(image_bytes)
                with contextlib.suppress(BrokenPipeError):
                    while remaining:
                        remaining = remaining[os.write(descriptor, remaining) :]
            finally:
                os.close(descriptor)
            stop.wait(0.01)

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            first = not seen.is_set()
            seen.set()
            retry = first and failure == "provider_retry"
            if first and failure in {"qa_image_read", "image_encode"}:
                (folder / "final.png").unlink()
                os.mkfifo(folder / "final.png")
                writer = threading.Thread(target=release_old_unbounded_image_read, daemon=True)
                writer.start()
                writers.append(writer)
            if first and failure == "provider_log":
                logs = logo.qa / "jev"
                logs.mkdir(parents=True, exist_ok=True)
                os.mkfifo(logs / "answers.jsonl")
            self.send_response(429 if retry else 200)
            if retry:
                self.send_header("Retry-After", "10")
            if first and failure == "asset_corrupt":
                assets_dir = logo.qa / "jev/assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                for asset in body["assets"].values():
                    digest = hashlib.sha256(base64.b64decode(asset["data_base64"])).hexdigest()
                    os.mkfifo(assets_dir / f"{digest}.{asset['format']}")
            response = json.dumps(
                {
                    "answers": {key: {"type": "noul", "noul": 0.9} for key in body["questions"]},
                    "usage": {"input_tokens": 123, "output_tokens": 7, "cost": 0.001},
                }
            ).encode()
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    if failure == "image_encode":
        # Exercise the existing request-splitting path with the same QA questions.
        monkeypatch.setattr("logo_maker.jev.client.MAX_QUESTIONS_PER_REQUEST", 1)
    client = JevClient(logo)
    client.url = f"http://127.0.0.1:{server.server_port}"
    if failure == "tiny_image_read":

        def preflight_after_cache_check(*args):
            (folder / "final.png").unlink()
            os.mkfifo(folder / "final.png")
            writer = threading.Thread(target=release_old_unbounded_image_read, daemon=True)
            writer.start()
            writers.append(writer)
            return {}

        monkeypatch.setattr(render, "machine_context", preflight_after_cache_check)
    started = time.monotonic()
    try:
        if failure == "asset_corrupt":
            with pytest.raises(pipeline.AuthoringNeeded):
                pipeline.finalize(logo, client, budget=Budget(wall_seconds=30))
            requests = list((logo.qa / "jev/requests").glob("*.json"))
            assert len(requests) == 1
            request = json.loads(requests[0].read_text())
            for asset in request["assets"].values():
                retained = logo.qa / f"jev/assets/{asset['sha256']}.{asset['format']}"
                assert retained.is_file(), "retained judgment image is not a regular file"
                assert hashlib.sha256(retained.read_bytes()).hexdigest() == asset["sha256"]
            usage = json.loads(logo.run_json.read_text())["jev"]
            assert {
                k: usage[k] for k in ("requests", "input_tokens", "output_tokens", "cost_usd")
            } == {"requests": 1, "input_tokens": 123, "output_tokens": 7, "cost_usd": 0.001}
            assert usage["unpriced_requests"] == 0
            assert "synthetic-test-key" not in requests[0].read_text()
        else:
            with pytest.raises(SamplingLimit, match="time_limit"):
                pipeline.finalize(logo, client, budget=Budget(wall_seconds=6))
        if failure == "tiny_image_read":
            assert image_read_started.is_set(), "test did not reach tiny image preparation"
            assert not seen.is_set(), (
                "provider started after image preparation exhausted its budget"
            )
        else:
            assert seen.is_set(), "test did not reach the provider"
            if failure not in {"provider_retry", "provider_log", "asset_corrupt"}:
                assert image_read_started.is_set(), "test did not reach the blocked image read"
        if failure == "provider_log":
            from logo_maker.runlog import runlog

            assert runlog(logo.run_json).data["jev"]["requests"] == 1
            assert client._seq == 2
        assert time.monotonic() - started < (33 if failure == "asset_corrupt" else 9), (
            "blocked QA exceeded the whole-job budget"
        )
        assert prior.read_text() == '{"winner":"approved prior"}'
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=1)
        for writer in writers:
            writer.join(timeout=1)


def test_exhausted_finalize_budget_stops_before_loading_inputs(tmp_path):
    from logo_maker import pipeline
    from logo_maker.paths import LogoDir
    from logo_maker.sampling import SamplingLimit

    now = [0.0]
    budget = Budget(wall_seconds=1, clock=lambda: now[0])
    now[0] = 2
    with pytest.raises(SamplingLimit, match="time_limit"):
        pipeline.finalize(LogoDir(tmp_path / "not-created"), object(), budget=budget)


def test_finalize_sampling_stop_names_evidence_and_preserves_existing_winner(tmp_path, monkeypatch):
    from logo_maker import pipeline
    from logo_maker.paths import LogoDir

    logo = LogoDir(tmp_path / "logo")
    logo.brief.parent.mkdir(parents=True, exist_ok=True)
    logo.brief.write_text(
        'name="Test"\nsummary="Test mark"\ntone=["calm"]\n[palette]\nprimary="#245846"\n[fonts]\ndisplay="Test font"\n'
    )
    (logo.ideation / "finalists.json").write_text('{"ids":["a|b|c"]}')
    prior = logo.ideation / "winner.json"
    prior.write_text('{"winner":"approved-prior"}')
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, "a|b|c")
    monkeypatch.setattr(pipeline, "brand", lambda logo: pipeline.Brand({}, {}))
    monkeypatch.setattr(
        pipeline, "qa_concept", lambda *a, **k: {"result": "sampling_review_needed"}
    )
    with pytest.raises(pipeline.AuthoringNeeded) as caught:
        pipeline.finalize(logo, client=object())
    assert logo.concept("a|b|c") / ".build/final.sampling.json" in caught.value.files
    assert prior.read_text() == '{"winner":"approved-prior"}'


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


@pytest.mark.live
def test_live_m5_finalization_retains_gpu_exports_and_budgeted_judgments(tmp_path):
    """Explicit on-machine final/export/live-provider check; no quality approval implied."""
    import hashlib
    import os
    import time

    from logo_maker import export, pipeline
    from logo_maker.blender.execution import verify_denoiser_log
    from logo_maker.jev.client import JevClient
    from logo_maker.paths import LogoDir, concept_slug

    if os.environ.get("LOGO_MAKER_LIVE_GPU_VALIDATION") != "1":
        pytest.skip("set LOGO_MAKER_LIVE_GPU_VALIDATION=1 for the explicit M5/provider check")
    from runpy import run_path

    fixture = run_path(str(Path(__file__).resolve().parents[1] / "scripts/validate_sampling.py"))[
        "fixture"
    ]
    root = Path(os.environ.get("LOGO_MAKER_LIVE_ROOT", str(tmp_path / "live-logo")))
    if root.exists():
        pytest.fail("live validation requires a new output folder")
    started = time.monotonic()
    budget = Budget(wall_seconds=1800, attempt_limit=4)
    logo = LogoDir(root)
    pipeline.new(logo, "OPTICS")
    palette = {"primary": "#245846", "background": "#F4F1EA", "ink": "#131D18"}
    logo.brief.write_text(
        'name="OPTICS"\nsummary="A precise green directional instrument mark with metal lettering"\n'
        'tone=["precise", "calm"]\n[palette]\nprimary="#245846"\n'
        'background="#F4F1EA"\nink="#131D18"\n[fonts]\ndisplay="Open Sans:wght=700"\n'
    )
    cid = "sampling-typography|embossed_plate|polished_metal"
    folder = logo.concepts / concept_slug(cid)
    fixture(folder, "typography", 0, 0.01, 4096)
    pipeline.prepare_motif(folder)
    rendered = render.render(folder, "final", budget=budget)
    assert rendered.execution is not None
    execution = json.loads(rendered.execution.read_text())
    assert execution["status"] == "verified"
    assert execution["resolution"] == [4000, 4000]
    assert any(
        "M5 Pro" in d["name"] and d["type"] == "METAL" and d["use"] for d in execution["devices"]
    )
    assert all(not d["use"] for d in execution["devices"] if d["type"] == "CPU")
    native_log = rendered.execution.parent / execution["log"]
    assert hashlib.sha256(native_log.read_bytes()).hexdigest() == execution["log_sha256"]
    assert verify_denoiser_log(native_log.read_text())["device_type"] == "Metal"
    assert Image.open(rendered.png).size == (2000, 2000)
    export_started = time.monotonic()
    paths = export.export_all(
        folder,
        folder / "exports",
        name="OPTICS",
        palette=palette,
        motif_svg=folder / "motif.svg",
        budget=budget,
    )
    export_seconds = time.monotonic() - export_started
    manifest = json.loads((folder / "exports/manifest.json").read_text())
    for key, entry in manifest["files"].items():
        assert hashlib.sha256(paths[key].read_bytes()).hexdigest() == entry["sha256"]
    assert len(paths) == 31
    assert rendered.sampling is not None
    sampling = json.loads(rendered.sampling.read_text())
    assert sampling["profile"]["state"] == "profile_unqualified"
    assert (
        manifest["sampling"]["record_sha256"]
        == hashlib.sha256(rendered.sampling.read_bytes()).hexdigest()
    )
    execution_hash = hashlib.sha256(rendered.execution.read_bytes()).hexdigest()
    (logo.ideation / "finalists.json").write_text(json.dumps({"ids": [cid]}))
    prior = logo.ideation / "winner.json"
    prior.write_text('{"winner":"prior test winner"}')
    native_attempts_before_qa = budget.attempts
    qa_started = time.monotonic()
    with pytest.raises(pipeline.AuthoringNeeded) as stop:
        pipeline.finalize(logo, JevClient(logo), budget=budget)
    qa_seconds = time.monotonic() - qa_started
    assert prior.read_text() == '{"winner":"prior test winner"}'
    assert hashlib.sha256(rendered.execution.read_bytes()).hexdigest() == execution_hash
    assert budget.attempts == native_attempts_before_qa, (
        "finalize repeated an unchanged native render"
    )
    requests = list((logo.qa / "jev/requests").glob("*.json"))
    assert requests, "no completed live judgments were retained"
    recorded_usage = []
    for path in requests:
        request = json.loads(path.read_text())
        recorded_usage.append(request["usage"])
        assert request["answers"]
        assert request["assets_status"] == "ready"
        for asset in request["assets"].values():
            image = logo.qa / f"jev/assets/{asset['sha256']}.{asset['format']}"
            assert hashlib.sha256(image.read_bytes()).hexdigest() == asset["sha256"]
    rounds = [json.loads(line) for line in (logo.qa / "rounds.jsonl").read_text().splitlines()]
    assert rounds[-1]["result"] != "pass"
    usage = json.loads(logo.run_json.read_text())["jev"]
    assert usage["requests"] == len(requests)
    assert usage["input_tokens"] == sum(row["input_tokens"] for row in recorded_usage)
    assert usage["output_tokens"] == sum(row["output_tokens"] for row in recorded_usage)
    assert abs(usage["cost_usd"] - sum(row["cost"] for row in recorded_usage)) <= 0.000001 * len(
        requests
    )
    report = {
        "seconds": time.monotonic() - started,
        "render_seconds": rendered.seconds,
        "export_seconds": export_seconds,
        "finalize_seconds": qa_seconds,
        "budget": budget.record(),
        "request_count": len(requests),
        "usage": usage,
        "qa_result": rounds[-1]["result"],
        "stop": str(stop.value),
        "execution": str(rendered.execution),
        "sampling": str(rendered.sampling),
        "verified_exports": len(paths),
        "qualification": "incomplete",
        "timing_scope": "fixture and job setup, motif, native render/denoise/diagnostics, delivery, full export and actual final QA/provider work; excludes pytest/import startup and later evidence copy/review",
        "kernel_cache_state": "unknown",
        "owner_acceptance": "not inferred",
    }
    (root / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")


@pytest.mark.parametrize("blocked", ["brief", "finalists", "runlog"])
def test_finalize_blocked_input_terminates_and_keeps_winner(tmp_path, blocked):
    import os
    import time

    from logo_maker import pipeline
    from logo_maker.paths import LogoDir
    from logo_maker.sampling import SamplingLimit

    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Test")
    logo.brief.write_text(
        'name="Test"\nsummary="Test mark"\ntone=["calm"]\n[palette]\nprimary="#245846"\n[fonts]\ndisplay="Test font"\n'
    )
    from test_brief_workflow import freeze_for_stage_test

    freeze_for_stage_test(logo)
    (logo.ideation / "finalists.json").write_text('{"ids":[]}')
    winner_path = logo.ideation / "winner.json"
    winner_path.write_text('{"winner":"approved prior"}')
    paths = {
        "brief": logo.brief,
        "finalists": logo.ideation / "finalists.json",
        "runlog": logo.run_json,
    }
    source = paths[blocked]
    source.unlink()
    os.mkfifo(source)
    # Avoid an already cached RunLog masking the actual blocked initial read.
    from logo_maker import runlog as log_module

    log_module._OPEN.pop(logo.run_json.resolve(), None)
    started = time.monotonic()
    with pytest.raises(SamplingLimit, match="time_limit"):
        pipeline.finalize(logo, object(), budget=Budget(wall_seconds=5))
    assert time.monotonic() - started < 7
    assert winner_path.read_text() == '{"winner":"approved prior"}'


def test_failed_retry_preserves_usable_active_image_and_provenance(tmp_path, monkeypatch):
    compiled(tmp_path)
    monkeypatch.setattr(render, "machine_context", lambda *a: {})

    def builder(path, *args, budget):
        budget.begin_attempt()
        target = Path(json.loads(path.read_text())["output_dir"])
        Image.new("RGBA", (64, 64), (30, 40, 50, 255)).save(target / "final.png")
        (target / "final.execution.json").write_text('{"status":"verified"}')

    monkeypatch.setattr(render, "_run_builder", builder)
    first = render.render(tmp_path, "final")
    assert first.sampling is not None
    prior_image = first.png.read_bytes()
    prior_record = first.sampling.read_bytes()
    assert render.artifact_current(tmp_path, "final", check_machine=False)

    def fail(*args, **kwargs):
        raise RuntimeError("GPU-only denoising unverified")

    monkeypatch.setattr(render, "_run_builder", fail)
    with pytest.raises(RuntimeError, match="GPU-only"):
        render.render(tmp_path, "final")
    assert first.png.read_bytes() == prior_image
    assert first.sampling.read_bytes() == prior_record
    assert render.artifact_current(tmp_path, "final", check_machine=False)
    failures = list((tmp_path / ".build").glob("final.sampling.failed-*.json"))
    assert len(failures) == 1
    assert not json.loads(failures[0].read_text())["published"]
