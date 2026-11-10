"""Question truth tables on fixed answer dicts; describe() covers every builder."""

from logo_maker.jev import questions as Q


def _s1(fit, feas, leg):
    return {
        "concept_fit": {"choice": fit},
        "feasible_as_object": {"noul": feas},
        "legible_at_size": {"noul": leg},
    }


def test_noul_bands():
    assert Q.noul_status(0.99) == "yes"
    assert Q.noul_status(0.7) == "yes"
    assert Q.noul_status(0.699) == "unsettled"
    assert Q.noul_status(0.3) == "unsettled"
    assert Q.noul_status(0.299) == "no"
    assert Q.noul_status(0.0) == "no"


def test_stage1_rows():
    assert Q.stage1_decision(_s1("strong_fit", 0.9, 0.8))[0] is True
    assert Q.stage1_decision(_s1("weak_fit", 0.9, 0.8))[0] is True
    assert Q.stage1_decision(_s1("off_brand", 0.9, 0.9))[0] is False
    assert Q.stage1_decision(_s1("strong_fit", 0.1, 0.9))[0] is False
    assert Q.stage1_decision(_s1("strong_fit", 0.9, 0.2))[0] is False
    keep, reason = Q.stage1_decision(_s1("strong_fit", 0.5, 0.9))
    assert keep is True
    assert "unsettled" in reason
    keep, _ = Q.stage1_decision(_s1("weak_fit", 0.4, 0.5))
    assert keep is True


def test_stage2_composite():
    base = {"standout": {"score": 2.0}, "double_meaning": {"noul": 0.9}, "memorable": {"noul": 0.9}}
    assert Q.stage2_composite(base) == 3.0
    base["memorable"]["noul"] = 0.05
    assert Q.stage2_composite(base) == 2.5
    base["double_meaning"]["noul"] = 0.5
    assert Q.stage2_composite(base) == 2.25


def test_preview_rows():
    def pv(match, read, levels):
        probs = dict(zip("01234", levels, strict=True))
        score = sum(int(k) * p for k, p in probs.items())
        return {
            "matches_concept": {"noul": match},
            "readable_mark": {"noul": read},
            "appealing": {"score": score, "probabilities": probs},
        }

    pleasant = (0.0, 0.1, 0.5, 0.3, 0.1)
    assert Q.preview_decision(pv(0.9, 0.9, pleasant))[0] is True
    assert Q.preview_decision(pv(0.1, 0.9, pleasant))[0] is False
    assert Q.preview_decision(pv(0.9, 0.2, pleasant))[0] is False
    # The cutoff is on P(>= Pleasant), boundary inclusive.
    assert Q.preview_decision(pv(0.9, 0.9, (0.1, 0.4, 0.4, 0.1, 0.0)))[0] is True
    assert Q.preview_decision(pv(0.9, 0.9, (0.1, 0.41, 0.39, 0.1, 0.0)))[0] is False
    # A compressed-but-pleasant answer (expected 1.8 < 2) still passes.
    assert Q.preview_decision(pv(0.9, 0.9, (0.08, 0.26, 0.47, 0.18, 0.01)))[0] is True
    keep, reason = Q.preview_decision(pv(0.5, 0.9, pleasant))
    assert keep is True
    assert "unsettled" in reason


def test_head_to_head_table():
    assert Q.head_to_head_table("a", "a", "a", "b")[0] == "a"
    assert Q.head_to_head_table("b", "b", "a", "b")[0] == "b"
    winner, reason = Q.head_to_head_table("a", "b", "a", "b")
    assert winner == "split"
    assert "no decision" in reason


def test_qa_status_and_blocking():
    assert Q.qa_status(0.95) == "pass"
    assert Q.qa_status(0.05) == "fail"
    assert Q.qa_status(0.5) == "unsettled"
    assert [Q.qa_blocks(Q.qa_status(p)) for p in (0.29, 0.3, 0.69, 0.7)] == [
        True,
        False,
        False,
        False,
    ]


def test_describe_covers_every_builder():
    from logo_maker import catalog

    treatments = {t: e.description for t, e in catalog.treatments().items()}
    materials = {m: e.description for m, e in catalog.materials().items()}
    built: dict = {}
    built.update(Q.intake_style_questions())
    built.update(Q.intake_color_questions(["#1E4A7A", "#C96F2B"]))
    built.update(Q.palette_questions([{"primary": "#1E4A7A", "background": "#FFFFFF"}]))
    built.update(Q.font_questions([{"display": "Fam:wght=700", "text": "Fam:wght=400"}]))
    built.update(Q.treatment_fit_questions("m", dict(list(treatments.items())[:3])))
    built.update(Q.material_fit_questions(dict(list(materials.items())[:3])))
    built.update(Q.stage1_questions())
    built.update(Q.stage2_questions())
    built.update(Q.head_to_head_questions("n1", "d1", "n2", "d2", "s"))
    built.update(Q.preview_screen_questions())
    built.update(Q.qa_questions())
    ids = {r["question"] for r in Q.describe()}
    dynamic = {qid for qid in built if qid.startswith(("fits_", "brand_"))}
    static = set(built) - dynamic
    assert static <= ids, static - ids
    assert any(q.startswith("fits_") for q in ids)
    assert any(q.startswith("brand_") for q in ids)
    assert {r["type"] for r in Q.describe()} == {"noul", "choice", "score"}


def test_option_names_are_descriptive():
    from logo_maker.jev.questions import font_option_name, palette_option_name

    taken: set[str] = set()
    a = palette_option_name({"primary": "#1E4A7A"}, taken)
    b = palette_option_name({"primary": "#1E4A7A"}, taken)
    assert a != b
    assert "1e4a7a" in a
    assert a[:8] == "palette_"
    f = font_option_name({"display": "Some Family:wght=700"}, set())
    assert "some-family" in f
