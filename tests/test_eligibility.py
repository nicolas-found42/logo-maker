"""Selection contracts: visual eligibility cannot be supplied by relative preference."""

import json

import pytest
from PIL import Image

from logo_maker.jev.questions import eligibility_decision


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
    (build / f"{stage}.json").write_text("{}")
    report = {
        "status": "verified",
        "policy": "metal-gpu-only",
        "device_override": "METAL",
        "devices": [{"type": "CPU", "use": False}, {"type": "METAL", "use": True}],
        "denoiser_effective": {"device_type": "Metal"},
        "log_sha256": sha256(log),
        "host_sources_sha256": source_hashes(folder),
        "delivered_sha256": sha256(folder / f"{stage}.png"),
        "inputs_sha256": {"compiled_scene": sha256(build / f"{stage}.json")},
        "sampling": {"samples": 4096, "adaptive_threshold": 0.01, "seed": 42},
    }
    (build / f"{stage}.execution.json").write_text(json.dumps(report))


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
    return logo, cid, qualified_brief(folder / "preview.png")


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
    im = Image.new("RGBA", (512, 512))
    ImageDraw.Draw(im).ellipse((100, 100, 412, 412), fill=(100, 100, 100, 255))
    im.resize((128, 128), Image.Resampling.LANCZOS).save(logo.concept(cid) / "final.png")
    attest(logo.concept(cid), "final")
    (logo.ideation / "finalists.json").write_text(json.dumps({"ids": [cid]}))
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
    with pytest.raises(AuthoringNeeded, match="no finalist passed QA"):
        finalize(logo, EligibilityClient({"clean_edges": 0.1}))
    assert scene.read_bytes() == before
    rows = [json.loads(row) for row in (logo.qa / "rounds.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["result"] == "needs_diagnosis"


def test_owner_rejection_vetoes_model_pass_without_relabeling_answers(tmp_path):
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
                    "craftsmanship": "fail",
                    "brief_fit": "fail",
                    "preference": "unranked",
                    "statement": "both below floor",
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
    assert not (logo.ideation / "winner.json").exists()


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
    result = assess(
        logo, brief, cid, logo.concept(cid) / "final.png", InspectViews(), stage="final"
    )
    assert result["status"] == "pass"
