"""Content-bound creative revisions. Jev judges; the calling agent authors and inspects."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from logo_maker.paths import REPO_ROOT, LogoDir, concept_slug
from logo_maker.sampling import Budget

CONSTRUCTION_FIELDS = (
    "symbol",
    "brand_geometry",
    "material_construction",
    "intended_appearance",
    "disproof",
    "current_description",
)
OUTPUT_NAMES = {
    "preview.png",
    "final.png",
    "test.png",
    "scene.blend",
    "model.glb",
    "motif-sizes.png",
    "inspection.json",
    "inspection-final.json",
    "render-state.json",
    "diagnosis.json",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def construction(folder: Path) -> dict:
    from logo_maker.pipeline import AuthoringNeeded

    path = folder / "construction.json"
    data = read(path) if path.exists() else {}
    if any(not isinstance(data.get(k), str) or not data[k].strip() for k in CONSTRUCTION_FIELDS):
        raise AuthoringNeeded("write the per-concept construction/meaning brief", [path])
    deps = data.get("dependencies")
    if not isinstance(deps, list) or any(
        not isinstance(p, str) or not (folder / p).is_file() for p in deps
    ):
        raise AuthoringNeeded(
            "construction.dependencies must list existing source/asset paths", [path]
        )
    info_path = folder / "concept.json"
    info = read(info_path) if info_path.exists() else {}
    if info.get("description") != data["current_description"]:
        raise AuthoringNeeded(
            "update concept.description to the construction current_description", [info_path, path]
        )
    return data


def concept_sources(folder: Path, *, exclude: set[str] | None = None) -> dict[str, Path]:
    """One source/asset inventory shared by motif derivation and render invalidation."""
    files = {}
    excluded = OUTPUT_NAMES | (exclude or set())
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if (
            path.is_file()
            and not any(part.startswith(".") or part == "__pycache__" for part in relative.parts)
            and relative.parts[0] != "meshes"
            and path.name not in excluded
            and path.suffix not in {".blend1", ".pyc"}
        ):
            files[f"concept/{relative}"] = path
    intent = folder / "construction.json"
    if intent.exists():
        for i, name in enumerate(read(intent).get("dependencies", [])):
            path = (folder / name).resolve()
            if path.is_file():
                files[f"dependency/{i}/{path.name}"] = path
    return files


def inputs(logo: LogoDir, folder: Path) -> dict[str, Path]:
    """Explicit custom dependencies plus local sources and the owning tool's implementation."""
    construction(folder)
    files = {"brief.toml": logo.brief, **concept_sources(folder)}
    from logo_maker.brief import load

    for i, ref in enumerate(load(logo.brief).references):
        files[f"reference/{i}/{ref.path.name}"] = ref.path
    for base in (REPO_ROOT / "logo_maker",):
        for path in sorted(base.rglob("*")):
            if path.suffix in {".py", ".toml"} and "__pycache__" not in path.parts:
                files[f"tool/{path.relative_to(base)}"] = path
    return files


def source_hashes(logo: LogoDir, folder: Path) -> dict[str, str]:
    return {name: digest(path) for name, path in inputs(logo, folder).items()}


def history(logo: LogoDir, cid: str) -> list[dict]:
    root = logo.qa / "revisions" / concept_slug(cid)
    return [read(p) for p in sorted(root.glob("*/revision.json"))]


def current(
    logo: LogoDir, cid: str, quality: str = "preview", *, budget: Budget | None = None
) -> dict | None:
    folder = logo.concept(cid)
    state = folder / "render-state.json"
    if not state.exists():
        return None
    record = read(state).get(quality)
    if not record or record["source_sha256"] != source_hashes(logo, folder):
        return None
    image = folder / f"{quality}.png"
    if not image.exists() or record["image_sha256"] != digest(image):
        return None
    from logo_maker.render import artifact_current, inspection_artifact_current

    check = inspection_artifact_current if quality == "preview" else artifact_current
    return record if check(folder, quality, budget=budget) else None


def capture(logo: LogoDir, cid: str, quality: str, *, budget: Budget | None = None) -> dict:
    """Render a new revision once; archive provenance before another render can overwrite it."""
    from logo_maker import render
    from logo_maker.proc import ToolError

    if budget:
        budget.check()
    cached = current(logo, cid, quality, budget=budget)
    if cached:
        return cached
    folder = logo.concept(cid)
    from logo_maker.scene import load_scene

    if load_scene(folder / "scene.toml")["render"]["renderer"] != "cycles":
        raise ToolError(
            "creative refinement requires Cycles Metal GPU-only rendering; alternate renderer is unverified"
        )
    hashes = source_hashes(logo, folder)
    result = render.render(folder, quality, budget=budget)
    if not result.execution or not result.execution.is_file():
        raise ToolError("creative rendering requires verified Metal GPU execution evidence")
    execution = read(result.execution)
    if (
        execution.get("status") != "verified"
        or execution.get("policy") != "metal-gpu-only"
        or execution.get("denoiser_effective", {}).get("device_type") != "Metal"
    ):
        raise ToolError("creative rendering requires verified Metal tracing and denoising")
    if hashes != source_hashes(logo, folder):
        raise ToolError("sources changed during render; refusing stale creative evidence")
    prior = history(logo, cid)
    revision = f"{len(prior) + 1:04d}-{key(hashes)[:12]}-{quality}"
    dest = logo.qa / "revisions" / concept_slug(cid) / revision
    dest.mkdir(parents=True)
    for name, path in inputs(logo, folder).items():
        target = dest / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    shutil.copy2(result.png, dest / "render.png")
    if (folder / "motif-sizes.png").exists():
        shutil.copy2(folder / "motif-sizes.png", dest / "motif-sizes.png")
    shutil.copy2(result.execution, dest / "execution.json")
    native_log = result.execution.with_suffix(".log")
    if native_log.exists():
        shutil.copy2(native_log, dest / "execution.log")
    if (folder / ".build").exists():
        shutil.copytree(
            folder / ".build",
            dest / "build",
            ignore=shutil.ignore_patterns("*.png", "*.exr", "attempt-*", "*.prior-*"),
        )
    if (result.execution.parent / "scene.json").exists():
        shutil.copy2(result.execution.parent / "scene.json", dest / "build" / "selected-scene.json")
    sampling = read(result.sampling) if result.sampling and result.sampling.exists() else {}
    if sampling:
        write(dest / "sampling.json", sampling)
    record = {
        "revision": revision,
        "concept": cid,
        "quality": quality,
        "previous": prior[-1]["revision"] if prior else None,
        "source_sha256": hashes,
        "concept_sha256": digest(folder / "concept.json"),
        "image_sha256": digest(result.png),
        "image": str((dest / "render.png").relative_to(logo.root)),
        "evidence": str(dest.relative_to(logo.root)),
        "construction": construction(folder),
        "execution": execution,
        "host_total_seconds": result.seconds,
        "sampling": sampling,
        "reuse_scope": "retained_preview_only"
        if quality == "preview" and "custom_scene_sha256" in sampling.get("context", {})
        else "supported_runtime_scope",
        "custom_dependency_inventory": "unknown"
        if "custom_scene_sha256" in sampling.get("context", {})
        else "catalog",
        "sampling_calibration": sampling.get("profile", {"state": "profile_unqualified"}),
    }
    write(dest / "revision.json", record)
    state = read(folder / "render-state.json") if (folder / "render-state.json").exists() else {}
    state[quality] = record
    write(folder / "render-state.json", state)
    # Keep files/history, revoke eligibility. Direct finalize/export must recheck it.
    from logo_maker.runlog import runlog

    log = runlog(logo.run_json)
    for stage in (
        ("preview", "finalize", "export") if quality == "preview" else ("finalize", "export")
    ):
        log.stage(stage, "stale", revision=revision)
    return record


def require_current(
    logo: LogoDir,
    cid: str,
    record: dict,
    *,
    budget: Budget | None = None,
    inspection_sha256: str | None = None,
) -> None:
    from logo_maker.pipeline import AuthoringNeeded

    active = current(logo, cid, record["quality"], budget=budget)
    inspection = logo.concept(cid) / (
        "inspection-final.json" if record["quality"] == "final" else "inspection.json"
    )
    inspection_changed = inspection_sha256 is not None and (
        not inspection.exists() or digest(inspection) != inspection_sha256
    )
    if not active or active["revision"] != record["revision"] or inspection_changed:
        raise AuthoringNeeded(
            "inputs or device context changed while judging; refresh and inspect the render",
            [logo.concept(cid) / "scene.toml", logo.concept(cid) / "construction.json"],
            details={
                "dimension": "stale_judgment",
                "artifact": record["image"],
                "revision": record["revision"],
            },
        )


def inspected(logo: LogoDir, cid: str, record: dict) -> dict:
    from logo_maker.pipeline import AuthoringNeeded

    path = logo.concept(cid) / (
        "inspection-final.json" if record["quality"] == "final" else "inspection.json"
    )
    data = read(path) if path.exists() else {}
    detail = {
        "dimension": "inspection",
        "revision": record["revision"],
        "artifact": record["image"],
        "next_comparison": "open retained image and prior revision; record observations, critique and user direction",
    }
    if (
        data.get("revision") != record["revision"]
        or not isinstance(data.get("observations"), str)
        or not data["observations"].strip()
        or not isinstance(data.get("critiques"), list)
    ):
        raise AuthoringNeeded(
            "inspect the retained render; write current inspection.json", [path], details=detail
        )
    # Preserve unresolved critique too: it is the evidence the next revision must address.
    evidence = logo.root / record["evidence"]
    write(evidence / "inspection.json", data)
    write(evidence / "inspections" / f"{key(data)}.json", data)
    for critique in data["critiques"]:
        if (
            not isinstance(critique, dict)
            or critique.get("kind") not in {"craftsmanship", "brief_fit", "preference", "technical"}
            or any(
                not isinstance(critique.get(k), str) or not critique[k].strip()
                for k in ("dimension", "artifact", "evidence", "action", "comparison")
            )
            or critique.get("resolved") is not True
        ):
            raise AuthoringNeeded(
                "resolve critique through authoring, comparison or user direction",
                [path, logo.concept(cid) / "construction.json"],
                details={**detail, "critique": critique},
            )
    write(logo.root / record["evidence"] / "inspection.json", data)
    return data


def report(logo: LogoDir, ids: list[str]) -> dict:
    revisions = {cid: history(logo, cid) for cid in ids}
    pool = logo.ideation / "pool.jsonl"
    comparisons = logo.qa / "comparisons.json"
    return {
        "text_combinations": sum(bool(line.strip()) for line in pool.read_text().splitlines())
        if pool.exists()
        else 0,
        "authored_motifs": sum(
            (logo.concept(cid) / "motif.svg").exists() or (logo.concept(cid) / "motif.py").exists()
            for cid in ids
        ),
        "rendered_variants": sum(len(v) for v in revisions.values()),
        "completed_refinement_rounds": sum(
            comparison_complete(logo.root / r["evidence"] / "comparison.json")
            for rows in revisions.values()
            for r in rows
        ),
        "comparisons": read(comparisons) if comparisons.exists() else [],
        "revisions": revisions,
    }


def judge_revision(logo: LogoDir, cid: str, record: dict, inspection: dict, client) -> dict:
    from logo_maker.brief import load
    from logo_maker.jev.client import Image
    from logo_maker.jev.questions import creative_questions, creative_ready, noul_status
    from logo_maker.pipeline import AuthoringNeeded

    check_image(logo, record)
    evidence = logo.root / record["evidence"]
    flat_image = evidence / "motif-sizes.png"
    if not flat_image.exists():
        from logo_maker.motif import size_sheet

        size_sheet(evidence / "sources" / "concept" / "motif.svg", flat_image)
    path = evidence / "judgment.json"
    binding = key(
        {
            "source": record["source_sha256"],
            "image": record["image_sha256"],
            "flat_image": digest(flat_image),
            "inspection": inspection,
            "judge": [
                getattr(client, "model", type(client).__name__),
                getattr(client, "url", None),
            ],
            "questions": creative_questions(),
        }
    )
    cached = read(path) if path.exists() else {}
    if cached.get("binding") == binding:
        answers = cached["answers"]
    else:
        state = {
            "brief": load(logo.brief).as_state(),
            "construction": record["construction"],
            "render": Image(logo.root / record["image"]),
            "motif": Image(flat_image),
            "inspection": inspection,
        }
        answers = client.ask(
            state, creative_questions(), label=f"creative-{concept_slug(cid)}-{record['revision']}"
        )
        write(path, {"binding": binding, "answers": answers})
    prior = [
        r
        for r in history(logo, cid)
        if r["quality"] == record["quality"] and r["revision"] < record["revision"]
    ]
    comparison = compare(logo, prior[-1], record, client) if prior else None
    if not creative_ready(answers):
        dimensions = {
            name: {"p": float(value["noul"]), "status": noul_status(float(value["noul"]))}
            for name, value in answers.items()
            if noul_status(float(value["noul"])) != "yes"
        }
        sources = {
            "construction.json",
            "inspection-final.json" if record["quality"] == "final" else "inspection.json",
        }
        if dimensions.keys() & {"craftsmanship", "material_intent"}:
            sources.update({"scene.toml", "scene.py"})
        if dimensions.keys() & {"brief_fit", "description_match"}:
            sources.update({"concept.json", "motif.py", "motif.svg", "scene.toml"})
        raise AuthoringNeeded(
            "creative readiness failed or remains uncertain; inspect the named dimensions before choosing a revision",
            [logo.concept(cid) / name for name in sorted(sources)],
            details={
                "dimension": "creative_readiness",
                "artifact": record["image"],
                "revision": record["revision"],
                "verdicts": answers,
                "required_dimensions": dimensions,
                "comparison": comparison,
                "next_comparison": "inspect the named dimensions and retained comparison; uncertain evidence may need a diagnostic probe or owner direction, while a confirmed defect needs an intent-led revision",
            },
        )
    if (
        comparison
        and noul_status(float(comparison["answers"]["critique_resolved"]["noul"])) != "yes"
    ):
        raise AuthoringNeeded(
            "revision comparison leaves critique unresolved; inspect or seek owner direction",
            [
                logo.concept(cid) / name
                for name in (
                    "construction.json",
                    "scene.toml",
                    "inspection-final.json" if record["quality"] == "final" else "inspection.json",
                )
            ],
            details={
                "dimension": "critique_resolution",
                "artifact": record["image"],
                "revision": record["revision"],
                "comparison": comparison,
            },
        )
    return answers


def compare(logo: LogoDir, before: dict, after: dict, client) -> dict:
    from logo_maker.brief import load
    from logo_maker.jev.client import Image
    from logo_maker.jev.questions import revision_questions

    check_image(logo, before)
    check_image(logo, after)
    before_dir, after_dir = (logo.root / r["evidence"] for r in (before, after))
    prior = {
        name: read(before_dir / name)
        for name in ("inspection.json", "judgment.json")
        if (before_dir / name).exists()
    }
    current_review = {
        name.removesuffix(".json"): read(after_dir / name)
        for name in ("inspection.json", "judgment.json")
        if (after_dir / name).exists()
    }
    binding = key(
        {
            "before": before,
            "after": after,
            "prior": prior,
            "current_review": current_review,
            "questions": revision_questions(),
            "judge": [
                getattr(client, "model", type(client).__name__),
                getattr(client, "url", None),
            ],
        }
    )
    path = logo.qa / "comparisons.json"
    rows = read(path) if path.exists() else []
    cached = next((r for r in rows if r["binding"] == binding), None)
    if cached:
        return cached
    state = {
        "brief": load(logo.brief).as_state(),
        "before": Image(logo.root / before["image"]),
        "after": Image(logo.root / after["image"]),
        "before_intent": before["construction"],
        "after_intent": after["construction"],
        "prior_critique": prior,
        "current_review": current_review,
    }
    answers = client.ask(state, revision_questions(), label=f"compare-{after['revision']}")
    if before["image_sha256"] == after["image_sha256"]:
        answers["visually_distinct"] = {"noul": 0.0, "reason": "identical image bytes"}
    result = {
        "binding": binding,
        "before": before["image"],
        "after": after["image"],
        "answers": answers,
    }
    rows.append(result)
    write(path, rows)
    write(after_dir / "comparisons" / f"{binding}.json", result)
    same_quality = [
        r
        for r in history(logo, after["concept"])
        if r["quality"] == after["quality"] and r["revision"] < after["revision"]
    ]
    if (
        before["concept"] == after["concept"]
        and same_quality
        and same_quality[-1]["revision"] == before["revision"]
    ):
        write(after_dir / "comparison.json", result)
    return result


def alternatives(logo: LogoDir, records: list[dict], client) -> None:
    from logo_maker.jev.questions import noul_status
    from logo_maker.pipeline import AuthoringNeeded

    distinct = False
    # Each changed concept must resolve its prior critique, regardless of other alternatives.
    for record in records:
        prior = [
            r
            for r in history(logo, record["concept"])
            if r["quality"] == record["quality"] and r["revision"] != record["revision"]
        ]
        if not prior:
            continue
        result = compare(logo, prior[-1], record, client)
        if noul_status(float(result["answers"]["critique_resolved"]["noul"])) != "yes":
            raise AuthoringNeeded(
                "revision comparison leaves critique unresolved",
                [logo.concept(record["concept"]) / "inspection.json"],
                details=result,
            )
        distinct |= noul_status(float(result["answers"]["visually_distinct"]["noul"])) == "yes"
        # A later small repair must not erase earlier genuine visual exploration.
        if not distinct:
            for earlier in reversed(prior[:-1]):
                result = compare(logo, earlier, record, client)
                if noul_status(float(result["answers"]["visually_distinct"]["noul"])) == "yes":
                    distinct = True
                    break
    if not distinct:
        for i, record in enumerate(records):
            for other in records[i + 1 :]:
                if record["image_sha256"] == other["image_sha256"]:
                    continue
                result = compare(logo, record, other, client)
                if noul_status(float(result["answers"]["visually_distinct"]["noul"])) == "yes":
                    distinct = True
                    break
            if distinct:
                break
    if not distinct:
        raise AuthoringNeeded(
            "show genuinely distinct rendered alternatives in symbol or construction",
            [logo.concept(r["concept"]) / "construction.json" for r in records],
            details={
                "dimension": "visual_alternatives",
                "artifacts": [r["image"] for r in records],
                "next_comparison": "author a distinct visual decision; material/text combinations alone do not qualify",
            },
        )


def campaign_key(logo: LogoDir, ids: list[str]) -> str:
    return key(
        {
            cid: {
                "sources": source_hashes(logo, logo.concept(cid)),
                "preview": digest(logo.concept(cid) / "preview.png")
                if (logo.concept(cid) / "preview.png").exists()
                else None,
                "inspection": digest(logo.concept(cid) / "inspection.json")
                if (logo.concept(cid) / "inspection.json").exists()
                else None,
            }
            for cid in ids
        }
    )


def require_binding(logo: LogoDir, data: dict, stage: str) -> None:
    from logo_maker.pipeline import AuthoringNeeded, shortlist

    if not data.get("binding") or data["binding"] != campaign_key(logo, shortlist(logo)):
        raise AuthoringNeeded(
            f"stale {stage} eligibility; rerun preview/refinement",
            [logo.ideation / "finalists.json"],
            details={"dimension": "stale_evidence"},
        )


def comparison_complete(path: Path) -> bool:
    from logo_maker.jev.questions import noul_status

    return (
        path.exists()
        and noul_status(float(read(path)["answers"]["critique_resolved"]["noul"])) == "yes"
    )


def diagnosis(logo: LogoDir, cid: str, record: dict, unknown: dict) -> dict:
    """Consume image-bound diagnosis without owning #5's sampling selection policy."""
    path = logo.concept(cid) / "diagnosis.json"
    if not path.exists():
        return unknown
    data = read(path)
    causes = {
        "sampling_noise",
        "cap_limitation",
        "design",
        "geometry",
        "material",
        "typography",
        "denoising",
        "filtering",
        "resolution",
        "alpha",
        "unknown",
    }
    evidence = data.get("evidence", [])
    if (
        data.get("revision") != record["revision"]
        or data.get("cause") not in causes
        or not isinstance(evidence, list)
        or not evidence
    ):
        return {**unknown, "invalid_diagnosis": "missing/stale revision, cause or evidence"}
    for item in evidence:
        if not isinstance(item, dict):
            return {**unknown, "invalid_diagnosis": "malformed evidence"}
        artifact = logo.root / item.get("artifact", "")
        if (
            not artifact.is_file()
            or item.get("sha256") != digest(artifact)
            or not item.get("observation")
        ):
            return {**unknown, "invalid_diagnosis": "changed/missing evidence"}
    result = {
        **data,
        "sampling_action": "none",
        "route": "sampling-policy-#5"
        if data["cause"] in {"sampling_noise", "cap_limitation"}
        else "authoring-or-diagnostic-probe",
    }
    write(logo.root / record["evidence"] / "diagnosis.json", result)
    return result


def check_image(logo: LogoDir, record: dict) -> None:
    from logo_maker.proc import ToolError

    image = logo.root / record["image"]
    if not image.is_file() or digest(image) != record["image_sha256"]:
        raise ToolError(
            "retained revision image changed or is missing; restore evidence before judging"
        )
