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


def screen_previews(logo, brief, previews, client, *, keep=3):
    doc = screen_previews_record(logo, brief, previews, client, keep=keep)
    (logo.ideation / "finalists.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return doc["ids"]


class EligibilityStop(ValueError):
    """No image met the gate. Keep its individual checks available to the caller."""

    def __init__(self, message: str, records: dict[str, dict]):
        super().__init__(f"{message}: {_eligibility_detail(records)}")
        self.records = records

    def authoring_details(self, logo: LogoDir, stage: str) -> dict:
        candidates = {}
        for cid, record in self.records.items():
            candidates[cid] = {
                "status": record["status"],
                "artifact": f"concepts/{concept_slug(cid)}/{stage}.png",
                "fit": {k: v for k, v in record.get("fit", {}).items() if v != "pass"},
                "technical": {k: v for k, v in record.get("technical", {}).items() if v != "pass"},
                "craft": [
                    {
                        "order": row["order"],
                        "reference_sha256": row["reference_sha256"],
                        "checks": {k: v for k, v in row["checks"].items() if v != "pass"},
                    }
                    for row in record.get("craft", [])
                    if row["status"] != "pass"
                ],
                "missing": record.get("missing", []),
            }
        return {
            "dimension": "image_eligibility",
            "stage": stage,
            "candidates": candidates,
            "journal": str(logo.root / "qa/eligibility.jsonl"),
        }


def _eligibility_detail(records: dict[str, dict]) -> str:
    """Status plus the recorded reasons, so stale evidence is not reported as a design failure."""
    parts = []
    for cid, record in records.items():
        reasons = "; ".join(str(reason) for reason in record.get("missing") or [])
        parts.append(f"{cid}: {record['status']}" + (f" ({reasons})" if reasons else ""))
    return "; ".join(parts)


def screen_previews_record(
    logo: LogoDir,
    brief: Brief,
    previews: dict[str, Path],
    client: JevAsker,
    *,
    keep: int = 3,
    budget: Budget | None = None,
) -> dict:
    """Screen preview renders down to finalists; writes `ideation/finalists.json`."""
    from logo_maker.eligibility import assess

    eligibility = {
        cid: assess(logo, brief, cid, p, client, stage="preview", budget=budget)
        for cid, p in previews.items()
    }
    previews = {cid: p for cid, p in previews.items() if eligibility[cid]["status"] == "pass"}
    if not previews:
        raise EligibilityStop("no preview survived eligibility", eligibility)
    questions = preview_screen_questions()
    if budget is not None:
        from logo_maker import host

        states = host.run({"operation": "concept_states", "root": str(logo.root)}, budget, [])[
            "states"
        ]
    else:
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
    from logo_maker.eligibility import require_current

    for cid in finalists:
        require_current(logo, brief, cid, eligibility[cid], stage="preview", budget=budget)
    doc = {
        "ids": finalists,
        "reasons": {cid: decisions[cid][1] for cid in finalists},
        "pleasant_cutoff": PREVIEW_MIN_PLEASANT,
        "eligibility": eligibility,
    }
    return doc


def tiny_version(final_png: Path, dest: Path, *, budget: Budget | None = None) -> Path:
    """Downscale to 32 px, then upscale with nearest-neighbor for the `tiny` state image."""
    if budget is not None:
        from logo_maker.host import run

        run({"operation": "tiny_image", "png": str(final_png), "dest": str(dest)}, budget, [])
        return dest
    # Keep transparency as the full `render` has it: flattening to RGB drops the alpha and leaves
    # the color stored under transparent pixels (usually black) as the background.
    with _PILImage.open(final_png) as source:
        im = source.convert("RGBA").convert("RGBa")  # premultiplied, so edges don't bleed
    tiny = im.resize((TINY_PX, TINY_PX), _PILImage.Resampling.LANCZOS)
    view = tiny.resize((TINY_VIEW_PX, TINY_VIEW_PX), _PILImage.Resampling.NEAREST)
    view.convert("RGBA").save(dest, "PNG")
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
    qa_dir = logo.root / "qa" if budget is not None else logo.qa
    tiny_path = qa_dir / f"{concept_slug(concept_id)}-tiny256.png"
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
    record = final_tournament_record(brief, finalists, client, logo=logo)
    (logo.ideation / "winner.json").write_text(json.dumps(record, indent=2, sort_keys=True))
    return record["winner"]


def final_tournament_record(
    brief: Brief,
    finalists: dict[str, Path],
    client: JevAsker,
    *,
    logo: LogoDir,
    budget: Budget | None = None,
) -> dict:
    """Choose without publishing; bounded callers commit winner and run state together."""
    from logo_maker.eligibility import assess, require_current

    eligibility = {
        cid: assess(logo, brief, cid, path, client, stage="final", budget=budget)
        for cid, path in finalists.items()
    }
    finalists = {
        cid: path for cid, path in finalists.items() if eligibility[cid]["status"] == "pass"
    }
    if not finalists:
        raise EligibilityStop("no final candidate meets the floor", eligibility)
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
    for cid in finalists:
        require_current(logo, brief, cid, eligibility[cid], budget=budget)
    return {
        "winner": by_slug[winner_slug],
        "slug": winner_slug,
        "reason": reason,
        "wins": wins,
        "matches": rows,
        "ranking_dimension": "aesthetic preference among eligible candidates",
        "eligibility": eligibility[by_slug[winner_slug]],
        "candidate_eligibility": eligibility,
    }


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
