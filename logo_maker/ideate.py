"""Ideation: metaphors -> scored pool -> screened shortlist of 8 concepts.

The agent writes `ideation/metaphors.toml`; jev scores fits and screens; code
applies every cutoff and runs the tournament. Stage files are resumable: lines
whose input hash still matches are reused without calling jev again.
"""

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logo_maker import catalog
from logo_maker.brief import Brief, load
from logo_maker.jev.client import JevAsker
from logo_maker.jev.questions import (
    concept_state,
    head_to_head_questions,
    head_to_head_table,
    material_fit_questions,
    stage1_decision,
    stage1_questions,
    stage2_composite,
    stage2_questions,
    treatment_fit_questions,
)
from logo_maker.paths import LogoDir, concept_slug, slugify

#: Pool ceiling and the per-item keeps that enforce it (40 metaphors x 6 x 4 = 960).
MAX_POOL_CONCEPTS = 1000
TREATMENTS_PER_METAPHOR = 6
MATERIALS_PER_BRIEF = 4
#: Tournament contenders: best concept per metaphor, then full round-robin both orders.
SHORTLIST_DEFAULT = 8


@dataclass(frozen=True)
class Metaphor:
    id: str
    text: str


@dataclass
class Concept:
    id: str  # 'metaphor|treatment|material'
    metaphor: str
    treatment: str
    material: str
    metaphor_text: str = ""
    treatment_desc: str = ""
    material_desc: str = ""
    scores: dict[str, Any] = field(default_factory=dict)


def load_metaphors(logo: LogoDir) -> list[Metaphor]:
    """Read and validate `ideation/metaphors.toml` ([[metaphor]] id/text entries)."""
    path = logo.metaphors
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(
            f"no metaphors at {path}; the agent writes 8-40 [[metaphor]] entries"
        ) from exc
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"{path}: cannot read ({exc}); rewrite it") from exc
    raw = data.get("metaphor", [])
    if not isinstance(raw, list) or not all(isinstance(entry, dict) for entry in raw):
        raise ValueError(f"{path}: write each metaphor as a [[metaphor]] table with id and text")
    if not 8 <= len(raw) <= 40:
        raise ValueError(f"{path} holds {len(raw)} metaphors; need 8-40")
    metaphors = []
    seen = set()
    for entry in raw:
        mid, text = entry.get("id", ""), entry.get("text", "")
        if not isinstance(mid, str) or not isinstance(text, str):
            raise ValueError(f"{path}: metaphor id and text must be strings, got {entry!r}")
        text = text.strip()
        key = slugify(mid)
        if not mid or key != mid.lower().replace("_", "-"):
            raise ValueError(f"metaphor id {mid!r} is not a slug (use [a-z0-9_-]+)")
        if key in seen:
            raise ValueError(f"duplicate metaphor id {mid!r} (slug {key!r} taken)")
        if not text:
            raise ValueError(f"metaphor {mid!r} has empty text")
        seen.add(key)
        metaphors.append(Metaphor(mid, text))
    return metaphors


def concept_id(metaphor: str, treatment: str, material: str) -> str:
    return f"{metaphor}|{treatment}|{material}"


def _input_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path}: cannot read ({exc}); delete the file to redo the stage") from exc
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{number}: not valid JSON ({exc.msg}); delete the file to redo the stage"
            ) from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n" if rows else ""
    pending = path.with_name(f".{path.name}.pending")
    pending.write_text(text)
    pending.replace(path)


def select_pool(
    metaphor_ids: list[str],
    treatment_fits: dict[str, dict[str, float]],
    material_fits: dict[str, float],
) -> list[tuple[str, str, str]]:
    """Code rule: per metaphor keep the best-fitting treatments, cross with the
    brief's best materials, trim by fit product so the pool never exceeds
    `MAX_POOL_CONCEPTS`. Deterministic: ties break by id."""
    materials = sorted(material_fits, key=lambda m: (-material_fits[m], m))[:MATERIALS_PER_BRIEF]
    combos: list[tuple[float, str, str, str]] = []
    for mid in metaphor_ids:
        fits = treatment_fits.get(mid, {})
        top = sorted(fits, key=lambda t: (-fits[t], t))[:TREATMENTS_PER_METAPHOR]
        for tid in top:
            for mat in materials:
                combos.append((fits[tid] * material_fits[mat], mid, tid, mat))
    combos.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
    return [(mid, tid, mat) for _, mid, tid, mat in combos[:MAX_POOL_CONCEPTS]]


def build_pool(logo: LogoDir, brief: Brief, client: JevAsker) -> list[Concept]:
    """Score every metaphor x treatment and every material, then write pool.jsonl."""
    metaphors = load_metaphors(logo)
    treatments = {tid: e.description for tid, e in catalog.treatments().items()}
    materials = {mid: e.description for mid, e in catalog.materials().items()}

    treat_jobs = [
        (
            {"brief": brief.as_state(), "metaphor": m.text},
            treatment_fit_questions(m.text, treatments),
            f"treatment-fit-{m.id}",
        )
        for m in metaphors
    ]
    treat_answers = client.ask_many(treat_jobs)
    treatment_fits = {
        m.id: {tid: float(treat_answers[i][f"fits_{tid}"]["noul"]) for tid in treatments}
        for i, m in enumerate(metaphors)
    }
    mat_answers = client.ask(
        {"brief": brief.as_state()}, material_fit_questions(materials), label="material-fit"
    )
    material_fits = {mid: float(mat_answers[f"fits_{mid}"]["noul"]) for mid in materials}

    texts = {m.id: m.text for m in metaphors}
    pool = select_pool([m.id for m in metaphors], treatment_fits, material_fits)
    concepts = [
        Concept(
            concept_id(mid, tid, mat),
            mid,
            tid,
            mat,
            texts[mid],
            treatments[tid],
            materials[mat],
            {"treatment_fit": treatment_fits[mid][tid], "material_fit": material_fits[mat]},
        )
        for mid, tid, mat in pool
    ]
    _write_jsonl(
        logo.ideation / "pool.jsonl",
        [
            {
                "id": c.id,
                "metaphor": c.metaphor,
                "treatment": c.treatment,
                "material": c.material,
                "scores": c.scores,
            }
            for c in concepts
        ],
    )
    return concepts


def load_pool_concepts(logo: LogoDir, brief: Brief) -> list[Concept]:
    treatments = {tid: e.description for tid, e in catalog.treatments().items()}
    materials = {mid: e.description for mid, e in catalog.materials().items()}
    texts = {m.id: m.text for m in load_metaphors(logo)}
    concepts = []
    for row in _read_jsonl(logo.ideation / "pool.jsonl"):
        mid, tid, mat = row["metaphor"], row["treatment"], row["material"]
        concepts.append(
            Concept(
                row["id"],
                mid,
                tid,
                mat,
                texts[mid],
                treatments[tid],
                materials[mat],
                row.get("scores", {}),
            )
        )
    if not concepts:
        raise ValueError("pool.jsonl is empty; run the pool step first")
    return concepts


def _cached_rows(path: Path, fields: dict[str, type | tuple[type, ...]]) -> list[dict[str, Any]]:
    """Stored jev rows that still hold every field the stage reads; any other row is asked again."""
    return [
        row
        for row in _read_jsonl(path)
        if isinstance(row, dict)
        and all(isinstance(row.get(name), kind) for name, kind in fields.items())
        and row["answers"]
    ]


def _resume(path: Path, fields: dict[str, type | tuple[type, ...]]) -> dict[str, dict[str, Any]]:
    need = {"id": str, "input_hash": str, "answers": dict, **fields}
    return {row["id"]: row for row in _cached_rows(path, need)}


def _concept_payload(brief: Brief, concept: Concept, questions: dict[str, Any]) -> Any:
    state = concept_state(
        brief,
        metaphor=concept.metaphor_text,
        treatment=concept.treatment_desc,
        material=concept.material_desc,
        treatment_id=concept.treatment,
        material_id=concept.material,
    )
    return {"state": state, "hash": _input_hash({"state": state, "questions": questions})}


def run_chain(
    logo: LogoDir, client: JevAsker, *, shortlist: int = SHORTLIST_DEFAULT
) -> list[Concept]:
    """Stage 1 screen -> stage 2 score -> best per metaphor -> round-robin -> shortlist."""
    brief = load(logo.brief)
    concepts = load_pool_concepts(logo, brief)
    by_id = {c.id: c for c in concepts}

    # Stage 1: one bundled request per concept (fit + feasible + legible share state).
    s1_path = logo.ideation / "stage1.jsonl"
    s1_done = _resume(s1_path, {"keep": bool})
    s1_questions = stage1_questions()
    jobs, order = [], []
    for c in concepts:
        payload = _concept_payload(brief, c, s1_questions)
        if s1_done.get(c.id, {}).get("input_hash") == payload["hash"]:
            continue
        jobs.append((payload["state"], s1_questions, f"stage1-{c.id}"))
        order.append(c)
    for concept, answers in zip(order, client.ask_many(jobs) if jobs else [], strict=True):
        payload = _concept_payload(brief, concept, s1_questions)
        keep, reason = stage1_decision(answers)
        s1_done[concept.id] = {
            "id": concept.id,
            "input_hash": payload["hash"],
            "answers": answers,
            "keep": keep,
            "reason": reason,
        }
    _write_jsonl(s1_path, [s1_done[c.id] for c in concepts])
    survivors = [by_id[cid] for cid, r in s1_done.items() if r["keep"] and cid in by_id]
    if not survivors:
        raise ValueError("stage 1 dropped every concept; loosen metaphors or treatments and rerun")

    # Stage 2: score survivors, keep the best per metaphor.
    s2_path = logo.ideation / "stage2.jsonl"
    s2_done = _resume(s2_path, {"composite": (int, float)})
    s2_questions = stage2_questions()
    jobs, order = [], []
    for c in survivors:
        payload = _concept_payload(brief, c, s2_questions)
        if s2_done.get(c.id, {}).get("input_hash") == payload["hash"]:
            continue
        jobs.append((payload["state"], s2_questions, f"stage2-{c.id}"))
        order.append(c)
    for concept, answers in zip(order, client.ask_many(jobs) if jobs else [], strict=True):
        payload = _concept_payload(brief, concept, s2_questions)
        s2_done[concept.id] = {
            "id": concept.id,
            "input_hash": payload["hash"],
            "answers": answers,
            "composite": stage2_composite(answers),
        }
    _write_jsonl(s2_path, [s2_done[c.id] for c in survivors])
    best: dict[str, Concept] = {}
    for c in survivors:
        comp = s2_done[c.id]["composite"]
        c.scores["composite"] = comp
        if c.metaphor not in best or (comp, c.id) > (
            best[c.metaphor].scores["composite"],
            best[c.metaphor].id,
        ):
            best[c.metaphor] = c
    contenders = sorted(best.values(), key=lambda c: (-c.scores["composite"], c.id))

    # Tournament: full round-robin, both option orders; a split scores half a win each.
    t_path = logo.ideation / "tournament.jsonl"
    stored = {
        (r["a"], r["b"]): r
        for r in _cached_rows(
            t_path, {"a": str, "b": str, "pick": str, "input_hash": str, "answers": dict}
        )
    }
    t_done: dict[tuple[str, str], dict[str, Any]] = {}
    brief_state = {"brief": brief.as_state()}
    wins: dict[str, float] = {c.id: 0.0 for c in contenders}
    jobs = []
    pairs = []
    descs = {
        c.id: f"{c.metaphor_text} as {c.treatment_desc} in {c.material_desc}" for c in contenders
    }
    slugs = {c.id: concept_slug(c.id) for c in contenders}
    for i, a in enumerate(contenders):
        for b in contenders[i + 1 :]:
            for first, second in ((a, b), (b, a)):
                state = dict(
                    brief_state,
                    contenders={
                        slugs[first.id]: descs[first.id],
                        slugs[second.id]: descs[second.id],
                    },
                )
                questions = head_to_head_questions(
                    slugs[first.id],
                    descs[first.id],
                    slugs[second.id],
                    descs[second.id],
                    "best fits the brand in `brief`",
                )
                # A stored pick is reused only for the exact state and question it answered.
                digest = _input_hash({"state": state, "questions": questions})
                kept = stored.get((first.id, second.id))
                if kept is not None and kept.get("input_hash") == digest:
                    t_done[(first.id, second.id)] = kept
                    continue
                jobs.append(
                    (state, questions, f"tournament-{slugs[first.id]}-vs-{slugs[second.id]}")
                )
                pairs.append((first, second, digest))
    answers_list = client.ask_many(jobs) if jobs else []
    rows = list(t_done.values())
    for (first, second, digest), answers in zip(pairs, answers_list, strict=True):
        pick = answers["preferred_mark"]["choice"]
        row = {
            "a": first.id,
            "b": second.id,
            "order": [slugs[first.id], slugs[second.id]],
            "pick": pick,
            "answers": answers,
            "input_hash": digest,
        }
        rows.append(row)
        t_done[(first.id, second.id)] = row
    for i, a in enumerate(contenders):
        for b in contenders[i + 1 :]:
            picks = [t_done[(first.id, second.id)]["pick"] for first, second in ((a, b), (b, a))]
            winner, _ = head_to_head_table(picks[0], picks[1], slugs[a.id], slugs[b.id])
            if winner == "split":
                wins[a.id] += 0.5
                wins[b.id] += 0.5
            else:
                wins[{slugs[a.id]: a.id, slugs[b.id]: b.id}[winner]] += 1.0
    _write_jsonl(t_path, rows)
    ranked = sorted(contenders, key=lambda c: (-wins[c.id], -c.scores["composite"], c.id))
    total_games = max(1, len(contenders) - 1)
    picked = ranked[: max(1, min(shortlist, len(ranked)))]
    shortlist_doc = {
        "ids": [c.id for c in picked],
        "reasons": {
            c.id: (
                f"{wins[c.id]:g}/{total_games} round-robin wins, "
                f"stage-2 composite {c.scores['composite']:.2f}"
            )
            for c in picked
        },
    }
    (logo.ideation / "shortlist.json").write_text(
        json.dumps(shortlist_doc, indent=2, sort_keys=True)
    )
    return picked
