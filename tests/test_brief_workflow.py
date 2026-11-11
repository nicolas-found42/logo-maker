"""Brief creation through public pipeline boundaries; no provider or GPU in offline tests."""

import json

import pytest

from logo_maker import pipeline
from logo_maker.paths import LogoDir


class BriefJudge:
    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.states = []

    def ask(self, state, questions, *, label):
        self.states.append(state)
        return {qid: {"noul": self.overrides.get(qid, 0.9)} for qid in questions}

    def ask_many(self, jobs):
        return [self.ask(state, questions, label=label) for state, questions, label in jobs]


def business_brief(tmp_path):
    logo = LogoDir(tmp_path)
    logo.brief.write_text(
        'name = "Sample"\n'
        'summary = "A repair workshop where neighbors mend their household objects."\n'
        'audience = "Neighbors booking a first repair session"\n'
        'tone = ["careful", "welcoming"]\n'
        'uses = ["app_icon"]\n'
    )
    return logo


def test_missing_evidence_requests_authoring_before_any_judgment(tmp_path):
    logo = business_brief(tmp_path)
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match=r"brief-evidence\.toml") as raised:
        pipeline.review_brief(logo, judge)
    assert logo.root / "brief-evidence.toml" in raised.value.files
    assert (logo.root / "brief-evidence.toml").is_file()
    assert not judge.states
    assert not (logo.ideation / "requirements.json").exists()


def evidence_record(logo):
    (logo.inputs / "project.txt").write_text(
        "Sample is a repair workshop where neighbors mend their household objects."
    )
    (logo.root / "brief-evidence.toml").write_text(
        "schema = 1\n"
        'communication_priority = "A welcoming place to care for objects together"\n'
        'design_latitude = ["palette", "material"]\n'
        '[[sources]]\nid = "project"\nkind = "fixture"\npath = "inputs/project.txt"\n'
        'excerpt = "neighbors mend their household objects"\n'
        '[[facts]]\nid = "activity"\n'
        'claim = "Neighbors mend household objects at the workshop"\n'
        'status = "established"\nsources = ["project"]\nessential = true\n'
        '[[requirements]]\nid = "welcome"\n'
        'claim = "The identity should feel welcoming"\nkind = "communication"\n'
        'origin = "proposal"\npriority = "prefer"\nsources = []\n'
    )


def freeze_for_stage_test(logo):
    """Use the public review with a canned external judgment; does not test semantic quality."""
    from logo_maker.brief import load

    summary = load(logo.brief).summary
    (logo.inputs / "stage-source.txt").write_text(summary)
    (logo.root / "brief-evidence.toml").write_text(
        'schema = 1\ncommunication_priority = "Recognizable identity for the stated service"\n'
        'design_latitude = ["concept construction"]\n'
        '[[sources]]\nid = "fixture"\nkind = "fixture"\npath = "inputs/stage-source.txt"\n'
        f"excerpt = {json.dumps(summary)}\n"
        '[[facts]]\nid = "activity"\n'
        f"claim = {json.dumps(summary)}\n"
        'status = "established"\nsources = ["fixture"]\nessential = true\n'
    )
    return pipeline.review_brief(
        logo, BriefJudge(), revision_reason="Selection fixture input revision"
    )


def plan_for_stage_test(logo, cid):
    """Prepare intent evidence via the public plan review, with a canned external judgment."""
    from logo_maker import briefing

    revision = briefing.current(logo)["requirements_revision"]
    folder = logo.concept(cid)
    if not (folder / "concept.json").exists():
        (folder / "concept.json").write_text(
            json.dumps(
                {
                    "id": cid,
                    "metaphor": "fixture form",
                    "description": "One resolved primary contour",
                }
            )
        )
    (folder / "plan.toml").write_text(
        f'schema = 1\nrequirements_revision = "{revision}"\n'
        'hypothesis = "A recognizable fixture mark"\n'
        'visual_mechanism = "One resolved primary contour"\n'
        "requirement_ids = []\nassumptions = []\n"
        '[[details]]\nfeature = "Primary contour"\npurpose = "Recognition"\n'
        'intended_scale = "Flat and hero"\nconstruction = "Extruded shared motif"\n'
        'deletion_test = "Removing the contour removes recognition"\n'
    )
    return briefing.review_plan(logo, cid, BriefJudge())


def test_review_freezes_supported_requirements_with_open_design_choices(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    judge = BriefJudge()
    record = pipeline.review_brief(logo, judge)
    assert record["status"] == "pass"
    frozen = json.loads((logo.ideation / "requirements.json").read_text())
    assert frozen["requirements_revision"] == record["requirements_revision"]
    assert frozen["state"]["design_latitude"] == ["palette", "material"]
    assert frozen["state"]["requirements"][0]["origin"] == "proposal"
    assert frozen["state"]["business"]["summary"] == (
        "A repair workshop where neighbors mend their household objects."
    )
    assert judge.states
    assert not (logo.ideation / "winner.json").exists()


def test_source_coverage_receives_only_relevant_evidence(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)

    class ScopedJudge(BriefJudge):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            for qid in questions:
                if qid.startswith("source_") and "business" in state:
                    answers[qid] = {"noul": 0.5}
            return answers

    record = pipeline.review_brief(logo, ScopedJudge())
    assert record["status"] == "pass"
    assert record["state"]["design_direction"]["open_choices"] == ["palette", "material"]


def test_authoring_obligation_is_preserved_without_becoming_a_brand_attribute(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    text = "Neighbors mend household objects. Develop more purposeful visual detail."
    (logo.inputs / "project.txt").write_text(text)
    path = logo.root / "brief-evidence.toml"
    source = path.read_text().split("[[requirements]]")[0]
    source = source.replace('kind = "fixture"', 'kind = "owner"').replace(
        'excerpt = "neighbors mend their household objects"', f'excerpt = "{text}"'
    )
    path.write_text(
        source + '\n[[obligations]]\nid = "detail"\nkind = "authoring"\n'
        'claim = "Develop more purposeful visual detail"\norigin = "owner"\n'
        'priority = "must"\nsources = ["project"]\n'
    )

    class ObligationJudge(BriefJudge):
        def ask(self, state, questions, *, label):
            answers = super().ask(state, questions, label=label)
            if "source_project_directions" in questions and not state["recorded_directions"]:
                answers["source_project_directions"] = {"noul": 0.1}
            return answers

    frozen = pipeline.review_brief(logo, ObligationJudge())
    assert frozen["state"]["obligations"][0]["kind"] == "authoring"
    assert frozen["state"]["requirements"] == []


def test_validation_obligation_rejects_duplicate_reference_pixels_before_provider(tmp_path):
    import shutil

    from PIL import Image

    logo = business_brief(tmp_path)
    evidence_record(logo)
    first = logo.inputs / "first.png"
    second = logo.inputs / "second.png"
    Image.new("RGBA", (32, 32), "red").save(first)
    shutil.copyfile(first, second)
    with logo.brief.open("a") as stream:
        for name in ("first.png", "second.png"):
            stream.write(
                f'\n[[references]]\npath = "inputs/{name}"\nuse = "craft"\nnote = "Matte"\n'
            )
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "comparison"\nkind = "validation"\n'
        'claim = "Compare two independent craft images"\norigin = "proposal"\n'
        'priority = "must"\nsources = []\nminimum_references = 2\n'
    )
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="distinct craft reference"):
        pipeline.review_brief(logo, judge)
    assert not judge.states


def test_relative_and_absolute_paths_reuse_the_same_obligation_freeze(tmp_path, monkeypatch):
    import shutil

    folder = tmp_path / "brand"
    folder.mkdir()
    logo = business_brief(folder)
    evidence_record(logo)
    shutil.copyfile(logo.brief, logo.inputs / "earlier.toml")
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "clarify"\nkind = "brief"\n'
        'claim = "Clarify the brief"\norigin = "proposal"\npriority = "must"\n'
        'sources = []\nbaseline = "inputs/earlier.toml"\n'
    )
    monkeypatch.chdir(tmp_path)
    judge = BriefJudge()
    first = pipeline.review_brief(LogoDir(folder.relative_to(tmp_path)), judge)
    count = len(judge.states)
    second = pipeline.review_brief(logo, judge)
    assert first["requirements_revision"] == second["requirements_revision"]
    assert len(judge.states) == count


def test_validation_obligation_cannot_substitute_unrelated_reference_images(tmp_path):
    from PIL import Image

    from logo_maker.eligibility import sha256

    logo = business_brief(tmp_path)
    evidence_record(logo)
    for name, color in (("first", "red"), ("second", "blue"), ("required", "green")):
        Image.new("RGBA", (32, 32), color).save(logo.inputs / f"{name}.png")
    with logo.brief.open("a") as stream:
        for name in ("first", "second"):
            stream.write(
                f'\n[[references]]\npath = "inputs/{name}.png"\nuse = "craft"\nnote = "Matte"\n'
            )
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text() + '\n[[obligations]]\nid = "comparison"\nkind = "validation"\n'
        'claim = "Compare the two required named references"\norigin = "proposal"\n'
        'priority = "must"\nsources = []\nminimum_references = 2\n'
        '[[obligations.expected_references]]\nlabel = "First required reference"\n'
        f'path = "inputs/first.png"\nsha256 = "{sha256(logo.inputs / "first.png")}"\n'
        '[[obligations.expected_references]]\nlabel = "Second required reference"\n'
        f'path = "inputs/required.png"\nsha256 = "{sha256(logo.inputs / "required.png")}"\n'
    )
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="reference identity"):
        pipeline.review_brief(logo, judge)
    assert not judge.states


def test_answer_for_another_request_cannot_overwrite_a_failed_check(tmp_path):
    from logo_maker.jev.client import JevError

    logo = business_brief(tmp_path)
    evidence_record(logo)

    class CrossTalkJudge(BriefJudge):
        def ask_many(self, jobs):
            replies = super().ask_many(jobs)
            replies[-1]["activity"] = {"noul": 0.99}
            return replies

    with pytest.raises(JevError, match="request answer keys"):
        pipeline.review_brief(logo, CrossTalkJudge({"activity": 0.1}))
    assert not (logo.ideation / "requirements.json").exists()


@pytest.mark.parametrize(
    ("fact_status", "expected"),
    [("unknown", "missing_evidence"), ("conflict", "fail"), ("assumption", "unsettled")],
)
def test_required_unresolved_fact_requests_evidence_without_guessing(
    tmp_path, fact_status, expected
):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    path = logo.root / "brief-evidence.toml"
    path.write_text(path.read_text().replace('status = "established"', f'status = "{fact_status}"'))
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="activity"):
        pipeline.review_brief(logo, judge)
    assert not judge.states
    assert not (logo.ideation / "requirements.json").exists()
    review = json.loads((logo.qa / "brief-reviews.jsonl").read_text().splitlines()[-1])
    assert review["status"] == expected


def test_conflicting_fact_is_the_first_consequential_followup(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    path = logo.root / "brief-evidence.toml"
    path.write_text(
        path.read_text().replace('status = "established"', 'status = "unknown"')
        + '\n[[facts]]\nid = "identity"\nclaim = "Two conflicting owner names"\n'
        'status = "conflict"\nessential = true\nsources = []\n'
    )
    with pytest.raises(pipeline.AuthoringNeeded) as raised:
        pipeline.review_brief(logo, BriefJudge())
    assert len(raised.value.questions) == 1
    assert "conflicting" in raised.value.questions[0]
    assert "identity" in raised.value.questions[0]


@pytest.mark.parametrize(
    ("qid", "value", "expected"),
    [("fact_activity", 0.1, "fail"), ("consistent", 0.1, "fail"), ("activity", 0.5, "unsettled")],
)
def test_negative_or_uncertain_judgments_never_freeze(tmp_path, qid, value, expected):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    with pytest.raises(pipeline.AuthoringNeeded, match=qid):
        pipeline.review_brief(logo, BriefJudge({qid: value}))
    assert not (logo.ideation / "requirements.json").exists()
    record = json.loads((logo.qa / "brief-reviews.jsonl").read_text().splitlines()[-1])
    assert record["status"] == expected


@pytest.mark.parametrize("value", [float("nan"), -0.1, 1.1, True, "yes"])
def test_malformed_brief_answers_are_errors(tmp_path, value):
    from logo_maker.jev.client import JevError

    logo = business_brief(tmp_path)
    evidence_record(logo)
    with pytest.raises(JevError, match="brief review failed"):
        pipeline.review_brief(logo, BriefJudge({"activity": value}))
    record = json.loads((logo.qa / "brief-reviews.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "api_error"
    assert not (logo.ideation / "requirements.json").exists()


def test_unchanged_frozen_brief_reuses_its_review(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    judge = BriefJudge()
    first = pipeline.review_brief(logo, judge)
    requests = len(judge.states)
    second = pipeline.review_brief(logo, judge)
    assert second["requirements_revision"] == first["requirements_revision"]
    assert requests > 0
    assert len(judge.states) == requests


def test_modified_frozen_content_cannot_reuse_a_review(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    judge = BriefJudge()
    pipeline.review_brief(logo, judge)
    requests = len(judge.states)
    path = logo.ideation / "requirements.json"
    record = json.loads(path.read_text())
    record["state"]["communication_priority"] = "A different direction"
    path.write_text(json.dumps(record))
    previous = path.read_bytes()
    with pytest.raises(pipeline.AuthoringNeeded, match="requirements record"):
        pipeline.review_brief(logo, judge)
    assert path.read_bytes() == previous
    assert len(judge.states) == requests


def test_missing_frozen_answers_cannot_supply_a_pass(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    judge = BriefJudge()
    pipeline.review_brief(logo, judge)
    requests = len(judge.states)
    path = logo.ideation / "requirements.json"
    record = json.loads(path.read_text())
    record.pop("answers")
    path.write_text(json.dumps(record))
    with pytest.raises(pipeline.AuthoringNeeded, match="requirements record"):
        pipeline.review_brief(logo, judge)
    assert len(judge.states) == requests


def test_changed_source_requires_explicit_reopening_and_preserves_prior_freeze(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    judge = BriefJudge()
    first = pipeline.review_brief(logo, judge)
    requests = len(judge.states)
    frozen = logo.ideation / "requirements.json"
    previous = frozen.read_bytes()
    (logo.inputs / "project.txt").write_text(
        "Sample is a repair workshop where neighbors mend their household objects. Updated project evidence."
    )
    with pytest.raises(pipeline.AuthoringNeeded, match="revision reason"):
        pipeline.review_brief(logo, judge)
    assert frozen.read_bytes() == previous
    assert len(judge.states) == requests
    revised = pipeline.review_brief(logo, judge, revision_reason="New project evidence supplied")
    assert revised["requirements_revision"] != first["requirements_revision"]
    archive = logo.root / "history" / "requirements" / f"{first['requirements_revision']}.json"
    assert archive.read_bytes() == previous


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('kind = "fixture"', 'kind = "untrusted_kind"'),
        ('status = "established"', 'status = "perhaps"'),
        ("essential = true", 'essential = "true"'),
        ('origin = "proposal"', 'origin = "owner"'),
        ('priority = "prefer"', 'priority = "automatic"'),
    ],
)
def test_malformed_provenance_stops_before_provider(tmp_path, before, after):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    path = logo.root / "brief-evidence.toml"
    path.write_text(path.read_text().replace(before, after))
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded):
        pipeline.review_brief(logo, judge)
    assert not judge.states
    assert not (logo.ideation / "requirements.json").exists()
    review = json.loads((logo.qa / "brief-reviews.jsonl").read_text().splitlines()[-1])
    assert review["status"] == "missing_evidence"


def test_source_changed_during_judgment_cannot_be_frozen(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)

    class ChangingJudge(BriefJudge):
        def ask(self, state, questions, *, label):
            (logo.inputs / "project.txt").write_text("The source was replaced during review.")
            return super().ask(state, questions, label=label)

    with pytest.raises(pipeline.AuthoringNeeded, match="changed during"):
        pipeline.review_brief(logo, ChangingJudge())
    assert not (logo.ideation / "requirements.json").exists()


def test_owner_mandate_is_reviewed_separately_from_designer_latitude(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    text = "Neighbors mend household objects. The owner requires an R monogram."
    (logo.inputs / "project.txt").write_text(text)
    evidence = logo.root / "brief-evidence.toml"
    evidence.write_text(
        evidence.read_text()
        .replace('kind = "fixture"', 'kind = "owner"')
        .replace('excerpt = "neighbors mend their household objects"', f'excerpt = "{text}"')
        .replace('origin = "proposal"', 'origin = "owner"')
        .replace('priority = "prefer"', 'priority = "must"')
        .replace("sources = []", 'sources = ["project"]')
        .replace("The identity should feel welcoming", "The identity must use an R monogram")
    )
    judge = BriefJudge({"mandates": 0.1})
    with pytest.raises(pipeline.AuthoringNeeded, match="mandates"):
        pipeline.review_brief(logo, judge)
    assert judge.states[0]["requirements"][0]["origin"] == "owner"
    assert judge.states[0]["design_latitude"] == ["palette", "material"]


@pytest.mark.parametrize("extraction", ["omitted", "recast_as_proposal"])
def test_unrepresented_owner_direction_cannot_freeze(tmp_path, extraction):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    text = "Neighbors mend household objects. The logo must be red."
    (logo.inputs / "project.txt").write_text(text)
    path = logo.root / "brief-evidence.toml"
    source = (
        path.read_text()
        .replace('kind = "fixture"', 'kind = "owner"')
        .replace('excerpt = "neighbors mend their household objects"', f'excerpt = "{text}"')
    )
    if extraction == "omitted":
        source = source.split("[[requirements]]")[0]
    else:
        source = source.replace(
            "The identity should feel welcoming", "The logo must be red"
        ).replace('kind = "communication"', 'kind = "visual"')
    path.write_text(source)
    judge = BriefJudge({"source_project_directions": 0.1})
    with pytest.raises(pipeline.AuthoringNeeded, match="source_project_directions"):
        pipeline.review_brief(logo, judge)
    assert not (logo.ideation / "requirements.json").exists()
    coverage = [state for state in judge.states if "recorded_directions" in state]
    assert coverage
    assert not coverage[0]["recorded_directions"]


def test_brief_review_supplies_reference_roles_and_invalidates_changed_pixels(tmp_path):
    from PIL import Image

    logo = business_brief(tmp_path)
    evidence_record(logo)
    image = logo.inputs / "floor.png"
    Image.new("RGBA", (32, 32), "red").save(image)
    with logo.brief.open("a") as stream:
        stream.write(
            '\n[[references]]\npath = "inputs/floor.png"\nuse = "craft"\nnote = "Matte red"\n'
        )
    judge = BriefJudge()
    first = pipeline.review_brief(logo, judge)
    assert judge.states[0]["design_direction"]["references"][0]["use"] == "craft"
    Image.new("RGBA", (32, 32), "blue").save(image)
    with pytest.raises(pipeline.AuthoringNeeded, match="revision reason"):
        pipeline.review_brief(logo, judge)
    second = pipeline.review_brief(logo, judge, revision_reason="Owner replaced the reference")
    assert second["requirements_revision"] != first["requirements_revision"]


def test_cli_brief_names_missing_evidence_without_needing_provider_access(tmp_path, capsys):
    from logo_maker.cli import main

    business_brief(tmp_path)
    assert main(["brief", str(tmp_path)]) == 3
    assert "brief-evidence.toml" in capsys.readouterr().err


def test_mcp_brief_returns_structured_authoring_work(tmp_path):
    import anyio

    from logo_maker import mcp_server

    business_brief(tmp_path)
    result = anyio.run(mcp_server.logo_brief, str(tmp_path))
    assert result["status"] == "authoring_needed"
    assert str(tmp_path / "brief-evidence.toml") in result["files"]


def test_new_cli_creates_and_names_brief_evidence_work(tmp_path, capsys):
    from logo_maker.cli import main

    assert main(["new", "sample", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "brief-evidence.toml").is_file()
    assert "brief-evidence.toml" in capsys.readouterr().out


@pytest.mark.parametrize(
    "stage", ["intake", "ideate", "motifs", "preview", "finalize", "export", "run", "improve"]
)
def test_public_stages_require_review_and_preserve_existing_exports(tmp_path, stage):
    logo = business_brief(tmp_path)
    exported = logo.exports / "hero-transparent.png"
    exported.write_bytes(b"existing approved output")
    floor = logo.root / "floor"
    floor.mkdir()
    (floor / "hero-transparent.png").write_bytes(b"existing improvement floor")
    fn = getattr(pipeline, stage)
    args = () if stage in {"export", "motifs"} else (BriefJudge(),)
    with pytest.raises(pipeline.AuthoringNeeded) as raised:
        fn(logo, *args)
    assert logo.root / "brief-evidence.toml" in raised.value.files
    assert exported.read_bytes() == b"existing approved output"
    assert (floor / "hero-transparent.png").read_bytes() == b"existing improvement floor"


def test_malformed_frozen_record_is_missing_evidence_not_a_pass(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    (logo.ideation / "requirements.json").write_text("[]")
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="requirements record"):
        pipeline.review_brief(logo, judge)
    assert not judge.states


def test_missing_provider_access_is_retained_as_api_error(tmp_path, monkeypatch):
    from logo_maker.jev.client import JevError

    logo = business_brief(tmp_path)
    evidence_record(logo)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(JevError):
        pipeline.review_brief(logo)
    record = json.loads((logo.qa / "brief-reviews.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "api_error"


def test_mcp_reports_only_consequential_missing_question(tmp_path):
    import anyio

    from logo_maker import mcp_server

    logo = business_brief(tmp_path)
    evidence_record(logo)
    path = logo.root / "brief-evidence.toml"
    path.write_text(path.read_text().replace('status = "established"', 'status = "unknown"'))
    result = anyio.run(mcp_server.logo_brief, str(tmp_path))
    assert result["status"] == "authoring_needed"
    assert len(result["questions"]) == 1
    assert "activity" in result["questions"][0]
    assert "palette" not in result["questions"][0]


def test_preview_requests_concept_plan_before_rendering(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    frozen = pipeline.review_brief(logo, BriefJudge())
    (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": ["shared"]}))
    folder = logo.concept("shared")
    (folder / "concept.json").write_text(json.dumps({"id": "shared", "metaphor": "joined forms"}))
    with pytest.raises(pipeline.AuthoringNeeded, match=r"plan\.toml") as raised:
        pipeline.preview(logo, BriefJudge())
    path = folder / "plan.toml"
    assert path in raised.value.files
    assert path.is_file()
    assert frozen["requirements_revision"] in path.read_text()
    assert not (folder / "preview.png").exists()


def planned_concept(logo):
    frozen = pipeline.review_brief(logo, BriefJudge())
    (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": ["shared"]}))
    folder = logo.concept("shared")
    (folder / "concept.json").write_text(json.dumps({"id": "shared", "metaphor": "joined forms"}))
    (folder / "plan.toml").write_text(
        "schema = 1\n"
        f'requirements_revision = "{frozen["requirements_revision"]}"\n'
        'hypothesis = "Joined forms make collective care tangible"\n'
        'visual_mechanism = "Two complementary contours form one open chamber"\n'
        'requirement_ids = ["welcome"]\nassumptions = ["A shared chamber suggests collective care"]\n'
        '[[details]]\nfeature = "Shared boundary"\n'
        'purpose = "Makes the complementary forms read as one"\n'
        'intended_scale = "Flat and avatar"\n'
        'construction = "Primary contours in the shared motif, extruded without new divisions"\n'
        'deletion_test = "Separating the forms removes the joined chamber"\n'
    )
    return folder


def test_supported_plan_is_reviewed_and_reused_without_claiming_pixel_quality(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    folder = planned_concept(logo)
    judge = BriefJudge()
    first = pipeline.review_plans(logo, judge)["shared"]
    second = pipeline.review_plans(logo, judge)["shared"]
    assert first == second
    assert len(judge.states) == 1
    assert first["status"] == "pass"
    assert judge.states[0]["plan"]["assumptions"] == ["A shared chamber suggests collective care"]
    assert (folder / "plan-review.json").is_file()
    assert not (folder / "preview.png").exists()
    assert not (logo.ideation / "winner.json").exists()


@pytest.mark.parametrize(("value", "expected"), [(0.1, "fail"), (0.5, "unsettled")])
def test_nonpassing_plan_returns_authoring_and_preserves_exports(tmp_path, value, expected):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    folder = planned_concept(logo)
    output = logo.exports / "hero-transparent.png"
    output.write_bytes(b"existing output")
    with pytest.raises(pipeline.AuthoringNeeded, match="plan_construction"):
        pipeline.review_plans(logo, BriefJudge({"plan_construction": value}))
    assert not (folder / "plan-review.json").exists()
    record = json.loads((logo.qa / "plan-reviews.jsonl").read_text().splitlines()[-1])
    assert record["status"] == expected
    assert output.read_bytes() == b"existing output"


def test_invalid_plan_answer_is_recorded_as_api_error(tmp_path):
    from logo_maker.jev.client import JevError

    logo = business_brief(tmp_path)
    evidence_record(logo)
    planned_concept(logo)
    with pytest.raises(JevError, match="plan review failed"):
        pipeline.review_plans(logo, BriefJudge({"plan_construction": float("nan")}))
    record = json.loads((logo.qa / "plan-reviews.jsonl").read_text().splitlines()[-1])
    assert record["status"] == "api_error"


def test_plan_for_old_requirements_stops_before_provider(tmp_path):
    logo = business_brief(tmp_path)
    evidence_record(logo)
    folder = planned_concept(logo)
    path = folder / "plan.toml"
    path.write_text(
        path.read_text().replace('requirements_revision = "', 'requirements_revision = "old-')
    )
    judge = BriefJudge()
    with pytest.raises(pipeline.AuthoringNeeded, match="current requirements"):
        pipeline.review_plans(logo, judge)
    assert not judge.states


def test_cli_plan_requests_named_authoring_work(tmp_path, capsys):
    from logo_maker.cli import main

    business_brief(tmp_path)
    assert main(["plan", str(tmp_path)]) == 3
    assert "brief-evidence.toml" in capsys.readouterr().err


def test_mcp_plan_returns_named_authoring_work(tmp_path):
    import anyio

    from logo_maker import mcp_server

    business_brief(tmp_path)
    result = anyio.run(mcp_server.logo_plan, str(tmp_path))
    assert result["status"] == "authoring_needed"
    assert str(tmp_path / "brief-evidence.toml") in result["files"]


def test_direction_review_excludes_craft_style_but_keeps_inspiration_roles(tmp_path):
    from PIL import Image

    logo = business_brief(tmp_path)
    evidence_record(logo)
    Image.new("RGB", (32, 32), "green").save(logo.inputs / "reference.png")
    with logo.brief.open("a") as handle:
        for role in ("craft", "style", "geometry"):
            handle.write(
                f'\n[[references]]\npath="inputs/reference.png"\nuse="{role}"\nnote="{role} context"\n'
            )

    class RoleJudge(BriefJudge):
        def ask(self, state, questions, *, label):
            if label == "brief-direction-preservation":
                assert {ref["use"] for ref in state["design_direction"]["references"]} == {
                    "style",
                    "geometry",
                }
                assert "craft context" not in json.dumps(state)
            return super().ask(state, questions, label=label)

    review = pipeline.review_brief(logo, RoleJudge())
    assert review["status"] == "pass"
    assert {r["use"] for r in review["state"]["design_direction"]["references"]} == {
        "craft",
        "style",
        "geometry",
    }
