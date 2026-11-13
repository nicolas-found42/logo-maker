"""Evidence review and frozen requirements before logo authoring."""

from __future__ import annotations

import hashlib
import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any

from logo_maker.brief import BriefError, load
from logo_maker.jev import client as client_module
from logo_maker.jev import questions as Q
from logo_maker.jev.client import Image, JevAsker, JevClient, JevError
from logo_maker.paths import LogoDir

TEMPLATE = """# Use available project/owner evidence first. Do not invent facts to fill this record.
schema = 1
communication_priority = ""
design_latitude = [] # choices intentionally left to design, not missing business facts

[[sources]]
id = "project"
kind = "project" # owner | project | fixture
path = "inputs/project.txt"
excerpt = "" # exact text from the source file

[[facts]]
id = "activity"
claim = ""
status = "established" # established | assumption | unknown | conflict
sources = ["project"]
essential = true

[[requirements]]
id = "communication"
claim = ""
kind = "communication" # business | communication | usage | visual
origin = "proposal" # owner | project | proposal
priority = "prefer" # must | prefer | avoid | open
sources = [] # owner/project mandates need supporting sources
"""

PLAN_TEMPLATE = """schema = 1
requirements_revision = "{revision}"
hypothesis = ""
visual_mechanism = ""
requirement_ids = [] # IDs from frozen requirements; proposals remain proposals
assumptions = []

[[details]]
feature = ""
purpose = ""
intended_scale = "" # where this matters: flat, small application, hero, native detail
construction = ""
deletion_test = "" # what would change if removed; ornament count is not quality
"""


def review_plan(logo: LogoDir, concept_id: str, client: JevAsker | None = None) -> dict:
    """Review authored intent before rendering; this never certifies rendered execution."""
    frozen = current(logo)
    path = logo.concept(concept_id) / "plan.toml"
    if not path.exists():
        path.write_text(PLAN_TEMPLATE.format(revision=frozen["requirements_revision"]))
    record = {
        "status": "missing_evidence",
        "concept_id": concept_id,
        "missing": [],
        "files": [path],
        "questions": [],
    }
    try:
        state, inputs = _plan_snapshot(logo, concept_id)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record["missing"] = [f"fill {path} with a concept hypothesis and detail plan: {exc}"]
        return _record(logo, record, journal="plan-reviews.jsonl")
    record.update(state=state, inputs=inputs)
    saved = path.with_name("plan-review.json")
    if saved.exists():
        try:
            previous = json.loads(saved.read_text())
            if (
                isinstance(previous, dict)
                and previous.get("status") == "pass"
                and previous.get("inputs") == inputs
                and previous.get("state") == state
                and _has_passing_answers(
                    previous,
                    Q.plan_review_questions(
                        state["plan"]["details"], state["authoring_obligations"]
                    ),
                )
            ):
                return previous
        except (OSError, ValueError):
            pass  # An invalid cache supplies no evidence; review the authored plan again.
    questions = Q.plan_review_questions(state["plan"]["details"], state["authoring_obligations"])
    try:
        client = client or JevClient(logo)
        general = {
            key: value for key, value in questions.items() if not key.startswith("plan_obligation_")
        }
        jobs = [(state, general, f"plan-{concept_id}")]
        for obligation in state["authoring_obligations"]:
            qid = f"plan_obligation_{obligation['id']}"
            focused = {**state}
            if obligation.get("baseline_image"):
                focused["prior_baseline"] = Image(logo.root / obligation["baseline_image"])
            jobs.append((focused, {qid: questions[qid]}, f"plan-{concept_id}-{obligation['id']}"))
        answers = _ask_jobs(client, jobs)
        checks = _answer_checks(answers, questions)
    except (KeyError, TypeError, ValueError, JevError) as exc:
        record.update(status="api_error", error=str(exc))
        _record(logo, record, journal="plan-reviews.jsonl")
        raise JevError(f"plan review failed: {exc}") from exc
    status = _outcome(checks)
    record.update(status=status, answers=answers, checks=checks)
    try:
        now_state, now = _plan_snapshot(logo, concept_id)
        unchanged = now == inputs and now_state == state
    except (OSError, ValueError, KeyError, TypeError):
        unchanged = False
    if not unchanged:
        record.update(
            status="missing_evidence", missing=["plan/requirements changed during review"]
        )
    elif status == "pass":
        record["files"] = []
        saved.write_text(json.dumps(record, indent=2, default=str) + "\n")
    else:
        record["missing"] = [
            f"plan {qid}: {value}" for qid, value in checks.items() if value != "pass"
        ]
    return _record(logo, record, journal="plan-reviews.jsonl")


def _plan_snapshot(logo: LogoDir, concept_id: str) -> tuple[dict, dict]:
    frozen = current(logo)
    folder = logo.concept(concept_id)
    path = folder / "plan.toml"
    plan = tomllib.loads(path.read_text())
    if type(plan.get("schema")) is not int or plan["schema"] != 1:
        raise ValueError("plan schema 1 required")
    if plan.get("requirements_revision") != frozen["requirements_revision"]:
        raise ValueError("plan must name the current requirements revision")
    for key in ("hypothesis", "visual_mechanism"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError(f"plan {key} required")
    requirement_ids = {row["id"] for row in frozen["state"]["requirements"]}
    selected = plan.get("requirement_ids")
    if (
        not isinstance(selected, list)
        or any(not isinstance(value, str) or value not in requirement_ids for value in selected)
        or (requirement_ids and not selected)
    ):
        raise ValueError("plan must cite applicable frozen requirement IDs")
    assumptions = plan.get("assumptions")
    if not isinstance(assumptions, list) or any(
        not isinstance(value, str) for value in assumptions
    ):
        raise ValueError("plan assumptions must be an explicit list")
    details = plan.get("details")
    fields = ("feature", "purpose", "intended_scale", "construction", "deletion_test")
    if (
        not isinstance(details, list)
        or not details
        or any(
            not isinstance(row, dict)
            or any(not isinstance(row.get(key), str) or not row[key].strip() for key in fields)
            for row in details
        )
    ):
        raise ValueError(
            "each detail needs feature, purpose, intended_scale, construction and deletion_test"
        )
    concept = json.loads((folder / "concept.json").read_text())
    if not isinstance(concept, dict):
        raise ValueError("concept.json must be a record")
    identity = {
        key: frozen["state"][key]
        for key in (
            "business",
            "design_direction",
            "communication_priority",
            "design_latitude",
            "facts",
            "requirements",
        )
    }
    state = {
        "requirements": identity,
        "authoring_obligations": [
            row for row in frozen["state"]["obligations"] if row["kind"] == "authoring"
        ],
        "concept": concept,
        "plan": plan,
    }
    inputs = {
        "requirements_revision": frozen["requirements_revision"],
        "plan_sha256": _sha(path),
        "concept_sha256": _sha(folder / "concept.json"),
        "rubric_sha256": _sha(Path(Q.__file__)),
        "review_protocol_sha256": _sha(Path(__file__)),
        "transport_sha256": _sha(Path(client_module.__file__)),
    }
    return state, inputs


def current_plan(logo: LogoDir, concept_id: str) -> dict:
    """Read the exact current plan review without provider calls or output mutation."""
    try:
        state, inputs = _plan_snapshot(logo, concept_id)
        record = json.loads((logo.concept(concept_id) / "plan-review.json").read_text())
        if (
            not isinstance(record, dict)
            or record.get("status") != "pass"
            or record.get("state") != state
            or record.get("inputs") != inputs
            or not _has_passing_answers(
                record,
                Q.plan_review_questions(state["plan"]["details"], state["authoring_obligations"]),
            )
        ):
            raise ValueError("plan review is stale or invalid")
        return record
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"current plan review required for {concept_id}: {exc}") from exc


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _answer_checks(answers: dict, questions: dict) -> dict[str, str]:
    checks = {}
    for qid in questions:
        value = answers[qid]["noul"]
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError(f"invalid Noul: {qid}")
        checks[qid] = Q.qa_status(value)
    return checks


def _ask_jobs(client: JevAsker, jobs: list[tuple[dict, dict, str]]) -> dict:
    answers = {}
    replies = client.ask_many(jobs)
    if len(replies) != len(jobs):
        raise ValueError("review returned an invalid request count")
    for (_, expected, _), reply in zip(jobs, replies, strict=True):
        if not isinstance(reply, dict) or reply.keys() != expected.keys():
            raise ValueError("review request answer keys are missing or unexpected")
        answers.update(reply)
    return answers


def _outcome(checks: dict[str, str]) -> str:
    if "fail" in checks.values():
        return "fail"
    return "pass" if checks and all(value == "pass" for value in checks.values()) else "unsettled"


def _has_passing_answers(record: dict, questions: dict) -> bool:
    """A cached status is not a substitute for its complete, well-formed judgment evidence."""
    try:
        checks = _answer_checks(record["answers"], questions)
        return record["checks"] == checks and _outcome(checks) == "pass"
    except (KeyError, TypeError, ValueError):
        return False


def _rows(evidence: dict, key: str) -> list[dict]:
    rows = evidence.get(key, [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{key} must be an array of records")
    ids = [row.get("id") for row in rows]
    if any(
        not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name)
        for name in ids
    ):
        raise ValueError(f"{key} needs nonempty named IDs")
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate {key} ID")
    return rows


def _source_ids(row: dict, sources: dict, *, required: bool) -> None:
    ids = row.get("sources", [])
    if (
        not isinstance(ids, list)
        or any(not isinstance(name, str) or name not in sources for name in ids)
        or (required and not ids)
    ):
        raise ValueError(f"{row['id']}: valid supporting source IDs required")


def _required(row: dict, key: str, kind: str) -> Any:
    """A row field the snapshot needs, failing with the row id rather than a bare KeyError."""
    if key not in row:
        raise ValueError(f"{kind} {row.get('id', '?')}: missing {key!r}")
    return row[key]


def _row_file(logo: LogoDir, row: dict, kind: str, key: str = "path") -> Path:
    """A row's file field, relative to the logo folder, that must name an existing file."""
    relative = _required(row, key, kind)
    if not isinstance(relative, str):
        raise ValueError(f"{kind} {row.get('id', '?')}: {key} must be a string")
    path = (logo.root / relative).resolve()
    if not path.is_file():
        raise ValueError(f"{kind} {row.get('id', '?')}: {key} {path} is not a file")
    return path


def _snapshot(logo: LogoDir) -> tuple[dict, dict]:
    brief = load(logo.brief)
    for ref in brief.references:
        # brief.load allows a craft reference that is not yet on disk; review needs its pixels.
        if not ref.path.is_file():
            raise BriefError(f"reference {ref.path} ({ref.use}) is not a file")
    evidence_path = logo.root / "brief-evidence.toml"
    evidence = tomllib.loads(evidence_path.read_text())
    if (
        type(evidence.get("schema")) is not int
        or evidence["schema"] != 1
        or not isinstance(evidence.get("communication_priority"), str)
        or not evidence["communication_priority"].strip()
    ):
        raise ValueError("schema 1 and a communication_priority are required")
    latitude = evidence.get("design_latitude", [])
    if not isinstance(latitude, list) or any(not isinstance(value, str) for value in latitude):
        raise ValueError("design_latitude must be named open design choices")
    sources = {}
    source_hashes = {}
    for source in _rows(evidence, "sources"):
        if source.get("kind") not in {"owner", "project", "fixture"}:
            raise ValueError(f"source {source['id']}: invalid source kind")
        path = _row_file(logo, source, "source")
        excerpt = _required(source, "excerpt", "source")
        if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in path.read_text():
            raise ValueError(f"source {source['id']}: exact nonempty excerpt required")
        sources[source["id"]] = {**source, "sha256": _sha(path)}
        source_hashes[str(path)] = _sha(path)
    facts = _rows(evidence, "facts")
    if not sources or not facts:
        raise ValueError("source evidence and factual claims are required")
    for fact in facts:
        if not isinstance(fact.get("claim"), str) or not fact["claim"].strip():
            raise ValueError("every fact needs a claim")
        if fact.get("status") not in {"established", "assumption", "unknown", "conflict"}:
            raise ValueError(f"fact {fact['id']}: invalid status")
        if not isinstance(fact.get("essential", False), bool):
            raise ValueError(f"fact {fact['id']}: essential must be boolean")
        _source_ids(fact, sources, required=fact["status"] == "established")
    requirements = _rows(evidence, "requirements")
    obligations = _rows(evidence, "obligations")
    if {row["id"] for row in requirements} & {row["id"] for row in obligations}:
        raise ValueError("identity requirements and workflow obligations need distinct IDs")
    for requirement in [*requirements, *obligations]:
        kinds = (
            {"brief", "authoring", "validation"}
            if requirement in obligations
            else {"business", "communication", "usage", "visual"}
        )
        if (
            not isinstance(requirement.get("claim"), str)
            or not requirement["claim"].strip()
            or requirement.get("kind") not in kinds
            or requirement.get("origin") not in {"owner", "project", "proposal"}
            or requirement.get("priority") not in {"must", "prefer", "avoid", "open"}
        ):
            raise ValueError(
                f"requirement {requirement['id']}: invalid claim, kind, origin or priority"
            )
        _source_ids(requirement, sources, required=requirement["origin"] != "proposal")
        if requirement["origin"] == "owner" and not any(
            sources[name]["kind"] == "owner" for name in requirement["sources"]
        ):
            raise ValueError(f"requirement {requirement['id']}: owner source required")
    previous_briefs = {}
    baseline_hashes = {}
    for obligation in obligations:
        if obligation["priority"] != "must":
            raise ValueError("workflow obligations must retain mandatory scope")
        if obligation["kind"] == "brief":
            baseline = _row_file(logo, obligation, "obligation", "baseline")
            try:
                previous_briefs[obligation["id"]] = load(baseline).as_state()
            except BriefError as exc:  # the baseline, not brief.toml, needs the fix
                raise ValueError(f"obligation {obligation['id']}: baseline {exc}") from exc
            baseline_hashes[str(baseline)] = _sha(baseline)
        if obligation["kind"] == "authoring" and obligation.get("baseline_image"):
            baseline = _row_file(logo, obligation, "obligation", "baseline_image")
            baseline_hashes[str(baseline)] = _sha(baseline)
        if obligation["kind"] == "validation":
            minimum = obligation.get("minimum_references")
            if type(minimum) is not int or minimum < 1:
                raise ValueError("validation obligation needs minimum_references >= 1")
            if len({_sha(ref.path) for ref in brief.references if ref.use == "craft"}) < minimum:
                raise ValueError("validation obligation needs more distinct craft reference images")
            targets = obligation.get("expected_references")
            if not isinstance(targets, list) or len(targets) < minimum:
                raise ValueError("validation obligation needs pinned reference identity records")
            actual = {_sha(ref.path) for ref in brief.references if ref.use == "craft"}
            pinned = set()
            for target in targets:
                if (
                    not isinstance(target, dict)
                    or not isinstance(target.get("label"), str)
                    or not target["label"].strip()
                ):
                    raise ValueError("reference identity needs a descriptive label")
                target_path = _row_file(logo, target, "expected_references")
                digest = _sha(target_path)
                if digest != target.get("sha256") or digest not in actual:
                    raise ValueError(
                        "validation reference identity is missing, changed or substituted"
                    )
                pinned.add(digest)
                baseline_hashes[str(target_path)] = digest
            if len(pinned) < minimum:
                raise ValueError("pinned reference identity records must be distinct")
    brief_state = brief.as_state()
    business_keys = {"name", "summary", "audience", "tone", "uses"}
    state = {
        "business": {key: value for key, value in brief_state.items() if key in business_keys},
        "design_direction": {
            key: value for key, value in brief_state.items() if key not in business_keys
        },
        "communication_priority": evidence["communication_priority"],
        "design_latitude": latitude,
        "facts": facts,
        "sources": sources,
        "requirements": requirements,
        "obligations": obligations,
        "previous_briefs": previous_briefs,
    }
    if latitude:
        state["design_direction"]["open_choices"] = latitude
    references = [
        {"path": str(ref.path), "use": ref.use, "note": ref.note, "sha256": _sha(ref.path)}
        for ref in brief.references
    ]
    if references:
        state["design_direction"]["references"] = references
    inputs = {
        "brief_sha256": _sha(logo.brief),
        "evidence_sha256": _sha(evidence_path),
        "sources": source_hashes,
        "references": {row["path"]: row["sha256"] for row in references},
        "baselines": baseline_hashes,
        "rubric_sha256": _sha(Path(Q.__file__)),
        "review_protocol_sha256": _sha(Path(__file__)),
        "transport_sha256": _sha(Path(client_module.__file__)),
    }
    return state, inputs


def _record(logo: LogoDir, record: dict, *, journal: str = "brief-reviews.jsonl") -> dict:
    with (logo.qa / journal).open("a") as stream:
        stream.write(json.dumps(record, default=str, sort_keys=True) + "\n")
    return record


def current(logo: LogoDir) -> dict:
    """Require current frozen inputs without performing a provider call or changing outputs."""
    try:
        state, inputs = _snapshot(logo)
        frozen_path = logo.ideation / "requirements.json"
        if not frozen_path.exists():
            raise ValueError("the brief has not been reviewed yet")
        frozen = json.loads(frozen_path.read_text())
        if (
            not isinstance(frozen, dict)
            or frozen.get("status") != "pass"
            or frozen.get("inputs") != inputs
            or frozen.get("state") != state
            or frozen.get("requirements_revision") != _digest(inputs)
            or not _has_passing_answers(
                frozen,
                Q.brief_review_questions(
                    state["facts"], state["requirements"], state["sources"], state["obligations"]
                ),
            )
        ):
            raise ValueError("requirements freeze is stale or invalid")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"current brief review required; run logo-maker brief: {exc}") from exc
    return frozen


def review(logo: LogoDir, client: JevAsker | None = None, *, revision_reason: str = "") -> dict:
    path = logo.root / "brief-evidence.toml"
    if not path.exists():
        path.write_text(TEMPLATE)
    record = {
        "status": "missing_evidence",
        "missing": [],
        "files": [path],
        "questions": [],
    }
    try:
        state, inputs = _snapshot(logo)
    except BriefError as exc:
        record["missing"] = [f"fix brief.toml: {exc}"]
        record["files"] = [logo.brief]
        return _record(logo, record)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record["missing"] = [
            f"fill brief-evidence.toml from available project/owner evidence: {exc}"
        ]
        return _record(logo, record)
    record.update(state=state, inputs=inputs, requirements_revision=_digest(inputs))
    frozen = logo.ideation / "requirements.json"
    previous = None
    if frozen.exists():
        try:
            previous = json.loads(frozen.read_text())
            if (
                not isinstance(previous, dict)
                or not {"status", "inputs", "state", "requirements_revision"} <= previous.keys()
                or previous["requirements_revision"] != _digest(previous["inputs"])
                or (previous["inputs"] == inputs and previous["state"] != state)
                or previous["status"] != "pass"
                or not _has_passing_answers(
                    previous,
                    Q.brief_review_questions(
                        previous["state"]["facts"],
                        previous["state"]["requirements"],
                        previous["state"]["sources"],
                        previous["state"]["obligations"],
                    )
                    if previous["inputs"] == inputs
                    else previous["checks"],
                )
            ):
                raise ValueError("invalid frozen requirements schema")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record["missing"] = [f"current requirements record is unreadable: {exc}"]
            return _record(logo, record)
        if previous.get("status") == "pass" and previous.get("inputs") == inputs:
            return previous
        if not revision_reason.strip():
            record["missing"] = ["requirements changed: supply an explicit revision reason"]
            return _record(logo, record)
        record["revision_reason"] = revision_reason.strip()
    unresolved = {
        fact["id"]: fact["status"]
        for fact in state["facts"]
        if fact.get("essential", False) and fact["status"] != "established"
    }
    if unresolved:
        priority = {"conflict": 0, "unknown": 1, "assumption": 2}
        selected = min(unresolved, key=lambda name: priority[unresolved[name]])
        status = (
            "fail"
            if "conflict" in unresolved.values()
            else "missing_evidence"
            if "unknown" in unresolved.values()
            else "unsettled"
        )
        record.update(
            status=status,
            missing=[f"required fact {name}: {value}" for name, value in unresolved.items()],
            questions=[Q.brief_followup(f"fact_{selected}", unresolved[selected])],
        )
        return _record(logo, record)
    questions = Q.brief_review_questions(
        state["facts"], state["requirements"], state["sources"], state["obligations"]
    )
    try:
        client = client or JevClient(logo)
        general = {
            key: question
            for key, question in questions.items()
            if key != "mandates" and not key.startswith("source_")
        }
        jobs = [(state, general, "brief-review")]
        for source_id, source in state["sources"].items():
            covered = [
                {
                    **{key: row[key] for key in ("id", "kind", "claim", "origin", "priority")},
                    "scope": Q.OBLIGATION_SCOPES[row["kind"]]
                    if row["kind"] in Q.OBLIGATION_SCOPES
                    else Q.REQUIREMENT_SCOPES[row["priority"]],
                    **(
                        {
                            "reference_labels": [
                                target["label"] for target in row["expected_references"]
                            ]
                        }
                        if row["kind"] == "validation"
                        else {}
                    ),
                }
                for row in [*state["requirements"], *state["obligations"]]
                if source_id in row.get("sources", [])
                and row["origin"] != "proposal"
                and (source["kind"] != "owner" or row["origin"] == "owner")
            ]
            jobs.append(
                (
                    {
                        "source": {
                            **{key: source[key] for key in ("kind", "excerpt")},
                            "context": Q.SOURCE_CONTEXTS[source["kind"]],
                        },
                        "recorded_directions": covered,
                    },
                    Q.brief_source_questions(source_id),
                    f"brief-source-{source_id}",
                )
            )
        if "mandates" in questions:
            direction = dict(state["design_direction"])
            references = [r for r in direction.pop("references", []) if r["use"] != "craft"]
            if references:
                direction["references"] = references
            jobs.append(
                (
                    {
                        "business": state["business"],
                        "design_direction": direction,
                        "requirements": state["requirements"],
                    },
                    {"mandates": questions["mandates"]},
                    "brief-direction-preservation",
                )
            )
        answers = _ask_jobs(client, jobs)
        checks = _answer_checks(answers, questions)
    except (KeyError, TypeError, ValueError, JevError) as exc:
        record.update(status="api_error", error=str(exc))
        _record(logo, record)
        raise JevError(f"brief review failed: {exc}") from exc
    status = _outcome(checks)
    record.update(status=status, answers=answers, checks=checks)
    try:
        current_state, current_inputs = _snapshot(logo)
        unchanged = current_inputs == inputs and current_state == state
    except (OSError, ValueError, KeyError, TypeError):
        unchanged = False
    if not unchanged:
        record.update(
            status="missing_evidence",
            missing=["brief/source evidence changed during judgment; review again"],
        )
        return _record(logo, record)
    if status != "pass":
        record["missing"] = [
            f"brief {qid}: {value}" for qid, value in checks.items() if value != "pass"
        ]
        failed = [qid for qid, value in checks.items() if value != "pass"]
        priority = {
            "consistent": 0,
            "requirements_complete": 1,
            "grounding": 2,
            "activity": 3,
            "audience": 4,
        }
        selected = min(
            failed,
            key=lambda qid: priority.get(
                qid, 1 if qid.startswith(("fact_", "requirement_", "source_")) else 5
            ),
        )
        record["questions"] = [Q.brief_followup(selected, checks[selected])]
        return _record(logo, record)
    if previous is not None:
        history = logo.root / "history" / "requirements"
        history.mkdir(parents=True, exist_ok=True)
        (history / f"{previous['requirements_revision']}.json").write_bytes(frozen.read_bytes())
    frozen.write_text(json.dumps(record, indent=2, default=str) + "\n")
    return _record(logo, record)
