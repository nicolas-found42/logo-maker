"""Ideation resume: stored judgments are reused only for the inputs they answered."""

from __future__ import annotations

import json

import pytest

from logo_maker import catalog
from logo_maker.ideate import _read_jsonl, _write_jsonl, run_chain
from logo_maker.paths import LogoDir


class EchoClient:
    """Answers every question with its first option, a high Noul, and a mid score."""

    def __init__(self):
        self.labels: list[str] = []

    def ask(self, state, questions, *, label):
        self.labels.append(label)
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": 0.95}
            elif q["type"] == "choice":
                first = next(iter(q["criteria"]))
                answers[qid] = {"type": "choice", "choice": first, "confidence": 0.9}
            else:
                answers[qid] = {"type": "score", "score": 2.0, "confidence": 0.9}
        return answers

    def ask_many(self, jobs):
        return [self.ask(s, q, label=lab) for s, q, lab in jobs]

    def tournament_calls(self) -> int:
        return sum(label.startswith("tournament-") for label in self.labels)


def _logo(tmp_path, description: str) -> LogoDir:
    logo = LogoDir(tmp_path / "logo")
    logo.ideation.mkdir(parents=True, exist_ok=True)
    logo.brief.write_text('name = "N"\nsummary = "S"\ntone = ["calm"]\n')
    (logo.ideation / "metaphors.toml").write_text(
        "".join(f'[[metaphor]]\nid = "m{i}"\ntext = "{description} m{i}"\n' for i in range(8))
    )
    treatment = next(iter(catalog.treatments()))
    material = next(iter(catalog.materials()))
    rows = [
        {"id": f"{m}|{treatment}|{material}", "metaphor": m, "treatment": treatment,
         "material": material, "scores": {}}
        for m in ("m0", "m1")
    ]  # fmt: skip
    (logo.ideation / "pool.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return logo


def test_tournament_picks_are_reused_only_for_unchanged_inputs(tmp_path):
    logo = _logo(tmp_path, "A wave")
    first = EchoClient()
    run_chain(logo, first)
    assert first.tournament_calls() == 2  # one pair, both option orders

    again = EchoClient()
    run_chain(logo, again)
    assert again.tournament_calls() == 0

    (logo.ideation / "metaphors.toml").write_text(
        (logo.ideation / "metaphors.toml").read_text().replace("A wave", "A flame")
    )
    edited = EchoClient()
    run_chain(logo, edited)
    assert edited.tournament_calls() == 2  # the stored picks judged the old description


def test_jsonl_errors_name_the_file_and_line(tmp_path):
    path = tmp_path / "tournament.jsonl"
    path.write_text('{"a": 1}\n{"a": \n')
    with pytest.raises(ValueError, match=r"tournament\.jsonl:2: not valid JSON"):
        _read_jsonl(path)


def test_jsonl_write_replaces_atomically(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"old": true}\n')
    _write_jsonl(path, [{"new": 1}])
    assert _read_jsonl(path) == [{"new": 1}]
    assert [p.name for p in tmp_path.iterdir()] == ["rows.jsonl"]


@pytest.mark.parametrize(
    ("name", "line", "stage"),
    [
        ("stage1.jsonl", "[1]", "stage1-"),
        ("stage1.jsonl", "null", "stage1-"),
        ("stage1.jsonl", '{"id": "x", "input_hash": "h", "answers": {"a": 1}}', "stage1-"),
        ("stage2.jsonl", "5", "stage2-"),
        ("tournament.jsonl", "[]", "tournament-"),
        ("tournament.jsonl", '{"answers": {"x": 1}}', "tournament-"),
    ],
)
def test_wrong_shaped_stage_rows_are_asked_again(tmp_path, name, line, stage):
    logo = _logo(tmp_path, "A wave")
    run_chain(logo, EchoClient())
    (logo.ideation / name).write_text(line + "\n")
    again = EchoClient()
    run_chain(logo, again)
    assert any(label.startswith(stage) for label in again.labels)
