"""Prepare blinded owner review with the same crops used for Jev."""

from __future__ import annotations

import html
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from logo_maker import study
from logo_maker.campaign import _read, _write
from logo_maker.sampling_diagnostics import sha256
from logo_maker.study_render import digest

LABELS = ("sound", "defect", "insufficient")


def prepare_panel(project: Path, specification: Path, output: Path) -> Path:
    rows = _read(specification)["cases"]
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("prepare at least three distinct comparison cases")
    order = sorted(rows, key=digest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".calibration-", dir=output.parent) as temporary:
        staging = Path(temporary) / "panel"
        public = staging / "review"
        public.mkdir(parents=True)
        evidence, sections, seen = {}, [], set()
        for number, case in enumerate(order, 1):
            root = study._safe(project, case["study"])
            manifest, binding = study._verify_manifest(root, root.name)
            folder = study._safe(root, manifest["concepts"][case["concept"]])
            design = _read(folder / "design.json")
            refs = [
                ref
                for ref in design["references"]
                if ref.get("sha256") == case["reference_sha256"]
                and ref.get("match")
                and ref.get("review_allowed") is True
                and ref["use"] == "craft"
            ]
            if len(refs) != 1:
                raise ValueError("select one permitted matched development photo")
            ref = refs[0]
            key = binding, ref["sha256"], case.get("view", ref["match"]["view"])
            if key in seen:
                raise ValueError("duplicate calibration case")
            seen.add(key)
            if view := case.get("view"):
                ref["match"] = {**ref["match"], "view": view, "render_region": [0, 0, 1, 1]}
            approved = {**design, "references": refs}
            brief = study._brief_for_review(root, folder, approved, manifest["files"])
            case_id = f"{number:02d}"
            crops = study._review_evidence(folder, approved, manifest["files"], brief, staging)
            match = crops["matches"][ref["sha256"]]
            files, pictures = {}, []
            for role, title in (("candidate_detail", "Design"), ("reference_detail", "Reference")):
                name = f"{case_id}-{role}.png"
                shutil.move(match[role], public / name)
                files[role] = {"file": name, "sha256": sha256(public / name)}
                pictures.append(
                    f'<figure><a href="{name}"><img src="{name}" alt="{title}"></a>'
                    f"<figcaption>{title}</figcaption></figure>"
                )
            feature = match["feature_name"] or match["feature"]
            evidence[case_id] = {
                "study_manifest_sha256": binding,
                "source": case,
                "feature": match["feature"],
                "feature_name": feature,
                "view_sha256": match["view_sha256"],
                "files": files,
                "intended_appearances": match["intended_appearances"],
            }
            sections.append(
                f"<section><h2>{case_id} · {html.escape(feature)}</h2>"
                f'<div class="pair">{"".join(pictures)}</div></section>'
            )
        _write(staging / "evidence.json", {"schema": 1, "cases": evidence})
        (public / "index.html").write_text(_PAGE + "".join(sections) + "</html>\n")
        staging.rename(output)
    return output / "review" / "index.html"


_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Construction review</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;color:#202524;background:#f7f7f4;
max-width:1040px;margin:auto;padding:28px}section{padding:10px 0 26px;
border-top:1px solid #c4c9c5}.pair{display:grid;grid-template-columns:repeat(2,1fr);
gap:16px}figure{margin:0}img{width:100%;height:280px;object-fit:contain;
background:#edece8}figcaption{font-weight:600}
@media(max-width:600px){img{height:160px}}
</style>
<h1>Construction review</h1>
<p>Judge the named feature in each design against the reference. Select
<strong>sound</strong> if the feature meets the reference finish,
<strong>defect</strong> if a visible construction or finish problem puts it below the
reference, or <strong>insufficient</strong> if the views cannot support the comparison.
For a defect, name what you see. Click an image for native detail.</p>
"""


def freeze_labels(panel: Path, labels: Path, *, owner_note: str) -> Path:
    """Bind independent labels and approved error limits before running an evaluation."""
    if not owner_note.strip():
        raise ValueError("record the independent reviewer's actual decision")
    evidence = _read(panel / "evidence.json")
    submitted = _read(labels)
    cases = submitted["cases"]
    if cases.keys() != evidence["cases"].keys():
        raise ValueError("label every case exactly once")
    if any(row.get("label") not in LABELS for row in cases.values()):
        raise ValueError("each case needs an independent label")
    for cid, row in cases.items():
        if row["label"] == "defect" and not str(row.get("observation", "")).strip():
            raise ValueError(f"identify the visible defect for case {cid}")
        for item in evidence["cases"][cid]["files"].values():
            if sha256(panel / "review" / item["file"]) != item["sha256"]:
                raise ValueError(f"review image changed for case {cid}")
    tolerances = submitted["tolerances"]
    transitions = {
        f"{actual}_as_{predicted}"
        for actual in LABELS
        for predicted in (*LABELS, "unsettled")
        if actual != predicted
    }
    if (
        not tolerances
        or tolerances.keys() - transitions
        or any(type(value) is not int or value < 0 for value in tolerances.values())
    ):
        raise ValueError("approve nonnegative error limits for named classification mistakes")
    frozen = {
        "panel_sha256": sha256(panel / "evidence.json"),
        "owner_note": owner_note,
        "cases": cases,
        "tolerances": tolerances,
    }
    path = panel / "labels.json"
    if path.exists():
        raise ValueError("frozen labels already exist for this panel")
    _write(path, frozen)
    return path


def _observable_comparison(client, paths, row, label) -> tuple[str, list]:
    from logo_maker.eligibility import _statuses
    from logo_maker.jev import questions
    from logo_maker.jev.client import Image

    prompts = questions.matched_craft_calibration_questions()
    comparisons: list[dict[str, Any]] = []
    for order in (tuple(paths), tuple(reversed(paths))):
        state = {
            **{name: Image(paths[name]) for name in order},
            "feature": row["feature_name"],
            "intended_appearance": row["intended_appearances"]["candidate"],
        }
        answers = client.ask(state, prompts, label=f"{label}-{order[0]}-first")
        comparisons.append(
            {"order": order, "answers": answers, "checks": _statuses(answers, prompts)}
        )
    checks = [comparison["checks"] for comparison in comparisons]
    visible = ("candidate_visible", "reference_visible")
    if any(all(check[key] == "fail" for check in checks) for key in visible):
        return "insufficient", comparisons
    if all(check[key] == "pass" for key in visible for check in checks):
        if all(check["candidate_defect"] == "fail" for check in checks):
            return "sound", comparisons
        if all(check["candidate_defect"] == "pass" for check in checks):
            return "defect", comparisons
    return "unsettled", comparisons


def _triage_comparison(client, paths, row, label) -> tuple[str, list]:
    from logo_maker.jev.client import Image
    from logo_maker.jev.questions import construction_triage_question

    prompts = construction_triage_question()
    outcomes = {
        "visible_intact_feature": "sound",
        "visible_damage_or_construction_error": "defect",
        "feature_outside_inspectable_area": "insufficient",
        "comparison_unclear": "unsettled",
    }
    comparisons: list[dict[str, Any]] = []
    for order in (tuple(paths), tuple(reversed(paths))):
        features = {
            "feature": row["feature_name"],
            "intended_appearance": row["intended_appearances"]["candidate"],
        }
        state = {**{name: Image(paths[name]) for name in order}, **features}
        answers = client.ask(state, prompts, label=f"{label}-{order[0]}-first")
        comparisons.append({"order": order, "answers": answers})
    choices = {
        comparison["answers"]["construction_observation"]["choice"] for comparison in comparisons
    }
    decision = outcomes[choices.pop()] if len(choices) == 1 else "unsettled"
    return decision, comparisons


def evaluate(panel: Path, client, *, rubric: str, variant: str = "baseline") -> dict:
    """Score the exact independently labeled inputs and report each error type."""
    from types import SimpleNamespace

    from logo_maker.eligibility import _matched_rows

    if variant not in ("baseline", "observable", "triage"):
        raise ValueError("choose baseline, observable, or triage evaluation")
    evidence_path = panel / "evidence.json"
    labels_path = panel / "labels.json"
    evidence, labels = _read(evidence_path), _read(labels_path)
    if sha256(evidence_path) != labels["panel_sha256"]:
        raise ValueError("calibration inputs differ from the labeled panel")
    labels_present = sorted({row["label"] for row in labels["cases"].values()})
    partition = evidence.get("partition", "development")
    if partition == "held_out" and set(labels_present) != set(LABELS):
        raise ValueError("held-out evaluation needs sound, defect, and insufficient evidence cases")
    errors = {}
    comparisons = {}
    for cid, row in evidence["cases"].items():
        paths = {}
        for role, file in row["files"].items():
            path = study._safe(panel / "review", file["file"])
            if sha256(path) != file["sha256"]:
                raise ValueError(f"calibration crop changed: {cid}/{role}")
            paths[role] = path
        expected = labels["cases"][cid]["label"]
        if variant == "observable":
            predicted, result = _observable_comparison(client, paths, row, f"calibration-{cid}")
        elif variant == "triage":
            predicted, result = _triage_comparison(client, paths, row, f"calibration-{cid}")
        else:
            result = _matched_rows(
                client,
                SimpleNamespace(path=paths["reference_detail"]),
                {**row, **paths, "view": "calibration", "regions": {}},
                row["files"]["candidate_detail"]["sha256"],
                f"calibration-{cid}",
            )
            predicted = {
                "pass": "sound",
                "fail": "defect",
                "missing_evidence": "insufficient",
                "unsettled": "unsettled",
            }[result["status"]]
        if expected != predicted:
            key = f"{expected}_as_{predicted}"
            errors[key] = errors.get(key, 0) + 1
        comparisons[cid] = {"expected": expected, "predicted": predicted, "judgments": result}
    exceeded = {
        key: count
        for key, count in errors.items()
        if key in labels["tolerances"] and count > labels["tolerances"][key]
    }
    return {
        "panel_sha256": sha256(evidence_path),
        "labels_sha256": sha256(labels_path),
        "rubric_sha256": rubric,
        "variant": variant,
        "partition": partition,
        "judge": {"model": client.model, "endpoint": client.url},
        "labels_present": labels_present,
        "errors": errors,
        "exceeded": exceeded,
        "comparisons": comparisons,
    }


def qualification(logo, state) -> str:
    """Report whether the installed production evaluator has current held-out evidence."""
    binding = state.get("evaluator")
    if not binding:
        return "pending"
    try:
        panel = study._safe(logo.root, binding["panel"])
        result_path = study._safe(panel, binding["result"])
        report = _read(result_path)
        if (
            sha256(result_path) != binding["sha256"]
            or report["panel_sha256"] != sha256(panel / "evidence.json")
            or report["labels_sha256"] != sha256(panel / "labels.json")
            or report["rubric_sha256"] != study.review_rubric(True)
        ):
            return "stale"
        if (
            report["partition"] != "held_out"
            or report["variant"] != "baseline"
            or set(report["labels_present"]) != set(LABELS)
        ):
            return "out_of_scope"
        if report["exceeded"]:
            return "failed"
        # A judge that abstains on every labeled sound case cannot qualify any design.
        if not any(
            row["expected"] == row["predicted"] == "sound" for row in report["comparisons"].values()
        ):
            return "failed"
        for row in _read(panel / "evidence.json")["cases"].values():
            if any(
                sha256(study._safe(panel / "review", file["file"])) != file["sha256"]
                for file in row["files"].values()
            ):
                return "stale"
        return "qualified"
    except (OSError, ValueError, KeyError, TypeError):
        return "stale"
