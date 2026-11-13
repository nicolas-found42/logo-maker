"""Study delivery and exact-image review without a GPU or live provider."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import anyio
import pytest
from PIL import Image, ImageDraw
from PIL.IcoImagePlugin import IcoImageFile

from logo_maker import eligibility, mcp_server, pipeline, study
from logo_maker.cli import main
from logo_maker.motif import Motif
from logo_maker.paths import LogoDir


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    monkeypatch.setattr(study.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(study.platform, "machine", lambda: "arm64")
    logo = LogoDir(tmp_path)
    logo.brief.write_text(
        'name = "Studio"\nsummary = "Makes signs."\ntone = ["precise"]\n'
        'intended_appearance = "Satin painted plate"\n'
    )
    return logo


def test_study_authoring_stops_and_host_guard(campaign, monkeypatch, capsys):
    target = str(campaign.root)
    assert main(["study", target, "--concept", "plate", "--preview"]) == 3
    assert "motif.py" in capsys.readouterr().err
    result = anyio.run(mcp_server.logo_study, target, ["plate"])
    assert result["status"] == "authoring_needed"
    assert "concept.json" in " ".join(result["files"])
    monkeypatch.setattr(study.platform, "machine", lambda: "x86_64")
    assert main(["study", target, "--concept", "plate"]) == 2
    assert "Apple Silicon" in capsys.readouterr().err
    assert not (campaign.root / "studies").exists()


@pytest.fixture
def delivered(campaign, monkeypatch):
    for name, color in (("craft", "blue"), ("holdout", "red")):
        Image.new("RGB", (64, 64), color).save(campaign.inputs / f"{name}.png")
    for cid in ("plate", "collar"):
        folder = campaign.concept(cid)
        (folder / "concept.json").write_text(json.dumps({"description": cid, "label": cid}))
        art = Motif()
        art.add("mark", art.circle(500, 500, 280), fill="#B70611")
        art.save(folder)
        if cid == "plate":
            dark = Motif()
            dark.add("mark", dark.circle(500, 500, 280), fill="#F2EBDD")
            dark.save(campaign.root / "dark-work").replace(folder / "compact-dark.svg")
        (folder / "source.blend").write_bytes(b"fixture scene")
        (folder / "references.json").write_text(
            json.dumps(
                {
                    "photos": [
                        {
                            "path": f"inputs/{path}.png",
                            "url": f"https://example.com/{path}",
                            "coverage": path,
                            "note": "Satin surface and rounded edge",
                            "use": role,
                        }
                        for path, role in (
                            ("craft", "craft"),
                            ("craft", "holdout"),
                            ("holdout", "holdout"),
                        )
                    ]
                }
            )
        )

    def render(source, compiled, output, name, budget, **kwargs):
        size = 2000 if name == "hero-transparent" else 128
        canvas = Image.new("RGBA", (size, size))
        ImageDraw.Draw(canvas).ellipse(
            (size // 4, size // 4, 3 * size // 4, 3 * size // 4), fill="red"
        )
        canvas.save(output / f"{name}.png")
        if name == "hero-transparent":
            blend = output / "scene.blend"
            blend.write_bytes(source.read_bytes())
            return {"inputs_sha256": {"editable_scene": sha256(blend.read_bytes()).hexdigest()}}
        return {}

    monkeypatch.setattr(study, "_render", render)
    return study.build(campaign, ["plate", "collar"])


def test_study_archive_matches_manifest_and_compact_icons(campaign, delivered):
    root = delivered["directory"]
    manifest = json.loads(delivered["manifest"].read_text())
    assert set(manifest["concepts"]) == {"plate", "collar"}
    with ZipFile(delivered["archive"]) as archive:
        assert set(archive.namelist()) == {"manifest.json", *manifest["files"]}
        for name, evidence in manifest["files"].items():
            assert sha256(archive.read(name)).hexdigest() == evidence["sha256"]
    assert (root / "plate" / "compact-light-dark.png").is_file()
    assert (root / "plate" / "mark-compact-dark.svg").is_file()
    assert (root / "plate" / "favicon-dark-16.png").is_file()
    assert not (root / "collar" / "mark-compact-dark.svg").exists()
    with Image.open(root / "plate" / "favicon.ico") as ico:
        assert isinstance(ico, IcoImageFile)
        for size in (16, 32, 48):
            with Image.open(root / "plate" / f"favicon-{size}.png") as icon:
                assert ico.ico.getimage((size, size)).tobytes() == icon.tobytes()
    assert pipeline.status(campaign)["studies"][0]["study_id"] == delivered["study_id"]


def test_pending_review_resumes_and_owner_acceptance_is_separate(campaign, delivered, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    study_id = delivered["study_id"]
    archive_sha = sha256(delivered["archive"].read_bytes()).hexdigest()
    pending = study.review(campaign, study_id, accepted=["plate"], owner_note="Use this design")
    assert pending["designs"]["plate"]["visual"]["status"] == "pending"
    assert pending["designs"]["plate"]["owner"]["status"] == "accepted"
    assert pending["designs"]["collar"]["owner"]["status"] == "pending"

    def compare(brief, concept, candidate, client, *, flat_mark, **kwargs):
        assert len(brief.references) == 2
        return {
            "status": "fail",
            "flat_source_sha256": sha256(flat_mark.read_bytes()).hexdigest(),
            "craft": [
                {
                    "candidate_sha256": sha256(candidate.read_bytes()).hexdigest(),
                    "reference_sha256": sha256(ref.path.read_bytes()).hexdigest(),
                }
                for ref in brief.references
            ],
        }

    monkeypatch.setenv("TYPESAFE_API_KEY", "local-test-placeholder")
    monkeypatch.setattr(eligibility, "compare_visual", compare)
    current = study.review(campaign, study_id)
    plate = current["designs"]["plate"]
    assert [row["reference_role"] for row in plate["visual"]["craft"]] == ["craft", "holdout"]
    assert plate["visual"]["status"] == "fail"
    assert plate["owner"] == pending["designs"]["plate"]["owner"]
    assert sha256(delivered["archive"].read_bytes()).hexdigest() == archive_sha


def test_review_rejects_changed_render_and_unnamed_acceptance(campaign, delivered):
    study_id = delivered["study_id"]
    with pytest.raises(ValueError, match="at least one accepted concept"):
        study.review(campaign, study_id, visual=False)
    hero = Path(delivered["directory"]) / "plate" / "hero-transparent.png"
    hero.write_bytes(b"edited")
    with pytest.raises(ValueError, match="study file changed"):
        study.review(campaign, study_id, accepted=["plate"], visual=False)


def test_matched_craft_distinguishes_missing_evidence_and_order_disagreement(tmp_path):
    from logo_maker.brief import Reference

    image = tmp_path / "detail.png"
    Image.new("RGB", (30, 30), "black").save(image)
    match = {
        "candidate_detail": image,
        "reference_detail": image,
        "feature": "edge",
        "view": "front",
        "view_sha256": "bound-render",
        "regions": {},
        "intended_appearances": {},
    }

    class Judge:
        def __init__(self, answers):
            self.answers = iter(answers)

        def ask(self, state, questions, *, label):
            ordered = list(state)[:2]
            assert label.endswith(f"-{ordered[0]}-first")
            return {
                qid: {"noul": probability}
                for qid, probability in zip(questions, next(self.answers), strict=True)
            }

    for answers, expected in (
        ([(0.2, 0.1), (0.1, 0.1)], "missing_evidence"),
        ([(0.9, 0.1), (0.9, 0.9)], "unsettled"),
        ([(0.9, 0.1), (0.9, 0.1)], "fail"),
        ([(0.9, 0.9), (0.9, 0.9)], "pass"),
    ):
        row = eligibility._matched_rows(
            Judge(answers), Reference(image, "craft"), match, "hero", "test"
        )
        assert row["status"] == expected
        assert row["candidate_sha256"] == "hero"
        assert row["view_sha256"] == "bound-render"


def test_adaptation_judges_source_and_delivered_icon(campaign, delivered):
    from logo_maker.brief import Brief, Reference
    from logo_maker.jev.questions import fit_questions

    folder = delivered["directory"] / "plate"
    hero, icon = folder / "hero-transparent.png", folder / "favicon-32.png"
    source = folder / "mark-flat-256.png"
    brief = Brief("Studio", "Makes signs", ("precise",), references=(Reference(hero, "craft"),))

    class Judge:
        def ask(self, state, questions, *, label):
            if label.endswith("-symbol-fit"):
                assert state["identity_source"].path == source
                assert set(questions) == {"source_identity", "adaptation_treatment"}
            elif label.endswith("-technical"):
                assert "identity_source" not in state
            elif label.endswith("-fit"):
                assert "identity_source" not in state
                assert set(questions) == fit_questions().keys() - {
                    "symbol",
                    "brand_specificity",
                    "meaningful_synthesis",
                    "communicative_clarity",
                }
                with Image.open(icon) as actual, Image.open(state["flat_32px"].path) as supplied:
                    assert (
                        actual.tobytes()
                        == supplied.resize((32, 32), Image.Resampling.NEAREST).tobytes()
                    )
            return {qid: {"noul": 0.1 if qid == "source_identity" else 0.9} for qid in questions}

        def ask_many(self, jobs):
            raise AssertionError("this review should use scoped requests")

    result = eligibility.compare_visual(
        brief,
        {},
        hero,
        Judge(),
        label="adaptation",
        flat_mark=icon,
        study_evidence={
            "identity": {"path": source, "note": "Keep the wordmark and change layout"}
        },
    )
    assert result["fit"]["source_identity"] == "fail"
    assert result["status"] == "fail"
