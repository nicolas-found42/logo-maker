"""Selection contracts: visual eligibility cannot be supplied by relative preference."""

import json

import pytest
from PIL import Image

from logo_maker.jev.questions import eligibility_decision


@pytest.fixture(autouse=True)
def synthetic_machine_context(monkeypatch):
    monkeypatch.setattr("logo_maker.render.machine_context", lambda *a: {})
    from test_refinement import inline_refinement_workers

    inline_refinement_workers(monkeypatch)


def attest(folder, stage):
    """A retained render result at the filesystem boundary; no Blender in offline tests."""
    from logo_maker.eligibility import sha256
    from logo_maker.render import source_hashes

    build = folder / ".build"
    build.mkdir(exist_ok=True)
    log = build / f"{stage}.execution.log"
    log.write_text(
        "Intel(R) Open Image Denoise 2.5.0\nType : Metal\nFilter: RT\nImage size: 32x32\n"
    )
    (build / "scene.json").write_text("{}")
    report = {
        "status": "verified",
        "policy": "metal-gpu-only",
        "device_override": "METAL",
        "devices": [{"type": "CPU", "use": False}, {"type": "METAL", "use": True}],
        "denoiser_effective": {"device_type": "Metal"},
        "log_sha256": sha256(log),
        "host_sources_sha256": source_hashes(folder),
        "delivered_sha256": sha256(folder / f"{stage}.png"),
        "inputs_sha256": {"compiled_scene": sha256(build / "scene.json")},
        "sampling": {"samples": 4096, "adaptive_threshold": 0.01, "seed": 42},
    }
    (build / f"{stage}.execution.json").write_text(json.dumps(report))
    from logo_maker.render import source_files

    (build / f"{stage}.sampling.json").write_text(
        json.dumps(
            {
                "published": True,
                "context": {},
                "dependencies": {str(p): sha256(p) for p in source_files(folder)},
                "delivered_sha256": sha256(folder / f"{stage}.png"),
                "execution": str(build / f"{stage}.execution.json"),
                "execution_sha256": sha256(build / f"{stage}.execution.json"),
                "profile": {"state": "qualified"},
                "outcomes": {"sampling": "profile_baseline", "cap": "unknown", "noise": "unknown"},
            }
        )
    )


def qualified_brief(image):
    from logo_maker.brief import Brief, Reference

    return Brief(
        "N",
        "S",
        ("calm",),
        intended_appearance="Matte clay with soft edges",
        references=(Reference(image, "craft", "Deliberately restrained matte finish"),),
    )


class EligibilityClient:
    """External judge stub with explicit, independently specified outcomes."""

    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.states = []

    def with_budget(self, budget):
        budget.check()
        return self

    def ask(self, state, questions, *, label):
        self.states.append((state, label))
        return {qid: {"noul": self.overrides.get(qid, 0.9)} for qid in questions}

    def ask_many(self, jobs):
        return [self.ask(s, q, label=label) for s, q, label in jobs]


def candidate_logo(tmp_path):
    from test_jev_stages import _write_metaphors, _write_pool

    from logo_maker.paths import LogoDir

    logo = LogoDir(tmp_path)
    cid = "m|medallion|clay"
    _write_metaphors(logo, ["m", *[f"other{i}" for i in range(7)]])
    _write_pool(logo, [cid])
    folder = logo.concept(cid)
    (folder / "motif.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path id="mark" fill="#646464" d="M250 250 L750 250 L750 750 L250 750 Z"/></svg>'
    )
    (folder / "scene.toml").write_text('[render]\nrenderer = "cycles"\n')
    for stage in ("preview", "final"):
        Image.new("RGBA", (32, 32), (100, 100, 100, 255)).save(folder / f"{stage}.png")
        attest(folder, stage)
    brief = qualified_brief(folder / "preview.png")
    review_inputs(logo, cid, brief)
    for stage in ("preview", "final"):
        attest(folder, stage)
    return logo, cid, brief


def review_inputs(logo, cid, brief):
    import tomlkit
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    state = brief.as_state()
    state["references"] = [
        {"path": str(ref.path), "use": ref.use, "note": ref.note} for ref in brief.references
    ]
    logo.brief.write_text(tomlkit.dumps(state))
    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, cid)
    for stage in ("preview", "final"):
        if (logo.concept(cid) / f"{stage}.png").exists():
            attest(logo.concept(cid), stage)
    if (logo.concept(cid) / "render-state.json").exists():
        prepare_creative_final(logo, cid)


def complete_fit(symbol="pass", appearance="pass"):
    return {
        "symbol": symbol,
        "appearance": appearance,
        "brand_specificity": "pass",
        "meaningful_synthesis": "pass",
        "constraint_fidelity": "pass",
        "communicative_clarity": "pass",
        "small_flat": "pass",
        "small_hero": "pass",
    }


def test_technical_strength_cannot_rescue_poor_craft():
    outcome = eligibility_decision(
        craft=["fail"],
        fit=complete_fit(),
        technical="pass",
        evidence="complete",
    )
    assert outcome == "fail"


def test_literal_depiction_cannot_rescue_an_undeveloped_brand_idea():
    assert (
        eligibility_decision(
            craft=["pass"],
            fit={
                "symbol": "pass",
                "appearance": "pass",
                "brand_specificity": "fail",
                "meaningful_synthesis": "pass",
                "constraint_fidelity": "pass",
                "communicative_clarity": "pass",
                "small_flat": "pass",
                "small_hero": "pass",
            },
            technical="pass",
            evidence="complete",
        )
        == "fail"
    )


@pytest.mark.parametrize(
    ("craft", "symbol", "appearance", "technical", "evidence", "expected"),
    [
        (["fail"], "fail", "fail", "fail", "complete", "fail"),
        (["pass", "pass"], "pass", "pass", "pass", "complete", "pass"),
        (["pass"], "unsettled", "pass", "pass", "complete", "unsettled"),
        (["pass", "unsettled"], "pass", "pass", "pass", "complete", "unsettled"),
        (["pass"], "pass", "fail", "pass", "complete", "fail"),
        ([], "pass", "pass", "pass", "complete", "missing_evidence"),
        (["pass"], "pass", "pass", "pass", "missing_evidence", "missing_evidence"),
        (["api_error"], "pass", "pass", "pass", "complete", "api_error"),
        (["pass"], "pass", "pass", "unsettled", "complete", "unsettled"),
        (["pass"], "pass", "pass", "fail", "complete", "fail"),
    ],
)
def test_essential_gate_rows(craft, symbol, appearance, technical, evidence, expected):
    assert (
        eligibility_decision(
            craft=craft,
            fit=complete_fit(symbol, appearance),
            technical=technical,
            evidence=evidence,
        )
        == expected
    )


def test_missing_reference_never_calls_provider_or_promotes(tmp_path):
    from logo_maker.brief import Brief
    from logo_maker.eligibility import assess
    from logo_maker.paths import LogoDir

    class NoCalls:
        def ask(self, *args, **kwargs):
            raise AssertionError("missing evidence must be resolved before model calls")

        def ask_many(self, jobs):
            raise AssertionError("unexpected model calls")

    record = assess(
        LogoDir(tmp_path),
        Brief("N", "S", ("calm",)),
        "m|medallion|clay",
        tmp_path / "missing.png",
        NoCalls(),
        stage="preview",
    )
    assert record["status"] == "missing_evidence"
    assert "craft reference" in " ".join(record["missing"])


def test_preview_cannot_promote_without_floor(tmp_path):
    from PIL import Image
    from test_jev_stages import FakeClient, _screen_answers, _write_metaphors, _write_pool

    from logo_maker.brief import Brief
    from logo_maker.judging import screen_previews
    from logo_maker.paths import LogoDir

    logo = LogoDir(tmp_path)
    cid = "m|medallion|clay"
    _write_metaphors(logo, ["m", *[f"other{i}" for i in range(7)]])
    _write_pool(logo, [cid])
    image = logo.concept(cid) / "preview.png"
    Image.new("RGB", (32, 32)).save(image)
    client = FakeClient([_screen_answers(0.9, 0.9, 4.0)])
    with pytest.raises(ValueError, match="missing_evidence"):
        screen_previews(logo, Brief("N", "S", ("calm",)), {cid: image}, client)
    assert not (logo.ideation / "finalists.json").exists()


def test_structural_review_uses_current_description_instead_of_ideation_text(tmp_path):
    import tomlkit
    from test_brief_workflow import BriefJudge

    from logo_maker import briefing
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    folder = logo.concept(cid)
    info_path = folder / "concept.json"
    info = json.loads(info_path.read_text())
    info["description"] = "Two broad paper S initials share one scored lower foot"
    info_path.write_text(json.dumps(info))
    plan_path = folder / "plan.toml"
    plan = tomlkit.parse(plan_path.read_text())
    plan["hypothesis"] = "The supplied initials join through a common team index"
    plan["visual_mechanism"] = info["description"]
    plan_path.write_text(tomlkit.dumps(plan))
    assert briefing.review_plan(logo, cid, BriefJudge())["status"] == "pass"
    attest(folder, "final")
    client = EligibilityClient()
    result = assess(logo, brief, cid, folder / "final.png", client, stage="final")
    assert result["status"] == "pass"
    literal = [
        state["concept"]
        for state, label in client.states
        if label.endswith(("-symbol-fit", "-technical"))
    ]
    assert len(literal) == 2
    assert all(c["description"] == info["description"] for c in literal)
    assert all(c["metaphor"] == plan["hypothesis"] for c in literal)


def test_missing_current_description_stops_before_visual_judgments(tmp_path):
    from test_brief_workflow import BriefJudge

    from logo_maker import briefing
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    folder = logo.concept(cid)
    path = folder / "concept.json"
    info = json.loads(path.read_text())
    info.pop("description", None)
    path.write_text(json.dumps(info))
    assert briefing.review_plan(logo, cid, BriefJudge())["status"] == "pass"
    attest(folder, "final")
    client = EligibilityClient()
    result = assess(logo, brief, cid, folder / "final.png", client, stage="final")
    assert result["status"] == "missing_evidence"
    assert "current description" in " ".join(result["missing"])
    assert not client.states


def test_equal_floor_passes_with_both_orders_and_current_revision(tmp_path):
    from logo_maker.eligibility import assess, require_current

    logo, cid, brief = candidate_logo(tmp_path)
    client = EligibilityClient()
    result = assess(logo, brief, cid, logo.concept(cid) / "final.png", client, stage="final")
    assert result["status"] == "pass"
    assert [r["order"] for r in result["craft"]] == [
        ["candidate", "reference"],
        ["reference", "candidate"],
    ]
    assert all(
        "reference" not in state
        for state, label in client.states
        if label.endswith("fit-technical")
    )
    require_current(logo, brief, cid, result)
    (logo.concept(cid) / "scene.toml").write_text("# revised scene")
    from logo_maker.proc import ToolError

    with pytest.raises(ToolError, match="execution"):
        require_current(logo, brief, cid, result)


def test_business_fit_receives_frozen_priority_without_author_rationale(tmp_path):
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)

    class BusinessFitJudge(EligibilityClient):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            if "brand_specificity" in questions and (
                "concept" in state or "communication_priority" not in state["brief"]
            ):
                answers["brand_specificity"] = {"noul": 0.1}
            return answers

    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", BusinessFitJudge(), stage="final"
    )
    assert result["status"] == "pass"


def test_changed_detail_plan_invalidates_final_eligibility(tmp_path):
    from logo_maker.eligibility import assess, require_current

    logo, cid, brief = candidate_logo(tmp_path)
    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", EligibilityClient(), stage="final"
    )
    assert result["status"] == "pass"
    (logo.concept(cid) / "plan.toml").write_text('hypothesis = "New construction"\n')
    from logo_maker.proc import ToolError

    with pytest.raises((ValueError, ToolError), match="stale"):
        require_current(logo, brief, cid, result)


def test_missing_plan_review_never_supplies_eligibility(tmp_path):
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    (logo.concept(cid) / "plan-review.json").unlink()
    client = EligibilityClient()
    result = assess(logo, brief, cid, logo.concept(cid) / "final.png", client, stage="final")
    assert result["status"] == "missing_evidence"
    assert not client.states


def test_finalize_rejects_changed_plan_before_render_or_selection(tmp_path):
    from logo_maker import pipeline

    logo, cid = finalize_logo(tmp_path)
    path = logo.concept(cid) / "plan.toml"
    path.write_text(path.read_text().replace("Recognition", "Changed purpose"))
    old_winner = logo.ideation / "winner.json"
    old_winner.write_text('{"winner": "previous"}')
    output = logo.exports / "hero-transparent.png"
    output.write_bytes(b"previous accepted image")
    judge = EligibilityClient()
    with pytest.raises(pipeline.AuthoringNeeded, match="plan review"):
        pipeline.finalize(logo, judge)
    assert not judge.states
    assert json.loads(old_winner.read_text())["winner"] == "previous"
    assert output.read_bytes() == b"previous accepted image"


@pytest.mark.parametrize(
    "qid", ["detail_preserved", "aliasing_free", "structure_correct", "noise_free"]
)
def test_smooth_or_noise_free_counterexamples_still_fail(tmp_path, qid):
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    result = assess(
        logo,
        brief,
        cid,
        logo.concept(cid) / "final.png",
        EligibilityClient({qid: 0.1}),
        stage="final",
    )
    assert result["status"] == "fail"
    assert result["sampling"]["convergence"] == "unknown"


def test_final_selection_all_poor_keeps_winner_exports_and_floor(tmp_path):
    from logo_maker.judging import final_tournament

    logo, cid, brief = candidate_logo(tmp_path)
    old = logo.ideation / "winner.json"
    old.write_text('{"winner": "existing"}')
    exported = logo.exports / "hero-transparent.png"
    exported.write_bytes(b"retained exports")
    floor = logo.root / "floor"
    floor.mkdir()
    (floor / "hero-transparent.png").write_bytes(b"retained same-brand floor")
    with pytest.raises(ValueError, match="no final candidate meets"):
        final_tournament(
            logo,
            brief,
            {cid: logo.concept(cid) / "final.png"},
            EligibilityClient({"form_finish": 0.1}),
        )
    assert json.loads(old.read_text()) == {"winner": "existing"}
    assert exported.read_bytes() == b"retained exports"
    assert (floor / "hero-transparent.png").read_bytes() == b"retained same-brand floor"


@pytest.mark.parametrize("malformed", [None, float("nan"), 2.0, True])
def test_api_failure_stays_error_and_keeps_old_winner(tmp_path, malformed):
    from logo_maker.jev.client import JevError
    from logo_maker.judging import final_tournament

    logo, cid, brief = candidate_logo(tmp_path)
    old = logo.ideation / "winner.json"
    old.write_text('{"winner": "existing"}')
    with pytest.raises(JevError, match="invalid eligibility answer"):
        final_tournament(
            logo,
            brief,
            {cid: logo.concept(cid) / "final.png"},
            EligibilityClient({"form_finish": malformed}),
        )
    assert json.loads(old.read_text()) == {"winner": "existing"}
    rows = [json.loads(s) for s in (logo.qa / "eligibility.jsonl").read_text().splitlines()]
    assert rows[-1]["status"] == "api_error"


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [
        (400, {"error": "image processing failed"}, "image processing failed"),
        (200, {"usage": {"input_tokens": 50, "output_tokens": 0, "cost": 0.0}}, "answers"),
        (200, ["not a response envelope"], "object"),
    ],
)
def test_provider_failure_retains_submitted_pixels_and_request(
    tmp_path, monkeypatch, status, payload, error
):
    import base64
    import hashlib

    import httpx

    from logo_maker.eligibility import assess
    from logo_maker.jev.client import JevClient, JevError

    logo, cid, brief = candidate_logo(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    submitted = []

    def reject(request):
        submitted.append(json.loads(request.content))
        return httpx.Response(status, json=payload)

    client = JevClient(logo)
    client._http = httpx.Client(transport=httpx.MockTransport(reject))
    with pytest.raises(JevError, match=error):
        assess(logo, brief, cid, logo.concept(cid) / "final.png", client, stage="final")
    requests = list((logo.qa / "jev" / "requests").glob("*.json"))
    assert len(requests) == 1
    record = json.loads(requests[0].read_text())
    assert record["status"] == "api_error"
    assert record["state"] == submitted[0]["state"]
    assert record["questions"] == submitted[0]["questions"]
    if status == 200 and isinstance(payload, dict):
        assert record["provider_usage"] == payload["usage"]
        assert record["usage"]["cost"] == 0.0
    else:
        assert record["usage"]["cost"] is None
    totals = json.loads(logo.run_json.read_text())["jev"]
    assert totals["requests"] == 1
    if status == 200 and isinstance(payload, dict):
        assert totals["cost_usd"] == 0.0
        assert totals["unpriced_requests"] == 0
        assert totals["output_tokens"] == 0
    else:
        assert totals["cost_usd"] is None
        assert totals["unpriced_requests"] == 1
        assert totals["input_tokens"] is None
    assert "test-secret" not in requests[0].read_text()
    for key, asset in submitted[0]["assets"].items():
        raw = base64.b64decode(asset["data_base64"])
        digest = hashlib.sha256(raw).hexdigest()
        assert record["assets"][key]["sha256"] == digest
        assert (logo.qa / "jev" / "assets" / f"{digest}.png").read_bytes() == raw
    outcome = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert outcome["status"] == "api_error"


@pytest.mark.parametrize("legacy", [False, True])
def test_unpriced_judgments_keep_reported_subtotal_and_unknown_total(tmp_path, monkeypatch, legacy):
    import httpx

    from logo_maker.eligibility import assess
    from logo_maker.jev.client import JevClient

    historical = {"requests": 2, "cost_usd": 0.7, "input_tokens": 30, "output_tokens": 4}
    if legacy:
        (tmp_path / "run.json").write_text(
            json.dumps(
                {
                    "seeds": {},
                    "stages": {},
                    "jev": historical,
                    "assets": {},
                    "versions": {},
                    "events": [],
                }
            )
        )
    logo, cid, brief = candidate_logo(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    calls = []

    def answer(request):
        payload = json.loads(request.content)
        calls.append(payload)
        usage = {"input_tokens": 10, "output_tokens": 2}
        if len(calls) == 1:
            usage["cost"] = 0.125
        return httpx.Response(
            200,
            json={
                "answers": {key: {"noul": 0.9} for key in payload["questions"]},
                "usage": usage,
            },
        )

    client = JevClient(logo)
    client._http = httpx.Client(transport=httpx.MockTransport(answer))
    outcome = assess(logo, brief, cid, logo.concept(cid) / "final.png", client, stage="final")
    assert outcome["status"] == "pass"
    records = [
        json.loads(path.read_text())
        for path in sorted((logo.qa / "jev" / "requests").glob("*.json"))
    ]
    assert records[0]["usage"]["cost"] == 0.125
    assert all(record["usage"]["cost"] is None for record in records[1:])
    assert all("cost" not in record["provider_usage"] for record in records[1:])
    usage = json.loads(logo.run_json.read_text())["jev"]
    assert usage["cost_usd"] is None
    assert usage["reported_cost_usd"] == 0.125
    assert usage["unpriced_requests"] == len(records) - 1 + (2 if legacy else 0)
    if legacy:
        assert usage["legacy_usage"] == historical
        assert usage["input_tokens"] is None
        assert usage["reported_input_tokens"] > 0


@pytest.mark.parametrize(
    ("change", "limit", "device", "outcome"),
    [
        ({"noise_free": "fail"}, "capped", "verified", "cap_limited_noise"),
        ({"noise_free": "fail"}, "below_cap", "verified", "sampling_noise"),
        ({"noise_free": "fail"}, "unknown", "verified", "noise_limit_unknown"),
        ({"detail_preserved": "fail"}, "capped", "verified", "detail_loss"),
        ({"aliasing_free": "fail"}, "below_cap", "verified", "persistent_aliasing"),
        ({"structure_correct": "fail"}, "below_cap", "verified", "structural_error"),
        ({"noise_free": "unsettled"}, "unknown", "verified", "unknown"),
        ({}, "capped", "verified", "visual_pass_capped"),
        ({}, "unknown", "verified", "visual_pass_limit_unknown"),
        ({}, "below_cap", "cpu", "device_error"),
    ],
)
def test_sampling_is_not_craft_or_preference(change, limit, device, outcome):
    from logo_maker.jev.questions import sampling_decision, technical_questions

    checks = dict.fromkeys(technical_questions(), "pass")
    checks.update(change)
    assert sampling_decision(checks, limit=limit, device=device) == outcome


def test_finalist_cannot_hide_provider_transport_error(tmp_path):
    from logo_maker.jev.client import JevError
    from logo_maker.judging import final_tournament

    class BrokenClient(EligibilityClient):
        def ask(self, state, questions, *, label):
            raise JevError("HTTP 503: retries exhausted")

    logo, cid, brief = candidate_logo(tmp_path)
    with pytest.raises(JevError, match="503"):
        final_tournament(logo, brief, {cid: logo.concept(cid) / "final.png"}, BrokenClient())
    assert not (logo.ideation / "winner.json").exists()


def test_cached_cpu_output_is_operational_error_not_craft_label(tmp_path):
    from logo_maker.eligibility import assess
    from logo_maker.proc import ToolError

    logo, cid, brief = candidate_logo(tmp_path)
    execution = logo.concept(cid) / ".build/final.execution.json"
    report = json.loads(execution.read_text())
    report["devices"][0]["use"] = True
    execution.write_text(json.dumps(report))
    client = EligibilityClient()
    with pytest.raises(ToolError, match="GPU-only"):
        assess(logo, brief, cid, logo.concept(cid) / "final.png", client, stage="final")
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "execution_policy_error"
    assert "craft" not in record
    assert not client.states


def finalize_logo(tmp_path):
    from PIL import ImageDraw
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    logo, cid, _ = candidate_logo(tmp_path)
    logo.brief.write_text("""name = "N"
summary = "S"
tone = ["calm"]
intended_appearance = "Matte clay with soft edges"
[palette]
primary = "#646464"
[fonts]
display = "Manrope:wght=700"
[[references]]
path = "concepts/m--medallion--clay/preview.png"
use = "craft"
note = "Deliberately restrained matte finish"
""")
    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, cid)
    im = Image.new("RGBA", (512, 512))
    ImageDraw.Draw(im).ellipse((100, 100, 412, 412), fill=(100, 100, 100, 255))
    im.resize((128, 128), Image.Resampling.LANCZOS).save(logo.concept(cid) / "final.png")
    prepare_creative_final(logo, cid)
    return logo, cid


def test_lone_finalist_is_rechecked_before_winner(tmp_path):
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, _ = finalize_logo(tmp_path)
    winner = logo.ideation / "winner.json"
    winner.write_text('{"winner": "previous"}')
    with pytest.raises(AuthoringNeeded, match="no final candidate meets"):
        finalize(logo, EligibilityClient({"form_finish": 0.1}))
    assert json.loads(winner.read_text()) == {"winner": "previous"}


def test_lone_eligible_finalist_has_proof_not_a_forced_choice(tmp_path):
    from logo_maker.pipeline import finalize

    logo, cid = finalize_logo(tmp_path)
    assert finalize(logo, EligibilityClient()) == cid
    result = json.loads((logo.ideation / "winner.json").read_text())
    assert result["eligibility"]["status"] == "pass"
    assert result["matches"] == []


def test_generic_edge_failure_requests_diagnosis_without_sample_escalation(tmp_path):
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, cid = finalize_logo(tmp_path)
    scene = logo.concept(cid) / "scene.toml"
    before = scene.read_bytes()
    with pytest.raises(AuthoringNeeded, match="technical diagnosis"):
        finalize(logo, EligibilityClient({"clean_edges": 0.1}))
    assert scene.read_bytes() == before
    rows = [json.loads(row) for row in (logo.qa / "rounds.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["result"] == "authoring_needed"


@pytest.mark.parametrize(
    "feedback",
    [
        {"craftsmanship": "fail", "brief_fit": "fail", "statement": "both below floor"},
        {"overall": "fail", "statement": "rootshare fails"},
    ],
)
def test_owner_rejection_vetoes_model_pass_without_relabeling_answers(tmp_path, feedback):
    from logo_maker.eligibility import sha256
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, cid = finalize_logo(tmp_path)
    (logo.qa / "owner-feedback.json").write_text(
        json.dumps(
            [
                {
                    "concept": cid,
                    "candidate_sha256": sha256(logo.concept(cid) / "final.png"),
                    "brief_sha256": sha256(logo.brief),
                    "preference": "unranked",
                    **feedback,
                }
            ]
        )
    )
    with pytest.raises(AuthoringNeeded, match="no final candidate meets"):
        finalize(logo, EligibilityClient())
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "fail"
    assert record["decision_basis"] == "owner_rejection"
    assert record["fit"]["symbol"] == "pass"
    assert record["owner_feedback"][0] == {
        "concept": cid,
        "candidate_sha256": sha256(logo.concept(cid) / "final.png"),
        "brief_sha256": sha256(logo.brief),
        "preference": "unranked",
        **feedback,
    }
    assert not (logo.ideation / "winner.json").exists()


def test_unchanged_rejected_pixels_need_fresh_review_after_input_change(tmp_path):
    from dataclasses import replace

    from logo_maker.brief import load
    from logo_maker.eligibility import owner_review_scope, sha256
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, cid = finalize_logo(tmp_path)
    image = logo.concept(cid) / "final.png"
    brief = load(logo.brief)
    review = {
        "concept": cid,
        "candidate_sha256": sha256(image),
        "brief_sha256": sha256(logo.brief),
        "input_revision_sha256": owner_review_scope(logo, brief, cid, image),
        "overall": "fail",
        "statement": "Owner rejects this exact final.",
    }
    (logo.qa / "owner-feedback.json").write_text(json.dumps([review]))
    review_inputs(logo, cid, replace(brief, summary="An updated explanation of the same service."))
    (logo.ideation / "winner.json").write_text('{"winner": "previous"}')
    exported = logo.exports / "hero-transparent.png"
    exported.write_bytes(b"previous accepted output")
    with pytest.raises(AuthoringNeeded, match="no final candidate meets"):
        finalize(logo, EligibilityClient())
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "unsettled"
    assert record["decision_basis"] == "stale_owner_review"
    assert record["owner_feedback_stale"] == [review]
    assert record["fit"]["symbol"] == "pass"
    assert exported.read_bytes() == b"previous accepted output"
    assert json.loads((logo.ideation / "winner.json").read_text())["winner"] == "previous"


@pytest.mark.parametrize(
    ("label", "expected"),
    [("fail", "fail"), ("uncertain", "unsettled"), ("invalid", "missing_evidence")],
)
def test_current_owner_review_keeps_scope_and_labels_distinct(tmp_path, label, expected):
    from logo_maker.brief import load
    from logo_maker.eligibility import owner_review_scope, sha256
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, cid = finalize_logo(tmp_path)
    image = logo.concept(cid) / "final.png"
    scope = owner_review_scope(logo, load(logo.brief), cid, image)
    row = {
        "concept": cid,
        "candidate_sha256": sha256(image),
        "brief_sha256": sha256(logo.brief),
        "input_revision_sha256": scope,
        "overall": label,
    }
    (logo.qa / "owner-feedback.json").write_text(json.dumps([row]))
    assert owner_review_scope(logo, load(logo.brief), cid, image) == scope
    with pytest.raises(AuthoringNeeded, match="no final candidate meets"):
        finalize(logo, EligibilityClient())
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["status"] == expected
    assert record["fit"]["symbol"] == "pass"
    if label != "invalid":
        assert record["owner_feedback"] == [row]
        assert record["owner_feedback_scopes"] == ["current"]
        assert "craftsmanship" not in row


def test_owner_approval_does_not_supply_missing_model_craft(tmp_path):
    from logo_maker.brief import load
    from logo_maker.eligibility import owner_review_scope, sha256
    from logo_maker.pipeline import AuthoringNeeded, finalize

    logo, cid = finalize_logo(tmp_path)
    image = logo.concept(cid) / "final.png"
    row = {
        "concept": cid,
        "candidate_sha256": sha256(image),
        "brief_sha256": sha256(logo.brief),
        "input_revision_sha256": owner_review_scope(logo, load(logo.brief), cid, image),
        "overall": "pass",
    }
    (logo.qa / "owner-feedback.json").write_text(json.dumps([row]))
    with pytest.raises(AuthoringNeeded, match="no final candidate meets"):
        finalize(logo, EligibilityClient({"form_finish": 0.1}))
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "fail"
    assert record["owner_feedback"] == [row]


def test_preview_rejection_never_transfers_to_different_final_pixels(tmp_path):
    from logo_maker.brief import load
    from logo_maker.eligibility import owner_review_scope, sha256
    from logo_maker.pipeline import finalize

    logo, cid = finalize_logo(tmp_path)
    preview = logo.concept(cid) / "preview.png"
    row = {
        "concept": cid,
        "candidate_sha256": sha256(preview),
        "brief_sha256": sha256(logo.brief),
        "input_revision_sha256": owner_review_scope(logo, load(logo.brief), cid, preview),
        "overall": "fail",
    }
    (logo.qa / "owner-feedback.json").write_text(json.dumps([row]))
    assert finalize(logo, EligibilityClient()) == cid
    record = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
    assert record["owner_feedback"] == []
    assert record["status"] == "pass"


def test_reviewed_detail_plan_cannot_supply_missing_visible_detail(tmp_path):
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "develop_detail"\n'
        'kind = "authoring"\nclaim = "Develop purposeful visual detail"\n'
        'origin = "proposal"\npriority = "must"\nsources = []\n'
    )
    from test_brief_workflow import BriefJudge, plan_for_stage_test

    from logo_maker import pipeline

    pipeline.review_brief(logo, BriefJudge(), revision_reason="Detail-development obligation")
    plan_for_stage_test(logo, cid)
    attest(logo.concept(cid), "final")
    result = assess(
        logo,
        brief,
        cid,
        logo.concept(cid) / "final.png",
        EligibilityClient({"realized_detail_0": 0.1}),
        stage="final",
    )
    assert result["status"] == "fail"
    assert result["detail_obligations"][0]["checks"]["realized_detail_0"] == "fail"
    assert result["fit"]["symbol"] == "pass"


def test_specific_authoring_correction_is_judged_separately_from_plan_realization(tmp_path):
    from test_brief_workflow import BriefJudge, plan_for_stage_test

    from logo_maker import pipeline
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "seating"\nkind = "authoring"\n'
        'claim = "Resolve the detached insert seating"\norigin = "proposal"\n'
        'priority = "must"\nsources = []\n'
    )
    pipeline.review_brief(logo, BriefJudge(), revision_reason="Specific seating correction")
    plan_for_stage_test(logo, cid)
    attest(logo.concept(cid), "final")

    class CorrectionJudge(EligibilityClient):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            if "obligation_realized" in questions:
                assert (
                    state["authoring_obligation"]["claim"] == "Resolve the detached insert seating"
                )
                answers["obligation_realized"] = {"noul": 0.1}
            return answers

    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", CorrectionJudge(), stage="final"
    )
    assert result["status"] == "fail"
    assert result["detail_obligations"][0]["checks"]["realized_detail_0"] == "pass"


def test_changed_detail_baseline_during_judgment_never_returns_pass(tmp_path):
    import shutil

    from test_brief_workflow import BriefJudge, plan_for_stage_test

    from logo_maker import pipeline
    from logo_maker.eligibility import assess

    logo, cid, brief = candidate_logo(tmp_path)
    baseline = logo.inputs / "baseline.png"
    shutil.copyfile(logo.concept(cid) / "preview.png", baseline)
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "detail"\nkind = "authoring"\n'
        'claim = "Develop detail"\norigin = "proposal"\npriority = "must"\nsources = []\n'
        'baseline_image = "inputs/baseline.png"\n'
    )
    pipeline.review_brief(logo, BriefJudge(), revision_reason="Retain a detail baseline")
    plan_for_stage_test(logo, cid)
    attest(logo.concept(cid), "final")

    class ChangingBaseline(EligibilityClient):
        def ask(self, state, questions, *, label):
            baseline.write_bytes(b"source changed during provider call")
            return super().ask(state, questions, label=label)

    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", ChangingBaseline(), stage="final"
    )
    assert result["status"] == "missing_evidence"
    assert result["missing"]


def test_reference_remainder_tiles_retain_native_pixels_without_upscaling(tmp_path):
    from dataclasses import replace

    from logo_maker.brief import Reference
    from logo_maker.eligibility import assess

    class InspectViews(EligibilityClient):
        def ask(self, state, questions, *, label):
            for tile in state.get("native_detail_views", {}).get("reference", {}).values():
                with Image.open(tile.path) as pixels:
                    assert pixels.size == (1000, 1000)
                    assert pixels.getpixel((0, 0)) == (40, 80, 120, 255)
            return super().ask(state, questions, label=label)

    logo, cid, brief = candidate_logo(tmp_path)
    reference = tmp_path / "reference-1200.png"
    Image.new("RGBA", (1200, 1200), (40, 80, 120, 255)).save(reference)
    brief = replace(brief, references=(Reference(reference, "craft", "Matte finish"),))
    review_inputs(logo, cid, brief)
    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", InspectViews(), stage="final"
    )
    assert result["status"] == "pass"


@pytest.mark.parametrize(
    "damage", ["stripped", "craft_missing", "contradicted_fit", "contradicted_craft"]
)
def test_current_proof_requires_complete_consistent_essential_answers(tmp_path, damage):
    from logo_maker.brief import load
    from logo_maker.eligibility import assess, require_current

    logo, cid, _ = candidate_logo(tmp_path)
    brief = load(logo.brief)
    proof = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", EligibilityClient(), stage="final"
    )
    assert proof["status"] == "pass"
    if damage == "stripped":
        proof = {k: proof[k] for k in ("status", "revision", "revision_sha256")}
    elif damage == "craft_missing":
        proof["craft"].pop()
    elif damage == "contradicted_fit":
        proof["answers"]["appearance"]["noul"] = 0.1
    else:
        proof["craft"][0]["answers"]["edge_refinement"]["noul"] = 0.1
    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        require_current(logo, brief, cid, proof)


def test_repeated_reference_bytes_keep_each_declared_comparison(tmp_path):
    from dataclasses import replace

    from logo_maker.brief import load
    from logo_maker.eligibility import assess, require_current

    logo, cid, _ = candidate_logo(tmp_path)
    brief = load(logo.brief)
    review_inputs(logo, cid, replace(brief, references=brief.references * 2))
    attest(logo.concept(cid), "final")
    brief = load(logo.brief)
    proof = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", EligibilityClient(), stage="final"
    )
    assert proof["status"] == "pass"
    assert len(proof["craft"]) == 4
    require_current(logo, brief, cid, proof)


def test_sampling_execution_resolves_meshes_against_compiled_build_directory(tmp_path):
    from logo_maker.eligibility import sha256
    from logo_maker.proc import ToolError
    from logo_maker.render import verify_execution

    logo, cid, _ = candidate_logo(tmp_path)
    folder = logo.concept(cid)
    build = folder / ".build"
    meshes = build / "meshes"
    meshes.mkdir()
    mesh = meshes / "part.ply"
    mesh.write_bytes(b"exact compiled mesh bytes")
    (build / "scene.json").write_text(json.dumps({"build_dir": str(build)}))
    execution = build / "final.execution.json"
    report = json.loads(execution.read_text())
    report["inputs_sha256"].update(compiled_scene=sha256(build / "scene.json"))
    report["inputs_sha256"]["meshes/part.ply"] = sha256(mesh)
    execution.write_text(json.dumps(report))
    sidecar = build / "final.sampling.json"
    sampling = json.loads(sidecar.read_text())
    sampling["execution_sha256"] = sha256(execution)
    sidecar.write_text(json.dumps(sampling))
    assert verify_execution(folder, "final")["status"] == "verified"
    mesh.write_bytes(b"changed mesh")
    with pytest.raises(ToolError, match="changed render input"):
        verify_execution(folder, "final")


def prepare_creative_final(logo, cid):
    """Retained synthetic creative evidence supplements the independent craft fixture."""
    from test_brief_workflow import plan_for_stage_test

    from logo_maker import refinement

    folder = logo.concept(cid)
    (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": [cid]}))
    info = json.loads((folder / "concept.json").read_text())
    info["description"] = "A single purposeful contour"
    (folder / "concept.json").write_text(json.dumps(info))
    (folder / "construction.json").write_text(
        json.dumps(
            {
                "symbol": "Shared contour",
                "brand_geometry": "One recognizable contour",
                "material_construction": "Solid matte body",
                "intended_appearance": "Matte clay",
                "disproof": "Unclear silhouette",
                "current_description": info["description"],
                "dependencies": [],
            }
        )
    )
    plan_for_stage_test(logo, cid)
    attest(folder, "final")
    build = folder / ".build"
    staged = refinement._archive(
        logo,
        cid,
        "final",
        refinement.source_hashes(logo, folder),
        folder / "final.png",
        build / "final.execution.json",
        build / "final.sampling.json",
        0,
    )
    for entry in staged["entries"]:
        if "source" in entry:
            __import__("pathlib").Path(entry["source"]).rename(entry["target"])
        else:
            __import__("pathlib").Path(entry["target"]).write_text(entry["text"])
    record = staged["record"]
    (folder / "inspection-final.json").write_text(
        json.dumps(
            {
                "revision": record["revision"],
                "observations": "Controlled synthetic contour",
                "critiques": [],
            }
        )
    )
    (logo.ideation / "finalists.json").write_text(
        json.dumps({"ids": [cid], "binding": refinement.campaign_key(logo, [cid])})
    )
