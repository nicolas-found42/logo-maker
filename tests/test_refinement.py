"""Public pipeline resume and evidence contracts, with external rendering/Jev boundaries faked."""

import json

import pytest

from logo_maker import pipeline
from logo_maker.paths import LogoDir


def inline_refinement_workers(monkeypatch):
    """Keep synthetic renderer/client patches in process; real ownership has separate tests."""
    from logo_maker import host, refinement

    original = host.run

    def run(payload, budget, stages):
        if payload["operation"] in {"refinement", "concept_states", "pipeline_inputs"}:
            budget.check()
            with refinement.owned_scope(None):
                return host.main(payload)
        return original(payload, budget, stages)

    monkeypatch.setattr(host, "run", run)


@pytest.fixture(autouse=True)
def synthetic_refinement_workers(monkeypatch):
    inline_refinement_workers(monkeypatch)


def job(tmp_path):
    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Commons")
    logo.brief.write_text(
        'name="Commons"\nsummary="Exchange practical skills"\ntone=["welcoming"]\n'
    )
    cid = "exchange|paper|paper"
    (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": [cid]}))
    folder = logo.concept(cid)
    (folder / "concept.json").write_text(
        json.dumps({"id": cid, "metaphor_text": "Interlocked teaching paths"})
    )
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, cid)
    return logo, cid, folder


def test_refine_requires_construction_intent_before_rendering(tmp_path):
    logo, _, folder = job(tmp_path)
    with pytest.raises(pipeline.AuthoringNeeded, match="construction") as stop:
        pipeline.refine(logo)
    assert folder / "construction.json" in stop.value.files


def refresh_reviews(logo):
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    freeze_for_stage_test(logo)
    for cid in pipeline.shortlist(logo):
        plan_for_stage_test(logo, cid)


def construction(folder):
    (folder / "construction.json").write_text(
        json.dumps(
            {
                "symbol": "Two routes interlock",
                "brand_geometry": "Equal give and receive paths",
                "material_construction": "Paper folds join at a crossing",
                "intended_appearance": "Matte paper with distinct folded planes",
                "disproof": "Flat repeated sheets with no exchange idea",
                "current_description": "Interlocked folded exchange paths",
                "dependencies": [],
            }
        )
    )
    info = json.loads((folder / "concept.json").read_text())
    info["description"] = "Interlocked folded exchange paths"
    (folder / "concept.json").write_text(json.dumps(info))
    (folder / "motif.svg").write_text(
        '<svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg"><path id="mark" fill="#123456" d="M200 200 L800 200 L800 800 L200 800 Z"/></svg>'
    )
    from logo_maker.scene import from_treatment

    (folder / "scene.toml").write_text(
        from_treatment(
            "extruded_solid",
            material_id="clay",
            palette={"primary": "#123456"},
            motif_json={"layers": []},
            seed=42,
        )
    )
    from test_brief_workflow import freeze_for_stage_test, plan_for_stage_test

    logo = LogoDir(folder.parents[1])
    freeze_for_stage_test(logo)
    plan_for_stage_test(logo, info["id"])


def fake_gpu(monkeypatch, image_path=None, *, sampling_qualified=True, custom_scope=False):
    inline_refinement_workers(monkeypatch)
    from PIL import Image

    from logo_maker import render
    from logo_maker.refinement import digest
    from logo_maker.render import RenderResult
    from logo_maker.sampling import Budget

    monkeypatch.setattr(render, "machine_context", lambda *args: {"machine": "offline"})

    def draw(folder, quality="preview", **kw):
        png = folder / f"{quality}.png"
        color = "red" if "fold" in (folder / "scene.toml").read_text() else "blue"
        if image_path is None:
            Image.new("RGBA", (64, 64), color).save(png)
        else:
            import shutil

            shutil.copyfile(image_path, png)
        execution = folder / ".build" / f"{quality}.execution.json"
        execution.parent.mkdir(exist_ok=True)
        execution.write_text(
            json.dumps(
                {
                    "status": "verified",
                    "policy": "metal-gpu-only",
                    "denoiser_effective": {"device_type": "Metal"},
                }
            )
        )
        execution.with_suffix(".log").write_text("GPU runtime evidence")
        if kw.get("budget"):
            kw["budget"].begin_attempt()
        sampling = folder / ".build" / f"{quality}.sampling.json"
        deps = {str(p): digest(p) for p in render.source_files(folder)}
        context = render.machine_context(kw.get("budget") or Budget())
        if custom_scope:
            context["custom_scene_sha256"] = "custom-dependencies-remain-unknown"
        sampling.write_text(
            json.dumps(
                {
                    "published": True,
                    "delivered_sha256": digest(png),
                    "source_key": render.content_key(deps),
                    "dependencies": deps,
                    "execution": str(execution),
                    "execution_sha256": digest(execution),
                    "context": context,
                    "profile": {
                        "state": "qualified" if sampling_qualified else "profile_unqualified"
                    },
                    "outcomes": {
                        "sampling": "profile_baseline" if sampling_qualified else "review_needed"
                    },
                }
            )
        )
        return RenderResult(
            png, folder / "scene.blend", folder / "model.glb", 1, quality, execution, sampling
        )

    monkeypatch.setattr(render, "render", draw)


def test_refine_preserves_old_image_and_demands_new_inspection_after_source_edit(
    tmp_path, monkeypatch
):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect") as stop:
        pipeline.refine(logo)
    first = pipeline.status(logo)["revisions"][cid][-1]
    assert first["image_sha256"]
    inspection = {
        "revision": first["revision"],
        "observations": "Visible flat slabs",
        "user_feedback": "",
        "critiques": [],
    }
    (folder / "inspection.json").write_text(json.dumps(inspection))
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# fold\n")
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    records = pipeline.status(logo)["revisions"][cid]
    assert len(records) == 2
    assert records[0]["image_sha256"] != records[1]["image_sha256"]
    assert records[0]["source_sha256"] != records[1]["source_sha256"]
    assert records[1]["previous"] == first["revision"]
    assert (logo.root / records[0]["image"]).exists()
    assert stop.value.details["dimension"] == "inspection"


class Judge:
    def __init__(self, p=0.95):
        self.p = p
        self.states = []

    def with_budget(self, budget):
        # This fake performs immediate in-memory work; real transports own killable workers.
        budget.check()
        return self

    def ask(self, state, questions, *, label):
        self.states.append(state)
        return {name: {"noul": self.p} for name in questions}

    def ask_many(self, jobs):
        return [self.ask(s, q, label=label) for s, q, label in jobs]


def inspect_current(logo, cid, folder):
    latest = pipeline.status(logo)["revisions"][cid][-1]
    inspection_name = "inspection-final.json" if latest["quality"] == "final" else "inspection.json"
    (folder / inspection_name).write_text(
        json.dumps(
            {
                "revision": latest["revision"],
                "observations": "Plane changes visible along folded paths",
                "user_feedback": "Keep the matte finish",
                "critiques": [],
            }
        )
    )
    return latest


def test_creative_failure_names_dimension_and_requires_agent_reauthoring(tmp_path, monkeypatch):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    judge = Judge(0.1)
    with pytest.raises(pipeline.AuthoringNeeded, match="creative") as stop:
        pipeline.refine(logo, judge)
    assert "craftsmanship" in stop.value.details["verdicts"]
    assert stop.value.details["artifact"].endswith("render.png")
    assert (
        judge.states[0]["construction"]["current_description"]
        == "Interlocked folded exchange paths"
    )
    assert "8192" not in (folder / "scene.toml").read_text()


def test_distinct_structural_revision_resolves_critique_and_counts_separately(
    tmp_path, monkeypatch
):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
        pipeline.refine(logo, Judge())
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# fold\n")
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo, Judge())
    inspect_current(logo, cid, folder)
    result = pipeline.refine(logo, Judge())
    assert result["rendered_variants"] == 2
    assert result["authored_motifs"] == 1
    assert result["text_combinations"] == 0
    assert result["completed_refinement_rounds"] == 1


def test_export_rejects_changed_sources_even_with_done_stage_flags(tmp_path):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    (logo.ideation / "winner.json").write_text(json.dumps({"winner": cid}))
    from logo_maker.runlog import runlog

    runlog(logo.run_json).stage("finalize", "done")
    with pytest.raises(pipeline.AuthoringNeeded, match="stale"):
        pipeline.export(logo)


@pytest.mark.parametrize("edit", ["scene", "description", "brief", "dependency"])
def test_content_edits_revoke_finalist_eligibility_without_mtime_help(tmp_path, edit):
    import os

    from logo_maker import refinement

    logo, _, folder = job(tmp_path)
    construction(folder)
    dependency = folder / "edge-profile.dat"
    dependency.write_text("one")
    intent = json.loads((folder / "construction.json").read_text())
    intent["dependencies"] = ["edge-profile.dat"]
    (folder / "construction.json").write_text(json.dumps(intent))
    data = {"binding": refinement.campaign_key(logo, pipeline.shortlist(logo))}
    target = {
        "scene": folder / "scene.toml",
        "description": folder / "construction.json",
        "brief": logo.brief,
        "dependency": dependency,
    }[edit]
    stamp = target.stat()
    if target.suffix == ".json":
        value = json.loads(target.read_text())
        value["current_description" if edit == "description" else "question_dependency"] = (
            "changed geometry"
        )
        target.write_text(json.dumps(value))
    else:
        with target.open("a") as stream:
            stream.write("\n# changed")
    os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(pipeline.AuthoringNeeded, match=r"stale|update concept"):
        refinement.require_binding(logo, data, "preview")


def test_technical_edge_failures_preserve_explicit_sampling_and_return_diagnosis(
    tmp_path, monkeypatch
):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    import tomlkit

    doc = tomlkit.parse((folder / "scene.toml").read_text())
    doc["render"]["max_samples"] = 512
    doc["render"]["adaptive_threshold"] = 0.02
    (folder / "scene.toml").write_text(tomlkit.dumps(doc))
    original = (folder / "scene.toml").read_bytes()
    with pytest.raises(pipeline.AuthoringNeeded, match="diagnosis") as stop:
        pipeline.qa_concept(logo, cid, Judge(0.1), pipeline.Brand({"primary": "#123456"}, {}))
    assert stop.value.details["diagnosis"]["sampling_action"] == "none"
    assert (folder / "scene.toml").read_bytes() == original


def test_alternate_renderer_is_rejected_before_gpu_work(tmp_path, monkeypatch):
    from logo_maker.proc import ToolError

    logo, _, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    (folder / "scene.toml").write_text(
        (folder / "scene.toml").read_text().replace('renderer = "cycles"', 'renderer = "luxcore"')
    )
    with pytest.raises(ToolError, match="Metal GPU-only"):
        pipeline.refine(logo, Judge())
    assert not (folder / "preview.png").exists()


def test_refinement_keeps_earlier_distinct_alternative_after_a_small_followup(
    tmp_path, monkeypatch
):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    for note in ("", "# fold", "# small followup"):
        if note:
            with (folder / "scene.toml").open("a") as stream:
                stream.write("\n" + note)
        with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
            pipeline.refine(logo, Judge())
        inspect_current(logo, cid, folder)
        if not note:
            with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
                pipeline.refine(logo, Judge())
        else:
            result = pipeline.refine(logo, Judge())
    assert result["rendered_variants"] == 3


def test_retained_image_tampering_never_reuses_a_cached_judgment(tmp_path, monkeypatch):
    from logo_maker.proc import ToolError

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    record = inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
        pipeline.refine(logo, Judge())
    (logo.root / record["image"]).write_bytes(b"changed retained image")
    with pytest.raises(ToolError, match="retained revision image changed"):
        pipeline.refine(logo, Judge())


def test_direct_finalize_rechecks_sources_after_valid_preview_receipt(tmp_path):
    from logo_maker import refinement

    logo, cid, folder = job(tmp_path)
    construction(folder)
    (logo.ideation / "finalists.json").write_text(
        json.dumps({"ids": [cid], "binding": refinement.campaign_key(logo, [cid])})
    )
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# revised structure")
    with pytest.raises(pipeline.AuthoringNeeded, match="stale preview"):
        pipeline.finalize(logo, Judge())


def test_uncertain_dimensions_request_inspection_or_direction_without_forcing_an_edit(
    tmp_path, monkeypatch
):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded) as stop:
        pipeline.refine(logo, Judge(0.5))
    assert all(
        value["status"] == "unsettled"
        for value in stop.value.details["required_dimensions"].values()
    )
    assert "owner direction" in stop.value.details["next_comparison"]


def test_final_revision_cannot_pass_with_unresolved_comparative_critique(tmp_path, monkeypatch):
    from logo_maker.paths import REPO_ROOT

    class UnresolvedComparison(Judge):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            if "critique_resolved" in answers:
                answers["critique_resolved"]["noul"] = 0.1
            return answers

    logo, cid, folder = job(tmp_path)
    construction(folder)
    refresh_reviews(logo)
    pipeline.motifs(logo)
    fake_gpu(monkeypatch, REPO_ROOT / "examples/chief-of-staff/reference-256.png")
    judge = UnresolvedComparison()
    brand = pipeline.Brand({"primary": "#123456"}, {})
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.qa_concept(logo, cid, judge, brand)
    inspect_current(logo, cid, folder)
    assert pipeline.qa_concept(logo, cid, judge, brand)["result"] == "pass"
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# substantive final revision")
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.qa_concept(logo, cid, judge, brand)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="comparison"):
        pipeline.qa_concept(logo, cid, judge, brand)


def test_current_owner_direction_invalidates_unresolved_comparison(tmp_path, monkeypatch):
    class DirectionJudge(Judge):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            if "critique_resolved" in answers:
                direction = (
                    state.get("current_review", {}).get("inspection", {}).get("user_feedback", "")
                )
                answers["critique_resolved"]["noul"] = 0.95 if "Owner prefers" in direction else 0.1
            return answers

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    judge = DirectionJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
        pipeline.refine(logo, judge)
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# fold")
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo, judge)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="comparison"):
        pipeline.refine(logo, judge)
    inspection = json.loads((folder / "inspection.json").read_text())
    inspection["user_feedback"] = (
        "Owner prefers this restrained finish between successful treatments"
    )
    (folder / "inspection.json").write_text(json.dumps(inspection))
    assert pipeline.refine(logo, judge)["rendered_variants"] == 2


def test_creative_final_cannot_bypass_unqualified_sampling(tmp_path, monkeypatch):
    from logo_maker.paths import REPO_ROOT

    logo, cid, folder = job(tmp_path)
    construction(folder)
    refresh_reviews(logo)
    pipeline.motifs(logo)
    fake_gpu(
        monkeypatch,
        REPO_ROOT / "examples/chief-of-staff/reference-256.png",
        sampling_qualified=False,
    )
    judge = Judge()
    with pytest.raises(pipeline.AuthoringNeeded, match="sampling qualification") as stop:
        pipeline.qa_concept(logo, cid, judge, pipeline.Brand({"primary": "#123456"}, {}))
    assert stop.value.details["dimension"] == "sampling_profile"
    assert all("construction" not in state for state in judge.states)


def test_sampling_budget_failure_stays_operational_and_preserves_prior_image(tmp_path, monkeypatch):
    from logo_maker.sampling import Budget, SamplingLimit

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    prior = folder / "final.png"
    prior.write_bytes(b"usable prior image")
    clock = [0.0]
    budget = Budget(wall_seconds=1, clock=lambda: clock[0])
    clock[0] = 2.0
    with pytest.raises(SamplingLimit, match="time_limit"):
        pipeline.qa_concept(logo, cid, Judge(), pipeline.Brand({}, {}), budget=budget)
    assert prior.read_bytes() == b"usable prior image"


def test_machine_context_drift_invalidates_creative_render_reuse(tmp_path, monkeypatch):
    from logo_maker import render

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    monkeypatch.setattr(
        render, "machine_context", lambda *args: {"machine": "changed-device-build"}
    )
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo, Judge())
    assert pipeline.status(logo)["rendered_variants"] == 2


def test_source_edit_during_judgment_cannot_become_current_eligibility(tmp_path, monkeypatch):
    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)

    class EditingJudge(Judge):
        def ask(self, state, questions, *, label):
            if "craftsmanship" in questions:
                with (folder / "scene.toml").open("a") as stream:
                    stream.write("\n# edit while judgment request is in flight")
            return super().ask(state, questions, label=label)

    with pytest.raises(pipeline.AuthoringNeeded, match=r"changed (while|during).*judging"):
        pipeline.refine(logo, EditingJudge())
    assert not (logo.ideation / "finalists.json").exists()


@pytest.mark.parametrize("edit", ["scene", "inspection"])
def test_final_tournament_cannot_approve_in_flight_edits(tmp_path, monkeypatch, edit):
    import shutil

    from logo_maker import refinement
    from logo_maker.paths import REPO_ROOT

    logo, cid, folder = job(tmp_path)
    with logo.brief.open("a") as stream:
        stream.write('\n[palette]\nprimary="#123456"\n[fonts]\ndisplay="Manrope:wght=700"\n')
    construction(folder)
    other = "other|paper|paper"
    other_folder = logo.concept(other)
    shutil.copytree(folder, other_folder, dirs_exist_ok=True)
    info = json.loads((other_folder / "concept.json").read_text())
    info["id"] = other
    (other_folder / "concept.json").write_text(json.dumps(info))
    (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": [cid, other]}))
    refresh_reviews(logo)
    pipeline.motifs(logo)
    reference = REPO_ROOT / "examples/chief-of-staff/reference-256.png"
    fake_gpu(monkeypatch, reference)
    brand = pipeline.Brand({"primary": "#123456"}, {"display": "Manrope:wght=700"})
    for current_id in (cid, other):
        current_folder = logo.concept(current_id)
        shutil.copyfile(reference, current_folder / "preview.png")
        with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
            pipeline.qa_concept(logo, current_id, Judge(), brand)
        inspect_current(logo, current_id, current_folder)
        assert pipeline.qa_concept(logo, current_id, Judge(), brand)["result"] == "pass"
    (logo.ideation / "finalists.json").write_text(
        json.dumps({"ids": [cid, other], "binding": refinement.campaign_key(logo, [cid, other])})
    )
    winner = logo.ideation / "winner.json"
    winner.write_text('{"winner":"approved-prior"}')

    class EditingTournament(Judge):
        edited = False

        def ask(self, state, questions, *, label):
            if "preferred_mark" in questions:
                if not self.edited:
                    self.edited = True
                    if edit == "scene":
                        with (folder / "scene.toml").open("a") as stream:
                            stream.write("\n# source edit during final tournament")
                    else:
                        path = folder / "inspection-final.json"
                        data = json.loads(path.read_text())
                        data["critiques"] = [
                            {
                                "kind": "preference",
                                "dimension": "finish",
                                "artifact": "final.png",
                                "evidence": "New unresolved owner direction",
                                "action": "Review direction",
                                "comparison": "Compare finishes",
                                "resolved": False,
                            }
                        ]
                        path.write_text(json.dumps(data))
                return {
                    "preferred_mark": {
                        "choice": next(iter(questions["preferred_mark"]["criteria"]))
                    }
                }
            return super().ask(state, questions, label=label)

    monkeypatch.setattr("logo_maker.eligibility.assess", lambda *a, **kw: {"status": "pass"})
    monkeypatch.setattr("logo_maker.eligibility.require_current", lambda *a, **kw: None)
    with pytest.raises(pipeline.AuthoringNeeded, match=r"changed (while|during).*judging"):
        pipeline.finalize(logo, EditingTournament())
    assert winner.read_text() == '{"winner":"approved-prior"}'


def test_custom_preview_can_be_inspected_without_qualifying_production_reuse(tmp_path, monkeypatch):
    from logo_maker import render

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch, custom_scope=True, sampling_qualified=False)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
        pipeline.refine(logo, Judge())
    assert pipeline.status(logo)["rendered_variants"] == 1
    assert not render.artifact_current(folder, "preview", check_machine=False)


@pytest.mark.parametrize("identity", ["model", "url"])
def test_budget_view_preserves_judge_identity_for_creative_and_comparison_caches(
    tmp_path, monkeypatch, identity
):
    from logo_maker.jev.client import JevClient
    from logo_maker.sampling import Budget

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    with pytest.raises(pipeline.AuthoringNeeded, match="alternatives"):
        pipeline.refine(logo, Judge())
    with (folder / "scene.toml").open("a") as stream:
        stream.write("\n# fold: structurally distinct second fixture")
    with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
        pipeline.refine(logo)
    inspect_current(logo, cid, folder)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    client = JevClient(logo)
    labels = []

    def immediate_provider(state, questions, *, label, budget=None):
        assert budget is not None, "creative/comparison request lost its explicit deadline"
        budget.check()
        labels.append(label)
        return Judge().ask(state, questions, label=label)

    monkeypatch.setattr(client, "ask", immediate_provider)
    budget = Budget()
    try:
        assert pipeline.refine(logo, client, budget=budget)["rendered_variants"] == 2
        assert any(label.startswith("creative-") for label in labels)
        assert any(label.startswith("compare-") for label in labels)
        labels.clear()
        pipeline.refine(logo, client, budget=budget)
        assert not labels, "unchanged bounded judge should reuse its current judgments"
        setattr(client, identity, getattr(client, identity) + "-other-judge")
        pipeline.refine(logo, client, budget=budget)
        assert any(label.startswith("creative-") for label in labels)
        assert any(label.startswith("compare-") for label in labels)
    finally:
        if client._http is not None:
            client._http.close()


@pytest.mark.parametrize("stage", ["refine", "qa"])
def test_bounded_creative_entry_rejects_clients_without_budget_binding(
    tmp_path, monkeypatch, stage
):
    from logo_maker.proc import ToolError
    from logo_maker.sampling import Budget

    logo, cid, folder = job(tmp_path)
    construction(folder)
    fake_gpu(monkeypatch)
    if stage == "refine":
        with pytest.raises(pipeline.AuthoringNeeded, match="inspect"):
            pipeline.refine(logo)
        inspect_current(logo, cid, folder)
    if stage == "refine":
        with pytest.raises(ToolError, match="budget_conflict"):
            pipeline.refine(logo, object(), budget=Budget())
    else:
        with pytest.raises(ToolError, match="budget_conflict"):
            pipeline.qa_concept(logo, cid, object(), pipeline.Brand({}, {}), budget=Budget())
