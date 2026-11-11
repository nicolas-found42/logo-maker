"""Reference-relative visual gates. No preference ranking or device-based quality labels."""

from __future__ import annotations

import hashlib
import io
import json
import math
from collections import Counter
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
from logo_maker.sampling import Budget

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
        "render_provenance": {
            name: sha256(folder / ".build" / name)
            for name in (f"{candidate.stem}.sampling.json", f"{candidate.stem}.execution.json")
            if (folder / ".build" / name).is_file()
        },
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
    budget: Budget | None = None,
) -> dict:
    """Visual comparison only; historical CPU art is valid visual evidence.

    Production callers must use assess(), which independently enforces execution.
    Candidate/brief requests exclude cross-brand reference images and vice versa.
    """
    with TemporaryDirectory(prefix="logo-eligibility-") as tmp:
        return _compare_views(
            brief, concept, candidate, client, label, flat_mark, Path(tmp), identity_context, budget
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
    budget: Budget | None = None,
) -> dict:
    views = (
        _host_images(brief, candidate, flat_mark, dest, budget)
        if budget is not None
        else _prepare_images(brief, candidate, flat_mark, dest)
    )
    craft_rows: list[dict[str, Any]] = []
    details = {k: Image(v) for k, v in views["candidate"].items()}
    for index, ref in enumerate(ref for ref in brief.references if ref.use == "craft"):
        ref_details = {k: Image(v) for k, v in views["references"][index].items()}
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
                    "reference_sha256": views["reference_sha256"][index],
                    "candidate_sha256": views["candidate_sha256"],
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
    state["hero_32px"] = Image(dest / "hero-small.png")
    questions = Q.fit_questions()
    questions.pop("symbol")
    if views["flat_source_sha256"] is not None:
        state["flat_32px"] = Image(dest / "flat-small.png")
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
        "view_sha256": views["view_sha256"],
        "flat_source_sha256": views["flat_source_sha256"],
        "status": Q.eligibility_decision(
            craft=[r["status"] for r in craft_rows],
            fit=fit,
            technical=_combined(list(technical.values())),
            evidence="complete",
        ),
    }


def _append(logo: LogoDir, record: dict, *, budget: Budget | None = None) -> None:
    if budget is not None:
        from logo_maker import host

        host.run(
            {
                "operation": "append_jsonl",
                "path": str(logo.root / "qa/eligibility.jsonl"),
                "data": record,
            },
            budget,
            [],
        )
        return
    with (logo.qa / "eligibility.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _detail_inputs(logo, concept_id, candidate, dest):
    from logo_maker import briefing

    frozen = briefing.current(logo)
    obligations = [row for row in frozen["state"]["obligations"] if row["kind"] == "authoring"]
    if not obligations:
        return []
    plan = briefing.current_plan(logo, concept_id)["state"]["plan"]
    jobs = []
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
        jobs.append(
            {
                "state": _pack_images(state),
                "obligation": obligation["id"],
                "questions": Q.detail_realization_questions(
                    plan["details"], baseline=bool(baseline)
                ),
            }
        )
    return jobs


def _detail_reviews(logo, concept_id, candidate, client, *, budget=None):
    with TemporaryDirectory(prefix="logo-detail-obligations-") as tmp:
        jobs = (
            _host_call("details", logo, None, concept_id, candidate, budget, dest=tmp)
            if budget is not None
            else _detail_inputs(logo, concept_id, candidate, Path(tmp))
        )
        rows = []
        for job in jobs:
            answers = client.ask(
                _unpack_images(job["state"]),
                job["questions"],
                label=f"detail-{concept_id}-{job['obligation']}",
            )
            checks = _statuses(answers, job["questions"])
            rows.append(
                {
                    "obligation": job["obligation"],
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
    budget: Budget | None = None,
) -> dict[str, Any]:
    prepared = (
        _host_call("prepare", logo, brief, concept_id, candidate, budget, stage=stage)
        if budget is not None
        else _prepare_assessment(logo, brief, concept_id, candidate, stage)
    )
    record = prepared["record"]
    if "concept" not in prepared:
        return record
    try:
        record.update(
            compare_visual(
                brief,
                prepared["concept"],
                candidate,
                client,
                label=f"{stage}-{candidate.parent.name}",
                flat_mark=logo.root / "concepts" / candidate.parent.name / "motif.svg",
                identity_context=prepared["context"]["state"],
                budget=budget,
            )
        )
        detail_reviews = _detail_reviews(logo, concept_id, candidate, client, budget=budget)
        record["detail_obligations"] = detail_reviews
        record["status"] = _combined([record["status"], *[row["status"] for row in detail_reviews]])
    except JevError as exc:
        record.update(status="api_error", error=str(exc))
        _append(logo, record, budget=budget)
        raise
    except (OSError, ValueError) as exc:
        record.update(
            status="missing_evidence", missing=[f"image evidence changed during judgment: {exc}"]
        )
        _append(logo, record, budget=budget)
        return record
    if budget is not None:
        return _host_call(
            "finish",
            logo,
            brief,
            concept_id,
            candidate,
            budget,
            record=record,
            execution=prepared["execution"],
        )
    return _finish_assessment(logo, brief, concept_id, candidate, record, prepared["execution"])


def _prepare_assessment(logo, brief, concept_id, candidate, stage):
    from logo_maker import briefing
    from logo_maker.brief import load

    refs = [ref for ref in brief.references if ref.use == "craft"]
    missing = []
    reviewed_plan = {}
    try:
        reviewed_plan = briefing.current_plan(logo, concept_id)
        if load(logo.brief) != brief:
            missing.append("supplied brief differs from the frozen source brief")
    except (OSError, ValueError) as exc:
        missing.append(str(exc))
    description = reviewed_plan.get("state", {}).get("concept", {}).get("description")
    if not isinstance(description, str) or not description.strip():
        missing.append("current description required in concept.json")
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
        return {"record": record}
    from logo_maker.ideate import load_pool_concepts
    from logo_maker.render import verify_execution

    try:
        execution = verify_execution(candidate.parent, stage)
        record["execution"] = {
            "status": "verified",
            "sha256": sha256(Path(execution["evidence_path"])),
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
        return {"record": record}
    if concept_id not in concepts:
        record["missing"].append("current concept revision missing")
        _append(logo, record)
        return {"record": record}
    c = concepts[concept_id]
    concept = Q.concept_state(
        brief,
        metaphor=reviewed_plan["state"]["plan"]["hypothesis"],
        treatment=c.treatment_desc,
        material=c.material_desc,
        treatment_id=c.treatment,
        material_id=c.material,
    )["concept"]
    concept["description"] = description
    try:
        reviewed_context = briefing.current(logo)
        rev = revision(logo, brief, concept_id, candidate)
        if rev["reviewed_requirements"] != reviewed_context["inputs"]:
            raise ValueError("requirements changed while preparing judgment context")
    except (OSError, ValueError) as exc:
        record["missing"].append(f"source evidence unavailable: {exc}")
        _append(logo, record)
        return {"record": record}
    record.update(revision=rev, revision_sha256=_digest(rev))
    return {
        "record": record,
        "concept": concept,
        "context": reviewed_context,
        "execution": execution,
    }


def _finish_assessment(logo, brief, concept_id, candidate, record, execution):
    rev = record["revision"]
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
    sampling_path = candidate.parent / ".build" / f"{record['stage']}.sampling.json"
    if sampling_path.is_file():
        sampling = json.loads(sampling_path.read_text())
        outcomes = sampling.get("outcomes", {})
        limit = outcomes.get("cap", "unknown")
        record["sampling"].update(
            profile=sampling.get("profile", {}),
            outcomes=outcomes,
            limit=limit,
            outcome=Q.sampling_decision(record["technical"], limit=limit, device="verified"),
            record_sha256=sha256(sampling_path),
        )
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


def _validate_proof(logo: LogoDir, brief: Brief, concept_id: str, proof: dict) -> None:
    """Recompute essential decisions from retained answers, never a cached pass flag."""
    from logo_maker import briefing

    try:
        refs = [r for r in brief.references if r.use == "craft"]
        expected = Counter(
            (sha256(r.path), order)
            for r in refs
            for order in (("candidate", "reference"), ("reference", "candidate"))
        )
        rows = proof["craft"]
        observed = [(r["reference_sha256"], tuple(r["order"])) for r in rows]
        if not expected or Counter(observed) != expected:
            raise ValueError("missing craft comparisons")
        for row in rows:
            checks = _statuses(row["answers"], Q.craft_questions())
            if (
                checks != row["checks"]
                or _combined(list(checks.values())) != "pass"
                or row["status"] != "pass"
                or row["candidate_sha256"] != proof["revision"]["candidate_sha256"]
            ):
                raise ValueError("invalid craft proof")
        checks = _statuses(proof["answers"], {**Q.fit_questions(), **Q.technical_questions()})
        if (
            proof["fit"] != {k: checks[k] for k in Q.fit_questions()}
            or proof["technical"] != {k: checks[k] for k in Q.technical_questions()}
            or _combined(list(checks.values())) != "pass"
        ):
            raise ValueError("invalid fit/technical proof")
        obligations = [
            o for o in briefing.current(logo)["state"]["obligations"] if o["kind"] == "authoring"
        ]
        detail_rows = proof["detail_obligations"]
        if len(detail_rows) != len(obligations) or {r["obligation"] for r in detail_rows} != {
            o["id"] for o in obligations
        }:
            raise ValueError("missing authoring-obligation proof")
        if obligations:
            plan = briefing.current_plan(logo, concept_id)["state"]["plan"]
            for obligation in obligations:
                row = next(r for r in detail_rows if r["obligation"] == obligation["id"])
                questions = Q.detail_realization_questions(
                    plan["details"], baseline=bool(obligation.get("baseline_image"))
                )
                checks = _statuses(row["answers"], questions)
                if (
                    checks != row["checks"]
                    or _combined(list(checks.values())) != "pass"
                    or row["status"] != "pass"
                ):
                    raise ValueError("invalid authoring-obligation proof")
    except (KeyError, TypeError, JevError, ValueError) as exc:
        raise ValueError("winner eligibility incomplete or inconsistent; rerun finalize") from exc


def require_current(
    logo: LogoDir,
    brief: Brief,
    concept_id: str,
    proof: dict,
    *,
    stage: str = "final",
    budget: Budget | None = None,
) -> None:
    """Export only a winner whose final pixels and complete inputs still match the gate."""
    if budget is not None:
        _host_call("current", logo, brief, concept_id, None, budget, proof=proof, stage=stage)
        return
    from logo_maker import briefing
    from logo_maker.render import verify_execution

    candidate = logo.concept(concept_id) / f"{stage}.png"
    verify_execution(candidate.parent, stage)
    try:
        briefing.current_plan(logo, concept_id)
        current = revision(logo, brief, concept_id, candidate)
    except (OSError, ValueError) as exc:
        raise ValueError("winner eligibility stale or missing; rerun finalize") from exc
    if (
        proof.get("status") != "pass"
        or proof.get("revision_sha256") != _digest(current)
        or proof.get("revision") != current
    ):
        raise ValueError("winner eligibility stale or absent; rerun finalize")
    _validate_proof(logo, brief, concept_id, proof)


def _pack_images(value):
    if isinstance(value, Image):
        return {"__image_path__": str(value.path)}
    if isinstance(value, dict):
        return {key: _pack_images(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_pack_images(item) for item in value]
    return value


def _unpack_images(value):
    if isinstance(value, dict):
        if set(value) == {"__image_path__"}:
            return Image(value["__image_path__"])
        return {key: _unpack_images(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unpack_images(item) for item in value]
    return value


def _prepare_images(brief, candidate, flat_mark, dest):
    details = _native_details(candidate, dest, "candidate")
    refs = [r for r in brief.references if r.use == "craft"]
    references = [_native_details(r.path, dest, f"reference-{i}") for i, r in enumerate(refs)]
    with PILImage.open(candidate) as source:
        _small_view(source, dest / "hero-small.png")
    if flat_mark is not None and flat_mark.is_file():
        with PILImage.open(
            io.BytesIO(resvg_py.svg_to_bytes(svg_string=flat_mark.read_text(), width=32, height=32))
        ) as flat:
            _small_view(flat, dest / "flat-small.png")
    return {
        "candidate": {k: str(v.path) for k, v in details.items()},
        "references": [{k: str(v.path) for k, v in row.items()} for row in references],
        "candidate_sha256": sha256(candidate),
        "reference_sha256": [sha256(r.path) for r in refs],
        "view_sha256": {p.name: sha256(p) for p in dest.glob("*.png")},
        "flat_source_sha256": sha256(flat_mark)
        if flat_mark is not None and flat_mark.is_file()
        else None,
    }


def _brief_payload(brief):
    from dataclasses import asdict

    return json.loads(json.dumps(asdict(brief), default=str))


def _host_call(action, logo, brief, concept_id, candidate, budget, **extra):
    from logo_maker import host

    result = host.run(
        {
            "operation": "eligibility",
            "action": action,
            "root": str(logo.root) if logo else None,
            "brief": _brief_payload(brief) if brief else None,
            "concept_id": concept_id,
            "candidate": str(candidate) if candidate else None,
            **extra,
        },
        budget,
        [],
    )
    if "error" in result:
        if result["error_type"] == "ToolError":
            raise ToolError(result["error"])
        raise ValueError(result["error"])
    return result["result"]


def _host_images(brief, candidate, flat_mark, dest, budget):
    return _host_call(
        "images",
        None,
        brief,
        None,
        candidate,
        budget,
        flat_mark=str(flat_mark) if flat_mark else None,
        dest=str(dest),
    )


def host_operation(payload):
    from logo_maker.brief import Reference

    logo = LogoDir(Path(payload["root"])) if payload["root"] else None
    data = payload["brief"]
    if data is not None:
        data["references"] = tuple(
            Reference(Path(r["path"]), r["use"], r["note"]) for r in data["references"]
        )
        for key in ("tone", "uses", "avoid"):
            data[key] = tuple(data[key])
    brief = Brief(**data) if data is not None else None
    cid = payload["concept_id"]
    candidate = Path(payload["candidate"]) if payload["candidate"] else None
    try:
        match payload["action"]:
            case "prepare":
                result = _prepare_assessment(logo, brief, cid, candidate, payload["stage"])
            case "finish":
                result = _finish_assessment(
                    logo, brief, cid, candidate, payload["record"], payload["execution"]
                )
            case "current":
                if logo is None or brief is None:
                    raise ValueError("current proof requires logo and brief")
                require_current(logo, brief, cid, payload["proof"], stage=payload["stage"])
                result = None
            case "images":
                result = _prepare_images(
                    brief,
                    candidate,
                    Path(payload["flat_mark"]) if payload["flat_mark"] else None,
                    Path(payload["dest"]),
                )
            case "details":
                result = _detail_inputs(logo, cid, candidate, Path(payload["dest"]))
            case _:
                raise ValueError("unknown eligibility operation")
        return {"result": result}
    except (OSError, ValueError, ToolError) as exc:
        return {"error": str(exc), "error_type": type(exc).__name__}
