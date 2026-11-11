"""Stage logic on fixed answers: pool cap, palette/font picks, screen, floor beats."""

import json

import pytest
from PIL import Image as _PILImage

from logo_maker.brief import Brief
from logo_maker.ideate import load_metaphors, select_pool
from logo_maker.intake import pick_fonts, pick_palette
from logo_maker.judging import beats_floor, screen_previews, tiny_version
from logo_maker.paths import LogoDir


class FakeClient:
    """Stub jev: canned answers per label prefix, in call order."""

    def __init__(self, answers: list[dict]):
        self._answers = list(answers)
        self.labels: list[str] = []

    def ask(self, state, questions, *, label):
        self.labels.append(label)
        return self._answers.pop(0)

    def ask_many(self, jobs):
        return [self.ask(s, q, label=lab) for s, q, lab in jobs]


def _brief(**kw):
    base = {"name": "N", "summary": "S", "tone": ("calm",)}
    base.update(kw)
    return Brief(name=base["name"], summary=base["summary"], tone=tuple(base["tone"]))


def _logo(tmp_path, metaphors: int = 8):
    logo = LogoDir(tmp_path / "logo")
    _write_metaphors(logo, [f"m{i:02d}" for i in range(metaphors)])
    return logo


def _write_metaphors(logo, mids):
    (logo.ideation / "metaphors.toml").write_text(
        "".join(f'[[metaphor]]\nid = "{m}"\ntext = "Motif {m}"\n' for m in mids)
    )


def _write_pool(logo, cids):
    import json as _json

    have = {
        line.split('"')[1]
        for line in (logo.ideation / "metaphors.toml").read_text().splitlines()
        if line.startswith("id = ")
    }
    missing = sorted({c.split("|")[0] for c in cids} - have)
    if missing:
        with (logo.ideation / "metaphors.toml").open("a") as fh:
            fh.write("".join(f'[[metaphor]]\nid = "{m}"\ntext = "Motif {m}"\n' for m in missing))
    rows = [
        {
            "id": c,
            "metaphor": c.split("|")[0],
            "treatment": c.split("|")[1],
            "material": c.split("|")[2],
            "scores": {},
        }
        for c in cids
    ]
    (logo.ideation / "pool.jsonl").write_text("\n".join(_json.dumps(r) for r in rows) + "\n")


def test_select_pool_caps_at_1000():
    mids = [f"m{i:02d}" for i in range(40)]
    treats = {f"t{i:02d}": 0.9 - i * 0.01 for i in range(12)}
    mats = {f"mat{i:02d}": 0.9 - i * 0.01 for i in range(19)}
    pool = select_pool(mids, {m: dict(treats) for m in mids}, mats)
    assert len(pool) == 960 <= 1000
    per_m_treats: dict[str, set] = {}
    for mid, tid, _ in pool:
        per_m_treats.setdefault(mid, set()).add(tid)
    assert all(len(v) <= 6 for v in per_m_treats.values())
    assert {mat for _, _, mat in pool} == {"mat00", "mat01", "mat02", "mat03"}


def test_select_pool_trims_to_cap_and_prefers_fit():
    mids = [f"m{i:03d}" for i in range(200)]
    treats = {f"t{i}": 1.0 for i in range(12)}
    mats = {f"m{i}": 1.0 for i in range(19)}
    pool = select_pool(mids, {m: dict(treats) for m in mids}, mats)
    assert len(pool) == 1000


def test_select_pool_tiebreak_is_deterministic():
    mids = ["b", "a"]
    fits = {"a": {"t2": 0.5, "t1": 0.5}, "b": {"t2": 0.5, "t1": 0.5}}
    first = select_pool(mids, fits, {"mat": 1.0})
    assert first == select_pool(mids, fits, {"mat": 1.0})
    assert ("a", "t1", "mat") in first
    assert ("a", "t2", "mat") in first


def test_load_metaphors_validation(tmp_path):
    logo = LogoDir(tmp_path / "bad")
    (logo.ideation).mkdir(parents=True, exist_ok=True)
    (logo.ideation / "metaphors.toml").write_text('[[metaphor]]\nid = "only"\ntext = "One"\n')
    with pytest.raises(ValueError, match="8-40"):
        load_metaphors(logo)
    dup = "".join(f'[[metaphor]]\nid = "same"\ntext = "T{i}"\n' for i in range(8))
    (logo.ideation / "metaphors.toml").write_text(dup)
    with pytest.raises(ValueError, match="duplicate"):
        load_metaphors(logo)
    bad = "".join(f'[[metaphor]]\nid = "Bad ID!"\ntext = "T{i}"\n' for i in range(8))
    (logo.ideation / "metaphors.toml").write_text(bad)
    with pytest.raises(ValueError, match="slug"):
        load_metaphors(logo)


def _palette_answers(pick, fits=0.95):
    return {
        "palette_pick": {"choice": pick, "confidence": 0.9, "probabilities": {pick: 0.9}},
        "any_palette_fits": {"noul": fits},
    }


def test_pick_palette_drops_wcag_failures(tmp_path):
    logo = _logo(tmp_path)
    bad = {"primary": "#FFFFFF", "background": "#FFFFFF", "ink": "#EEEEEE"}
    good1 = {"primary": "#1E3A5F", "background": "#F8F6F1", "accent": "#B3541E"}
    good2 = {"primary": "#2E5E2E", "background": "#F8F6F1", "accent": "#B3541E"}
    from logo_maker.jev.questions import palette_option_name

    taken: set[str] = set()
    names = [
        palette_option_name(bad, taken),
        palette_option_name(good1, taken),
        palette_option_name(good2, taken),
    ]
    client = FakeClient([_palette_answers(names[1])])
    winner = pick_palette(logo, _brief(), [bad, good1, good2], client)
    assert winner == good1
    doc = json.loads((logo.ideation / "palette.json").read_text())
    assert doc["palette"] == good1
    assert doc["dropped_wcag"]


def test_pick_palette_all_fail_raises(tmp_path):
    logo = _logo(tmp_path)
    with pytest.raises(ValueError, match="fails WCAG"):
        pick_palette(
            logo, _brief(), [{"primary": "#FFFFFF", "background": "#FFFFFF"}], FakeClient([])
        )


def test_pick_palette_no_fit_raises(tmp_path):
    logo = _logo(tmp_path)
    good = {"primary": "#1E3A5F", "background": "#F8F6F1"}
    from logo_maker.jev.questions import palette_option_name

    name = palette_option_name(good, set())
    with pytest.raises(ValueError, match="no palette proposal fits"):
        pick_palette(logo, _brief(), [good], FakeClient([_palette_answers(name, fits=0.1)]))


def test_pick_fonts_same_pattern(tmp_path):
    logo = _logo(tmp_path)
    proposals = [
        {"display": "Fam A:wght=700", "text": "Fam A:wght=400"},
        {"display": "Fam B:wght=700", "text": "Fam B:wght=400"},
    ]
    from logo_maker.jev.questions import font_option_name

    taken: set[str] = set()
    names = [font_option_name(p, taken) for p in proposals]
    client = FakeClient(
        [
            {
                "font_pick": {
                    "choice": names[1],
                    "confidence": 0.8,
                    "probabilities": {names[1]: 0.8},
                },
                "any_font_fits": {"noul": 0.85},
            }
        ]
    )
    assert pick_fonts(logo, _brief(), proposals, client) == proposals[1]
    with pytest.raises(ValueError, match="no font proposals"):
        pick_fonts(logo, _brief(), [], FakeClient([]))


def _screen_answers(match, read, appeal):
    low = int(appeal)  # split the mass between the two levels around the expected score
    probabilities = {str(level): 0.0 for level in range(5)}
    probabilities[str(low)] += 1.0 - (appeal - low)
    if appeal > low:
        probabilities[str(low + 1)] += appeal - low
    return {
        "matches_concept": {"noul": match},
        "readable_mark": {"noul": read},
        "appealing": {
            "score": appeal,
            "confidence": 0.7,
            "legend": {"0": "x"},
            "probabilities": probabilities,
        },
    }


def test_screen_previews_rank_and_keep(tmp_path):
    from test_eligibility import attest, qualified_brief, review_inputs

    from logo_maker.jev.questions import craft_questions, fit_questions, technical_questions

    logo = _logo(tmp_path)
    previews = {
        "m|embossed_plate|clay": tmp_path / "a.png",
        "m|medallion|enamel": tmp_path / "b.png",
        "m|tube_lines|neon_glow": tmp_path / "c.png",
        "m|voxel_build|wood": tmp_path / "d.png",
    }
    _write_pool(logo, list(previews))
    for p in previews.values():
        p.parent.mkdir(exist_ok=True)
        _PILImage.new("RGB", (32, 32), (10, 20, 30)).save(p)
    previews = {cid: logo.concept(cid) / "preview.png" for cid in previews}
    for p in previews.values():
        _PILImage.new("RGB", (32, 32), (10, 20, 30)).save(p)
        (p.parent / "motif.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path id="mark" fill="#646464" d="M250 250 L750 250 L750 750 L250 750 Z"/></svg>'
        )
        attest(p.parent, "preview")
    eligibility = [
        {qid: {"noul": 0.9} for qid in craft_questions()},
        {qid: {"noul": 0.9} for qid in craft_questions()},
        {"symbol": {"noul": 0.9}},
        {qid: {"noul": 0.9} for qid in fit_questions() if qid != "symbol"},
        {qid: {"noul": 0.9} for qid in technical_questions()},
    ]
    client = FakeClient(
        eligibility * len(previews)
        + [
            _screen_answers(0.9, 0.9, 2.5),
            _screen_answers(0.9, 0.9, 3.5),
            _screen_answers(0.1, 0.9, 4.0),
            _screen_answers(0.9, 0.9, 1.0),
        ]
    )
    brief = qualified_brief(tmp_path / "a.png")
    for cid in previews:
        review_inputs(logo, cid, brief)
    for path in previews.values():
        attest(path.parent, "preview")
    finalists = screen_previews(logo, brief, previews, client, keep=2)
    assert finalists == ["m|medallion|enamel", "m|embossed_plate|clay"]
    doc = json.loads((logo.ideation / "finalists.json").read_text())
    assert doc["ids"] == finalists


def test_screen_previews_empty_raises(tmp_path):
    logo = _logo(tmp_path)
    p = tmp_path / "a.png"
    _PILImage.new("RGB", (16, 16), (1, 2, 3)).save(p)
    _write_pool(logo, ["m|embossed_plate|clay"])
    with pytest.raises(ValueError, match="no preview survived"):
        screen_previews(
            logo,
            _brief(),
            {"m|embossed_plate|clay": p},
            FakeClient([_screen_answers(0.1, 0.1, 0.5)]),
        )


def test_beats_floor_table(tmp_path):
    logo = _logo(tmp_path)
    cand, floor = tmp_path / "c.png", tmp_path / "f.png"
    for p in (cand, floor):
        _PILImage.new("RGB", (16, 16), (9, 9, 9)).save(p)

    def hb(pick):
        return {"preferred_mark": {"choice": pick, "confidence": 0.9, "probabilities": {pick: 0.9}}}

    beats, info = beats_floor(
        logo, _brief(), cand, floor, FakeClient([hb("candidate"), hb("candidate")])
    )
    assert beats is True
    assert info["winner"] == "candidate"
    beats, info = beats_floor(logo, _brief(), cand, floor, FakeClient([hb("floor"), hb("floor")]))
    assert beats is False
    beats, info = beats_floor(
        logo, _brief(), cand, floor, FakeClient([hb("candidate"), hb("floor")])
    )
    assert beats is False
    assert info["winner"] == "split"


def test_tiny_version_nearest(tmp_path):
    src = tmp_path / "final.png"
    _PILImage.new("RGB", (200, 200), (200, 30, 30)).save(src)
    dest = tmp_path / "tiny.png"
    tiny_version(src, dest)
    assert _PILImage.open(dest).size == (256, 256)
