"""Judging after authoring: preview screen, final QA, winner tournament, floor beats.

Preview and final tournaments both use pairwise Choices with descriptively
named options, asked in both orders; splits never count as wins. QA returns a
`Verdict` per check so the finalize loop knows exactly what failed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image as _PILImage

from logo_maker.brief import Brief, load
from logo_maker.jev.client import Image, JevAsker
from logo_maker.jev.questions import (
    PREVIEW_MIN_PLEASANT,
    QA_CHECK_SPECS,
    concept_state,
    head_to_head_questions,
    head_to_head_table,
    preview_decision,
    preview_screen_questions,
    qa_questions,
    qa_status,
)
from logo_maker.paths import LogoDir, concept_slug
from logo_maker.sampling import Budget

#: 32 px test size, upscaled with nearest-neighbor so pixels stay honest.
TINY_PX = 32
TINY_VIEW_PX = 256


@dataclass(frozen=True)
class Verdict:
    check: str
    status: str  # 'pass' | 'fail' | 'unsettled'
    p: float


def _image_state(brief: Brief, extra: dict[str, Any]) -> dict[str, Any]:
    """Brief plus named extras (concept ids, image refs); no empty values."""
    return {"brief": brief.as_state(), **extra}


def _concept_states(logo: LogoDir, brief: Brief) -> dict[str, dict[str, Any]]:
    """Use current authored intent; the text pool remains historical ideation."""
    from logo_maker.pipeline import shortlist

    states = {}
    ids = shortlist(logo) if (logo.ideation / "shortlist.json").exists() else []
    for cid in ids:
        folder = logo.concept(cid)
        path = folder / "construction.json"
        if path.exists():
            construction = json.loads(path.read_text())
            info = json.loads((folder / "concept.json").read_text())
            states[cid] = {
                "brief": brief.as_state(),
                "concept": construction["current_description"],
                "construction": construction,
                "authored_concept": {
                    "id": info["id"],
                    "description": construction["current_description"],
                },
            }
    # Legacy direct judging callers without authored files still use original pool concepts.
    if not states:
        from logo_maker.ideate import load_pool_concepts

        states = {
            c.id: concept_state(
                brief,
                metaphor=c.metaphor_text,
                treatment=c.treatment_desc,
                material=c.material_desc,
                treatment_id=c.treatment,
                material_id=c.material,
            )
            for c in load_pool_concepts(logo, brief)
        }
    return states


def screen_previews(
    logo: LogoDir, brief: Brief, previews: dict[str, Path], client: JevAsker, *, keep: int = 3
) -> list[str]:
    """Screen preview renders down to finalists; writes `ideation/finalists.json`."""
    questions = preview_screen_questions()
    states = _concept_states(logo, brief)
    jobs = [
        (dict(states[cid], preview=Image(p)), questions, f"preview-{concept_slug(cid)}")
        for cid, p in previews.items()
    ]
    decisions = {}
    for (cid, _), answers in zip(
        previews.items(), client.ask_many(jobs) if jobs else [], strict=True
    ):
        ok, reason = preview_decision(answers)
        decisions[cid] = (ok, reason, answers)
    survivors = [cid for cid, (ok, _, _) in decisions.items() if ok]
    if not survivors:
        detail = "; ".join(
            f"{concept_slug(cid)}: {reason}" for cid, (_, reason, _) in decisions.items()
        )
        raise ValueError(f"no preview survived screening; the agent must revise motifs: {detail}")
    ranked = sorted(
        survivors,
        key=lambda cid: (
            -float(decisions[cid][2]["appealing"]["score"]),
            -decisions[cid][2]["matches_concept"]["noul"],
            -decisions[cid][2]["readable_mark"]["noul"],
            cid,
        ),
    )
    finalists = ranked[: max(1, min(keep, len(ranked)))]
    doc = {
        "ids": finalists,
        "reasons": {cid: decisions[cid][1] for cid in finalists},
        "pleasant_cutoff": PREVIEW_MIN_PLEASANT,
    }
    (logo.ideation / "finalists.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return finalists


def tiny_version(final_png: Path, dest: Path, *, budget: Budget | None = None) -> Path:
    """Downscale to 32 px, then upscale with nearest-neighbor for the `tiny` state image."""
    if budget is not None:
        from logo_maker.host import run

        run({"operation": "tiny_image", "png": str(final_png), "dest": str(dest)}, budget, [])
        return dest
    im = _PILImage.open(final_png).convert("RGB")
    tiny = im.resize((TINY_PX, TINY_PX), _PILImage.Resampling.LANCZOS)
    tiny.resize((TINY_VIEW_PX, TINY_VIEW_PX), _PILImage.Resampling.NEAREST).save(dest, "PNG")
    return dest


#: The QA checks, in the order `qa_questions()` asks them.
QA_CHECKS = tuple(QA_CHECK_SPECS)


def qa_judgments(
    logo: LogoDir,
    brief: Brief,
    concept_id: str,
    final_png: Path,
    client: JevAsker,
    *,
    budget: Budget | None = None,
) -> dict[str, Verdict]:
    """QA one final render (makes the 32 px version itself); returns per-check verdicts."""
    tiny_path = logo.qa / f"{concept_slug(concept_id)}-tiny256.png"
    tiny_version(final_png, tiny_path, budget=budget)
    state = _image_state(
        brief, {"concept_id": concept_id, "render": Image(final_png), "tiny": Image(tiny_path)}
    )
    answers = client.ask(state, qa_questions(), label=f"qa-{concept_slug(concept_id)}")
    return {
        check: Verdict(
            check, qa_status(float(answers[check]["noul"])), float(answers[check]["noul"])
        )
        for check in QA_CHECKS
    }


def _tournament_wins(
    contenders: list[str],
    descs: dict[str, str],
    images: dict[str, Image],
    brief: Brief,
    client: JevAsker,
    label: str,
) -> tuple[dict[str, float], list[dict]]:
    brief_state = {"brief": brief.as_state()}
    done: dict[tuple[str, str], str] = {}
    jobs, pairs = [], []
    for i, a in enumerate(contenders):
        for b in contenders[i + 1 :]:
            for first, second in ((a, b), (b, a)):
                # Each order presents renders and options first-then-second to cancel position bias.
                state = dict(brief_state, renders={first: images[first], second: images[second]})
                jobs.append(
                    (
                        state,
                        head_to_head_questions(
                            first,
                            descs[first],
                            second,
                            descs[second],
                            "is the stronger final render for the brand in `brief`",
                        ),
                        f"{label}-{first}-vs-{second}",
                    )
                )
                pairs.append((first, second))
    wins = dict.fromkeys(contenders, 0.0)
    rows = []
    for (first, second), answers in zip(pairs, client.ask_many(jobs) if jobs else [], strict=True):
        pick = answers["preferred_mark"]["choice"]
        rows.append(
            {"a": first, "b": second, "order": [first, second], "pick": pick, "answers": answers}
        )
        done[(first, second)] = pick
    for i, a in enumerate(contenders):
        for b in contenders[i + 1 :]:
            winner, _ = head_to_head_table(done[(a, b)], done[(b, a)], a, b)
            if winner == "split":
                wins[a] += 0.5
                wins[b] += 0.5
            else:
                wins[winner] += 1.0
    return wins, rows


def final_tournament(
    logo: LogoDir, brief: Brief, finalists: dict[str, Path], client: JevAsker
) -> str:
    """Full round-robin over final renders, both orders; writes `ideation/winner.json`."""
    slugs = {cid: concept_slug(cid) for cid in finalists}
    images = {slugs[cid]: Image(p) for cid, p in finalists.items()}
    descs = {slugs[cid]: f"The final render of {cid}." for cid in finalists}
    contenders = sorted(slugs.values())
    wins, rows = _tournament_wins(contenders, descs, images, brief, client, "final")
    ranked = sorted(contenders, key=lambda s: (-wins[s], s))
    winner_slug = ranked[0]
    by_slug = {slug: cid for cid, slug in slugs.items()}
    tied = sorted(s for s in contenders if wins[s] == wins[winner_slug])
    reason = f"{wins[winner_slug]:g} wins of {len(contenders) - 1} matches"
    if len(tied) > 1:
        reason += (
            f"; tied with {', '.join(s for s in tied if s != winner_slug)} on wins, "
            "decided by deterministic slug ordering"
        )
    (logo.ideation / "winner.json").write_text(
        json.dumps(
            {
                "winner": by_slug[winner_slug],
                "slug": winner_slug,
                "reason": reason,
                "wins": wins,
                "matches": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return by_slug[winner_slug]


def beats_floor(
    logo: LogoDir, brief: Brief, candidate: Path, floor: Path, client: JevAsker
) -> tuple[bool, dict[str, Any]]:
    """Does the candidate beat the current floor? Both orders; splits keep the floor.

    Truth table: wins both -> beats; loses either or splits -> stays.
    """
    images = {"candidate": Image(candidate), "floor": Image(floor)}
    descs = {"candidate": "The candidate logo render.", "floor": "The current best logo render."}
    subject = "is the stronger logo for the brand in `brief`"
    jobs = []
    for first, second in (("candidate", "floor"), ("floor", "candidate")):
        state = {
            "brief": brief.as_state(),
            "renders": {first: images[first], second: images[second]},
        }
        questions = head_to_head_questions(first, descs[first], second, descs[second], subject)
        jobs.append((state, questions, f"beats-floor-{first}-first"))
    candidate_first, floor_first = client.ask_many(jobs)
    pick_ab = candidate_first["preferred_mark"]["choice"]
    pick_ba = floor_first["preferred_mark"]["choice"]
    winner, reason = head_to_head_table(pick_ab, pick_ba, "candidate", "floor")
    beats = winner == "candidate"
    return beats, {
        "candidate_first": pick_ab,
        "floor_first": pick_ba,
        "winner": winner,
        "reason": reason,
    }


def load_brief(logo: LogoDir) -> Brief:
    return load(logo.brief)
