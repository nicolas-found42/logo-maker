"""Sampling decisions are image-bound technical outcomes, never craft judgments."""

import hashlib
import json

import pytest

from logo_maker import host
from logo_maker.sampling import Budget, Settings, decide


@pytest.mark.parametrize("explicit", [False, True])
def test_owned_controls_bind_review_bytes_and_preserve_explicit_settings(tmp_path, explicit):
    records = tmp_path / "records"
    records.mkdir()
    evidence = records / "review.json"
    evidence.write_text('{"sampling":"approved"}')
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    context = {"stage": "final"}
    profile = {
        "schema": 1,
        "context": context,
        "owner_review": "approved",
        "coverage": ["matte", "metal", "glass", "dark", "typography", "alpha"],
        "cases": [
            {"role": role, "evidence": {"path": "review.json", "sha256": digest}}
            for role in ("positive", "degraded", "held_out")
        ],
        "job_costs": [{"baseline_seconds": 40, "candidate_seconds": 35}],
        "settings": Settings(cap=128, minimum=16, seed=24).quality(),
    }
    profile_path = records / "profile.json"
    profile_path.write_text(json.dumps(profile))
    diagnosis_path = tmp_path / "diagnosis.json"
    diagnosis = {"kind": "sampling_noise", "image_sha256": "candidate"}
    diagnosis_path.write_text(json.dumps(diagnosis))
    quality = Settings(cap=512, seed=42, adaptive=not explicit).quality()
    quality["overrides"] = {"adaptive": False} if explicit else {}
    stages = []

    result = host.run(
        {
            "operation": "sampling_controls",
            "concept_dir": str(tmp_path),
            "config": {"profile": "records/profile.json", "diagnosis": str(diagnosis_path)},
            "context": context,
            "quality": quality,
        },
        Budget(wall_seconds=8),
        stages,
    )

    assert result["profile"][0] == ("override_conflict" if explicit else "qualified")
    assert result["quality"] == {
        **profile["settings"],
        "adaptive": not explicit,
        "seed": 42,
        "overrides": quality["overrides"],
    }
    assert result["diagnosis"] == diagnosis
    assert result["hashes"] == {
        str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (profile_path, evidence, diagnosis_path)
    }
    assert [(stage["operation"], stage["status"]) for stage in stages] == [
        ("sampling_controls", "completed")
    ]


def test_cap_limited_noise_changes_only_cap():
    current = Settings(cap=4096, threshold=0.01, minimum=0, seed=42, adaptive=True)
    diagnosis = {
        "kind": "sampling_noise",
        "region": "foreground",
        "independent_seeds": [42, 43],
        "noisy_and_denoised_reviewed": True,
        "source_key": "source-42",
        "image_sha256": "image-42",
        "basis": "retained shadow crops show stochastic grain, not missing geometry",
    }
    decision = decide(
        current,
        diagnosis,
        source_key="source-42",
        image_sha256="image-42",
        diagnostics={"status": "available", "regions": {"foreground": {"near_cap_fraction": 0.4}}},
        overrides={},
        attempts_left=1,
        seconds_left=100,
        estimated_seconds=30,
    )
    assert decision.state == "compare"
    assert decision.settings == Settings(
        cap=8192, threshold=0.01, minimum=0, seed=42, adaptive=True
    )


def test_non_sampling_and_unbound_evidence_never_escalate():
    current = Settings(seed=42)
    common: dict = {
        "source_key": "s",
        "image_sha256": "i",
        "diagnostics": {},
        "overrides": {},
        "attempts_left": 2,
        "seconds_left": 100,
        "estimated_seconds": 10,
    }
    assert decide(current, None, **common).state == "unknown"
    for kind in (
        "geometry",
        "typography",
        "denoiser_detail_loss",
        "alpha",
        "resolution",
        "filtering",
    ):
        evidence = {"kind": kind, "source_key": "s", "image_sha256": "i"}
        assert decide(current, evidence, **common).state == "refinement_needed"
        evidence["source_key"] = "old-seed-or-source"
        assert decide(current, evidence, **common).state == "unknown"


def test_below_cap_noise_overrides_and_budget_are_distinct():
    current = Settings(seed=42)
    evidence = {
        "kind": "sampling_noise",
        "region": "foreground",
        "source_key": "s",
        "image_sha256": "i",
        "independent_seeds": [42, 43],
        "noisy_and_denoised_reviewed": True,
        "basis": "crops",
    }
    common: dict = {
        "source_key": "s",
        "image_sha256": "i",
        "diagnostics": {"status": "available", "regions": {"foreground": {"near_cap_fraction": 0}}},
        "overrides": {},
        "attempts_left": 1,
        "seconds_left": 100,
        "estimated_seconds": 30,
    }
    result = decide(current, evidence, **common)
    assert result.settings == Settings(cap=4096, threshold=0.005, seed=42)
    common["overrides"] = {"adaptive_threshold": 0.01}
    assert decide(current, evidence, **common).state == "override_conflict"
    common["overrides"] = {}
    common["attempts_left"] = 0
    assert decide(current, evidence, **common).state == "attempt_limit"
    common["attempts_left"] = 1
    common["seconds_left"] = 20
    assert decide(current, evidence, **common).state == "time_limit"
    common["seconds_left"] = 100
    common["diagnostics"] = {}
    assert decide(current, evidence, **common).state == "unknown"
    evidence["independent_seeds"] = [42, 42]
    assert decide(current, evidence, **common).state == "unknown"


def test_profile_requires_matching_environment_scope_and_retained_owner_controls(tmp_path):
    from logo_maker.sampling import qualify_profile

    context = {
        "machine": "M5 Pro",
        "build": "bpy-hash",
        "oidn_library_sha256": "binary-hash",
        "resolution": 4000,
        "stage": "final",
        "settings_key": "settings-hash",
    }
    assert qualify_profile(None, context)[0] == "profile_unqualified"
    profile = {
        "schema": 1,
        "context": context,
        "settings": Settings().quality(),
        "owner_review": "pending",
        "cases": [],
    }
    assert qualify_profile(profile, context)[0] == "profile_unqualified"
    asset = tmp_path / "owner-review.json"
    asset.write_text('{"craft": "pass", "sampling": "pass"}')
    import hashlib

    review = {"path": str(asset), "sha256": hashlib.sha256(asset.read_bytes()).hexdigest()}
    profile.update(
        owner_review="approved",
        cases=[
            {"role": "positive", "evidence": review},
            {"role": "degraded", "evidence": review},
            {"role": "held_out", "evidence": review},
        ],
        job_costs=[{"baseline_seconds": 40, "candidate_seconds": 35}],
        coverage=["matte", "metal", "glass", "dark", "typography", "alpha"],
    )
    assert qualify_profile(profile, context)[0] == "qualified"
    assert qualify_profile(profile, {**context, "build": "updated-bpy"})[0] == "profile_stale"
    asset.write_text("changed review")
    assert qualify_profile(profile, context)[0] == "profile_unqualified"


def test_job_deadline_and_attempts_include_failed_work():
    import pytest

    from logo_maker.sampling import Budget, SamplingLimit

    clock = [10.0]
    budget = Budget(wall_seconds=20, attempt_limit=2, clock=lambda: clock[0])
    assert budget.begin_attempt() == 1
    clock[0] = 25
    assert budget.remaining == 5
    assert budget.begin_attempt() == 2
    with pytest.raises(SamplingLimit, match="attempt_limit"):
        budget.begin_attempt()
    clock[0] = 31
    with pytest.raises(SamplingLimit, match="time_limit"):
        budget.check()


def test_profile_transfer_is_limited_to_reviewed_materials():
    from logo_maker.sampling import qualify_profile

    context = {"build": "same", "material_presets": ["clear_glass"]}
    profile = {"schema": 1, "context": {"build": "same"}, "material_presets": ["matte_plastic"]}
    assert qualify_profile(profile, context)[0] == "profile_out_of_scope"


def test_custom_bpy_cannot_qualify_from_source_hash_alone():
    from logo_maker.sampling import qualify_profile

    context = {"build": "same", "custom_scene_sha256": "authored-source"}
    profile = {
        "schema": 1,
        "context": {"build": "same"},
        "custom_scenes_sha256": ["authored-source"],
    }
    state, reason = qualify_profile(profile, context)
    assert state == "profile_out_of_scope"
    assert "dependenc" in reason


def test_noise_below_cap_uses_its_region_not_unrelated_saturated_pixels():
    current = Settings(seed=42)
    diagnosis = {
        "kind": "sampling_noise",
        "source_key": "s",
        "image_sha256": "i",
        "independent_seeds": [42, 43],
        "noisy_and_denoised_reviewed": True,
        "basis": "grain only in reviewed tile",
        "region": "tile_1_1",
    }
    result = decide(
        current,
        diagnosis,
        source_key="s",
        image_sha256="i",
        diagnostics={
            "status": "available",
            "regions": {
                "foreground": {"near_cap_fraction": 0.4},
                "tile_1_1": {"near_cap_fraction": 0.0},
            },
        },
        overrides={},
        attempts_left=1,
        seconds_left=100,
        estimated_seconds=20,
    )
    assert result.settings == Settings(cap=4096, threshold=0.005, seed=42)
