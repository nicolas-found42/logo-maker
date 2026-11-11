"""Reference-relative visual gates. No preference ranking or device-based quality labels."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import resvg_py
from PIL import Image as PILImage

from logo_maker.brief import Brief
from logo_maker.jev import questions as Q
from logo_maker.jev.client import Image, JevAsker, JevError
from logo_maker.paths import LogoDir
from logo_maker.proc import ToolError

OWNER_DIMENSIONS = ("overall", "craftsmanship", "brief_fit", "intended_appearance")


def _owner_rejects(row: dict) -> bool:
    return any(row.get(key) == "fail" for key in OWNER_DIMENSIONS)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def revision(logo: LogoDir, brief: Brief, concept_id: str, candidate: Path) -> dict:
    """Bind a decision to source pixels, authored inputs, concept and rubric."""
    folder = logo.concept(concept_id)
    from logo_maker import briefing
    from logo_maker.brief import load

    if load(logo.brief) != brief:
        raise ValueError("brief changed since the judgment context was prepared")

    return {
        "candidate_sha256": sha256(candidate),
        "reviewed_requirements": briefing.current(logo)["inputs"],
        "brief": brief.as_state(),
        "references": [
            {"use": ref.use, "note": ref.note, "sha256": sha256(ref.path)}
            for ref in brief.references
        ],
        "sources": {
            str(p.relative_to(logo.root)): sha256(p)
            for p in [
                logo.brief,
                logo.root / "brief-evidence.toml",
                logo.ideation / "requirements.json",
                logo.ideation / "palette.json",
                logo.ideation / "fonts.json",
                logo.qa / "owner-feedback.json",
                logo.ideation / "pool.jsonl",
                logo.metaphors,
                *(
                    folder / name
                    for name in (
                        "concept.json",
                        "plan.toml",
                        "plan-review.json",
                        "motif.py",
                        "motif.svg",
                        "motif.json",
                        "scene.toml",
                        "scene.py",
                    )
                ),
            ]
            if p.is_file()
        },
        "rubric_sha256": sha256(Path(Q.__file__)),
        "eligibility_protocol_sha256": sha256(Path(__file__)),
    }


def _statuses(answers: dict, questions: dict) -> dict[str, str]:
    """Malformed provider answers are errors, including NaN/out-of-range probabilities."""
    if not isinstance(answers, dict) or answers.keys() != questions.keys():
        raise JevError("missing or invalid eligibility answer keys")
    result = {}
    for qid in questions:
        try:
            p = answers[qid]["noul"]
            if (
                isinstance(p, bool)
                or not isinstance(p, (int, float))
                or not math.isfinite(p)
                or not 0 <= p <= 1
            ):
                raise ValueError("invalid Noul")
            result[qid] = Q.qa_status(p)
        except (KeyError, TypeError, ValueError) as exc:
            raise JevError(f"missing or invalid eligibility answer: {qid}") from exc
    return result


def owner_review_scope(logo: LogoDir, brief: Brief, concept_id: str, candidate: Path) -> str:
    """Exact review context, stable when the review itself is appended to the feedback file."""
    context = revision(logo, brief, concept_id, candidate)
    context["sources"].pop("qa/owner-feedback.json", None)
    return _digest(context)


def _combined(statuses: list[str]) -> str:
    if "fail" in statuses:
        return "fail"
    return "pass" if statuses and all(s == "pass" for s in statuses) else "unsettled"


def _native_details(path: Path, dest: Path, name: str) -> dict[str, Image]:
    """Whole images over the transport limit need native-pixel evidence as well."""
    with PILImage.open(path) as source:
        if max(source.size) <= 1024:
            return {}
        # Tile all pixels, not selected favorable crops. Each side stays within the API limit.
        details = {}
        for y in range(0, source.height, 1000):
            for x in range(0, source.width, 1000):
                tile = dest / f"{name}-{x}-{y}.png"
                crop = source.crop(
                    (x, y, min(x + 1000, source.width), min(y + 1000, source.height))
                ).convert("RGBA")
                # Pad thin remainder strips so the transport's minimum side never
                # upscales or filters their native detail pixels.
                canvas = PILImage.new("RGBA", (1000, 1000))
                canvas.paste(crop, (0, 0))
                canvas.save(tile)
                details[f"x{x}_y{y}"] = Image(tile)
        return details


def _small_view(source: PILImage.Image, path: Path) -> Image:
    source.resize((32, 32), PILImage.Resampling.LANCZOS).resize(
        (320, 320), PILImage.Resampling.NEAREST
    ).save(path)
    return Image(path)


def compare_visual(
    brief: Brief,
    concept: dict,
    candidate: Path,
    client: JevAsker,
    *,
    label: str,
    flat_mark: Path | None = None,
    identity_context: dict | None = None,
) -> dict:
    """Visual comparison only; historical CPU art is valid visual evidence.

    Production callers must use assess(), which independently enforces execution.
    Candidate/brief requests exclude cross-brand reference images and vice versa.
    """
    with TemporaryDirectory(prefix="logo-eligibility-") as tmp:
        return _compare_views(
            brief, concept, candidate, client, label, flat_mark, Path(tmp), identity_context
        )


def _compare_views(
    brief: Brief,
    concept: dict,
    candidate: Path,
    client: JevAsker,
    label: str,
    flat_mark: Path | None,
    dest: Path,
    identity_context: dict | None = None,
) -> dict:
    craft_rows: list[dict[str, Any]] = []
    details = _native_details(candidate, dest, "candidate")
    for index, ref in enumerate(ref for ref in brief.references if ref.use == "craft"):
        ref_details = _native_details(ref.path, dest, f"reference-{index}")
        for order in (("candidate", "reference"), ("reference", "candidate")):
            images = {"candidate": Image(candidate), "reference": Image(ref.path)}
            state = {
                **{name: images[name] for name in order},
                "intended_appearances": {
                    "candidate": brief.intended_appearance,
                    "reference": ref.note,
                },
            }
            # Keep each image group in the same presentation order as the primary images.
            state["native_detail_views"] = {
                name: details if name == "candidate" else ref_details for name in order
            }
            questions = Q.craft_questions()
            answers = client.ask(state, questions, label=f"{label}-craft-{index}-{order[0]}-first")
            statuses = _statuses(answers, questions)
            craft_rows.append(
                {
                    "reference_sha256": sha256(ref.path),
                    "candidate_sha256": sha256(candidate),
                    "order": list(order),
                    "answers": answers,
                    "checks": statuses,
                    "status": _combined(list(statuses.values())),
                }
            )
    literal_state = {
        "candidate": Image(candidate),
        "brief": brief.as_state(),
        "concept": concept,
        "intended_appearance": brief.intended_appearance,
    }
    symbol_questions = {"symbol": Q.fit_questions()["symbol"]}
    symbol_answers = client.ask(literal_state, symbol_questions, label=f"{label}-symbol-fit")
    symbol = _statuses(symbol_answers, symbol_questions)
    fit_brief = brief.as_state()
    if identity_context is not None:
        fit_brief = {
            **identity_context["business"],
            **{
                key: value
                for key, value in identity_context["design_direction"].items()
                if key != "references"
            },
            "communication_priority": identity_context["communication_priority"],
            "identity_requirements": identity_context["requirements"],
        }
    state = {
        "candidate": Image(candidate),
        "brief": fit_brief,
        "intended_appearance": brief.intended_appearance,
    }
    with PILImage.open(candidate) as source:
        state["hero_32px"] = _small_view(source, dest / "hero-small.png")
    questions = Q.fit_questions()
    questions.pop("symbol")
    if flat_mark is not None and flat_mark.is_file():
        flat = PILImage.open(
            io.BytesIO(resvg_py.svg_to_bytes(svg_string=flat_mark.read_text(), width=32, height=32))
        )
        state["flat_32px"] = _small_view(flat, dest / "flat-small.png")
    else:
        questions.pop("small_flat")
    answers = client.ask(state, questions, label=f"{label}-fit")
    statuses = {**symbol, **_statuses(answers, questions)}
    fit = {qid: statuses.get(qid, "missing_evidence") for qid in Q.fit_questions()}
    # Independent call: native detail evidence, no tiny thumbnails or craft-reference style.
    technical_state = dict(literal_state)
    technical_state["native_details"] = details
    questions = Q.technical_questions()
    technical_answers = client.ask(technical_state, questions, label=f"{label}-technical")
    technical = _statuses(technical_answers, questions)
    return {
        "craft": craft_rows,
        "fit": fit,
        "technical": technical,
        "answers": {**symbol_answers, **answers, **technical_answers},
        "view_sha256": {p.name: sha256(p) for p in dest.glob("*.png")},
        "flat_source_sha256": sha256(flat_mark)
        if flat_mark is not None and flat_mark.is_file()
        else None,
        "status": Q.eligibility_decision(
            craft=[r["status"] for r in craft_rows],
            fit=fit,
            technical=_combined(list(technical.values())),
            evidence="complete",
        ),
    }


def _append(logo: LogoDir, record: dict) -> None:
    with (logo.qa / "eligibility.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _detail_reviews(
    logo: LogoDir, concept_id: str, candidate: Path, client: JevAsker
) -> list[dict]:
    from logo_maker import briefing

    frozen = briefing.current(logo)
    obligations = [row for row in frozen["state"]["obligations"] if row["kind"] == "authoring"]
    if not obligations:
        return []
    plan = briefing.current_plan(logo, concept_id)["state"]["plan"]
    rows = []
    with TemporaryDirectory(prefix="logo-detail-obligations-") as tmp:
        dest = Path(tmp)
        for obligation in obligations:
            state = {
                "candidate": Image(candidate),
                "detail_plan": plan,
                "authoring_obligation": obligation,
                "native_details": _native_details(candidate, dest, "candidate"),
            }
            baseline = obligation.get("baseline_image")
            if baseline:
                path = logo.root / baseline
                state["prior_baseline"] = Image(path)
                state["baseline_native_details"] = _native_details(path, dest, "baseline")
            questions = Q.detail_realization_questions(plan["details"], baseline=bool(baseline))
            answers = client.ask(state, questions, label=f"detail-{concept_id}-{obligation['id']}")
            checks = _statuses(answers, questions)
            rows.append(
                {
                    "obligation": obligation["id"],
                    "answers": answers,
                    "checks": checks,
                    "status": _combined(list(checks.values())),
                }
            )
    return rows


def assess(
    logo: LogoDir,
    brief: Brief,
    concept_id: str,
    candidate: Path,
    client: JevAsker,
    *,
    stage: str,
) -> dict[str, Any]:
    from logo_maker import briefing
    from logo_maker.brief import load

    refs = [ref for ref in brief.references if ref.use == "craft"]
    missing = []
    try:
        briefing.current_plan(logo, concept_id)
        if load(logo.brief) != brief:
            missing.append("supplied brief differs from the frozen source brief")
    except (OSError, ValueError) as exc:
        missing.append(str(exc))
    if not refs:
        missing.append("craft reference required (use = 'craft')")
    if not brief.intended_appearance:
        missing.append("intended_appearance required")
    if not candidate.is_file():
        missing.append("candidate pixels missing")
    flat_mark = logo.concept(concept_id) / "motif.svg"
    if not flat_mark.is_file():
        missing.append("flat master motif.svg required for small-size fit evidence")
    for ref in refs:
        if not ref.path.is_file() or not ref.note.strip():
            missing.append(
                f"craft reference pixels and intended-treatment note required: {ref.path}"
            )
    for path in [candidate, *(ref.path for ref in refs)]:
        if path.is_file():
            try:
                with PILImage.open(path) as img:
                    img.verify()
            except (OSError, ValueError) as exc:
                missing.append(f"unreadable image evidence {path.name}: {exc}")
    record: dict[str, Any] = {
        "concept": concept_id,
        "stage": stage,
        "status": "missing_evidence",
        "missing": missing,
    }
    if missing:
        _append(logo, record)
        return record
    from logo_maker.ideate import load_pool_concepts
    from logo_maker.render import verify_execution

    try:
        execution = verify_execution(candidate.parent, stage)
        record["execution"] = {
            "status": "verified",
            "sha256": sha256(candidate.parent / ".build" / f"{stage}.execution.json"),
        }
    except ToolError as exc:
        record.update(status="execution_policy_error", error=str(exc))
        _append(logo, record)
        raise
    try:
        concepts = {c.id: c for c in load_pool_concepts(logo, brief)}
    except (OSError, KeyError, ValueError) as exc:
        record["missing"].append(f"current concept evidence unavailable: {exc}")
        _append(logo, record)
        return record
    if concept_id not in concepts:
        record["missing"].append("current concept revision missing")
        _append(logo, record)
        return record
    c = concepts[concept_id]
    concept = Q.concept_state(
        brief, metaphor=c.metaphor_text, treatment=c.treatment_desc, material=c.material_desc
    )["concept"]
    try:
        reviewed_context = briefing.current(logo)
        rev = revision(logo, brief, concept_id, candidate)
        if rev["reviewed_requirements"] != reviewed_context["inputs"]:
            raise ValueError("requirements changed while preparing judgment context")
    except (OSError, ValueError) as exc:
        record["missing"].append(f"source evidence unavailable: {exc}")
        _append(logo, record)
        return record
    record.update(revision=rev, revision_sha256=_digest(rev))
    try:
        record.update(
            compare_visual(
                brief,
                concept,
                candidate,
                client,
                label=f"{stage}-{candidate.parent.name}",
                flat_mark=flat_mark,
                identity_context=reviewed_context["state"],
            )
        )
        detail_reviews = _detail_reviews(logo, concept_id, candidate, client)
        record["detail_obligations"] = detail_reviews
        record["status"] = _combined([record["status"], *[row["status"] for row in detail_reviews]])
    except JevError as exc:
        record.update(status="api_error", error=str(exc))
        _append(logo, record)
        raise
    except (OSError, ValueError) as exc:
        record.update(
            status="missing_evidence", missing=[f"image evidence changed during judgment: {exc}"]
        )
        _append(logo, record)
        return record
    record["sampling"] = {
        "settings": execution["sampling"],
        "noise": record["technical"]["noise_free"],
        "limit": "unknown",  # #5 sample-count diagnostics are not yet supplied by production.
        "convergence": "unknown",
        "device": "verified",
        "outcome": Q.sampling_decision(record["technical"], limit="unknown", device="verified"),
        "visual_acceptance": _combined(list(record["technical"].values())),
        "acceptance_basis": "independent delivered-image visual judgments; no numerical convergence claim",
    }
    feedback = logo.qa / "owner-feedback.json"
    if feedback.is_file():
        try:
            reviews = json.loads(feedback.read_text())
            if not isinstance(reviews, list) or any(not isinstance(row, dict) for row in reviews):
                raise ValueError("owner feedback must be an array of review records")
            for row in reviews:
                if any(
                    row.get(key, "unknown")
                    not in {"pass", "fail", "unknown", "uncertain", "unsettled"}
                    for key in OWNER_DIMENSIONS
                ):
                    raise ValueError("invalid owner feedback label")
            scope = owner_review_scope(logo, brief, concept_id, candidate)
            same_image = [
                row for row in reviews if row["candidate_sha256"] == rev["candidate_sha256"]
            ]
            matching = [
                row
                for row in same_image
                if row["brief_sha256"] == sha256(logo.brief)
                and row["concept"] == concept_id
                and ("input_revision_sha256" not in row or row["input_revision_sha256"] == scope)
            ]
            stale = [row for row in same_image if row not in matching]
        except (OSError, KeyError, TypeError, ValueError) as exc:
            record.update(status="missing_evidence", missing=[f"invalid owner feedback: {exc}"])
        else:
            record["owner_feedback"] = matching
            record["owner_review_scope"] = scope
            record["owner_feedback_scopes"] = [
                "current" if "input_revision_sha256" in row else "legacy_partial"
                for row in matching
            ]
            record["owner_feedback_stale"] = stale
            if any(_owner_rejects(row) for row in matching):
                # Preserve model answers separately. An owner rejection vetoes; approval never
                # replaces missing/unsettled essential judgments.
                record.update(status="fail", decision_basis="owner_rejection")
            elif any(_owner_rejects(row) for row in stale) and not any(
                row.get("overall") == "pass" and row.get("input_revision_sha256") == scope
                for row in matching
            ):
                if record["status"] == "pass":
                    record.update(status="unsettled", decision_basis="stale_owner_review")
            elif (
                any(
                    row.get(key) in {"uncertain", "unsettled"}
                    for row in matching
                    for key in OWNER_DIMENSIONS
                )
                and record["status"] == "pass"
            ):
                record.update(status="unsettled", decision_basis="owner_review_unsettled")
    # Inputs may have changed while the provider was running. Never attach old answers to new bytes.
    try:
        unchanged = revision(logo, brief, concept_id, candidate) == rev
    except (OSError, ValueError):
        unchanged = False
    if not unchanged:
        record.update(status="missing_evidence", missing=["inputs changed during judgment; rerun"])
    _append(logo, record)
    return record


def require_current(
    logo: LogoDir, brief: Brief, concept_id: str, proof: dict, *, stage: str = "final"
) -> None:
    """Export only a winner whose final pixels and complete inputs still match the gate."""
    from logo_maker import briefing
    from logo_maker.render import verify_execution

    candidate = logo.concept(concept_id) / f"{stage}.png"
    verify_execution(candidate.parent, stage)
    try:
        briefing.current_plan(logo, concept_id)
        current = revision(logo, brief, concept_id, candidate)
    except (OSError, ValueError) as exc:
        raise ValueError("winner eligibility stale or missing; rerun finalize") from exc
    if proof.get("status") != "pass" or proof.get("revision_sha256") != _digest(current):
        raise ValueError("winner eligibility stale or absent; rerun finalize")
