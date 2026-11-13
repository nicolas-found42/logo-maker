"""Content-bound creative revisions. Jev judges; the calling agent authors and inspects."""

from __future__ import annotations

import functools
import hashlib
import json
import shutil
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from logo_maker.paths import REPO_ROOT, LogoDir, concept_slug
from logo_maker.sampling import Budget

_ACTIVE_BUDGET: ContextVar[Budget | None] = ContextVar("refinement_budget", default=None)


@contextmanager
def owned_scope(budget: Budget | None):
    token = _ACTIVE_BUDGET.set(budget)
    try:
        yield
    finally:
        _ACTIVE_BUDGET.reset(token)


def bounded_entry(fn):
    @functools.wraps(fn)
    def call(*args, **kwargs):
        budget = kwargs.get("budget") or _ACTIVE_BUDGET.get() or Budget(attempt_limit=64)
        kwargs["budget"] = budget
        with owned_scope(budget):
            return fn(*args, **kwargs)

    return call


def _pack(value):
    if isinstance(value, LogoDir):
        return {"__logo__": str(value.root)}
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if isinstance(value, Budget):
        return None  # the enclosing worker owns the remaining deadline
    if isinstance(value, set):
        return {"__set__": sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_pack(v) for v in value]
    if isinstance(value, dict):
        return {k: _pack(v) for k, v in value.items()}
    return value


def _unpack(value):
    if isinstance(value, list):
        return [_unpack(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"__logo__"}:
            return LogoDir(Path(value["__logo__"]))
        if set(value) == {"__path__"}:
            return Path(value["__path__"])
        if set(value) == {"__set__"}:
            return set(value["__set__"])
        return {k: _unpack(v) for k, v in value.items()}
    return value


def owned_io(fn):
    @functools.wraps(fn)
    def call(*args, **kwargs):
        budget = kwargs.get("budget") or _ACTIVE_BUDGET.get()
        if budget is None:
            return fn(*args, **kwargs)
        from logo_maker import host
        from logo_maker.pipeline import AuthoringNeeded
        from logo_maker.proc import ToolError

        result = host.run(
            {
                "operation": "refinement",
                "action": fn.__name__,
                "args": _pack(args),
                "kwargs": _pack(kwargs),
            },
            budget,
            [],
        )
        if "error" in result:
            if result["error_type"] == "AuthoringNeeded":
                raise AuthoringNeeded(
                    result["error"], [Path(p) for p in result["files"]], details=result["details"]
                )
            raise ToolError(result["error"])
        return _unpack(result["result"])

    call._owned_io = True  # ty: ignore[missing-attribute]
    return call


def host_operation(payload):
    from logo_maker.pipeline import AuthoringNeeded
    from logo_maker.proc import ToolError

    fn = globals().get(payload["action"])
    if not callable(fn) or not getattr(fn, "_owned_io", False):
        raise ValueError("unknown refinement operation")
    try:
        return {"result": _pack(fn(*_unpack(payload["args"]), **_unpack(payload["kwargs"])))}
    except AuthoringNeeded as exc:
        return {
            "error": str(exc),
            "error_type": "AuthoringNeeded",
            "files": [str(p) for p in exc.files],
            "details": exc.details,
        }
    except (OSError, ValueError, ToolError) as exc:
        return {"error": str(exc), "error_type": type(exc).__name__}


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


@owned_io
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@owned_io
def read(path: Path) -> Any:
    return json.loads(path.read_text())


@owned_io
def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(".writing-" + uuid.uuid4().hex + "-" + path.name)
    pending.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


@owned_io
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


@owned_io
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


@owned_io
def inputs(logo: LogoDir, folder: Path) -> dict[str, Path]:
    """Explicit custom dependencies plus local sources and the owning tool's implementation."""
    from logo_maker import pipeline

    frozen = pipeline._require_brief(logo)
    pipeline._require_plan(logo, read(folder / "concept.json")["id"])
    construction(folder)
    files = {"brief.toml": logo.brief, **concept_sources(folder)}
    for name in ("brief-evidence.toml", "ideation/requirements.json"):
        files[name] = logo.root / name
    for i, source in enumerate([*frozen["inputs"]["sources"], *frozen["inputs"]["baselines"]]):
        path = Path(source)
        files[f"requirements_source/{i}/{path.name}"] = path
    from logo_maker.brief import load

    for i, ref in enumerate(load(logo.brief).references):
        files[f"reference/{i}/{ref.path.name}"] = ref.path
    for base in (REPO_ROOT / "logo_maker",):
        for path in sorted(base.rglob("*")):
            if path.suffix in {".py", ".toml"} and "__pycache__" not in path.parts:
                files[f"tool/{path.relative_to(base)}"] = path
    return files


@owned_io
def source_hashes(logo: LogoDir, folder: Path) -> dict[str, str]:
    return {name: digest(path) for name, path in inputs(logo, folder).items()}


@owned_io
def history(logo: LogoDir, cid: str) -> list[dict]:
    root = logo.qa / "revisions" / concept_slug(cid)
    return [read(p) for p in sorted(root.glob("[0-9]*/revision.json"))]


@owned_io
def _current_record(logo, cid, quality):
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
    return record


def current(
    logo: LogoDir, cid: str, quality: str = "preview", *, budget: Budget | None = None
) -> dict | None:
    with owned_scope(budget or _ACTIVE_BUDGET.get()):
        record = _current_record(logo, cid, quality)
        if record is None:
            return None
        from logo_maker.render import artifact_current, inspection_artifact_current

        check = inspection_artifact_current if quality == "preview" else artifact_current
        folder = logo.root / "concepts" / concept_slug(cid)
        return record if check(folder, quality, budget=budget or _ACTIVE_BUDGET.get()) else None


@bounded_entry
def capture(logo: LogoDir, cid: str, quality: str, *, budget: Budget | None = None) -> dict:
    """Render a new revision once; archive provenance before another render can overwrite it."""
    from logo_maker import render
    from logo_maker.proc import ToolError

    if budget:
        budget.check()
    cached = current(logo, cid, quality, budget=budget)
    if cached:
        return cached
    folder = logo.root / "concepts" / concept_slug(cid)
    hashes = _capture_inputs(logo, folder)
    result = render.render(folder, quality, budget=budget)
    if result.execution is None:
        raise ToolError("creative rendering requires verified Metal GPU execution evidence")
    staged = _archive(
        logo, cid, quality, hashes, result.png, result.execution, result.sampling, result.seconds
    )
    from logo_maker.publication import publish

    publish(
        staged["entries"],
        logo.root / "qa" / (".revision-publication-" + str(time.monotonic_ns()) + ".json"),
        budget or _ACTIVE_BUDGET.get() or Budget(),
        [],
    )
    record = staged["record"]
    revision = record["revision"]
    # Keep files/history, revoke eligibility. Direct finalize/export must recheck it.
    from logo_maker.runlog import runlog

    log = runlog(logo.run_json, budget=budget)
    for stage in (
        ("preview", "finalize", "export") if quality == "preview" else ("finalize", "export")
    ):
        log.stage(stage, "stale", revision=revision, budget=budget)
    return record


@owned_io
def _archive(logo, cid, quality, hashes, png, execution_path, sampling_path, seconds):
    folder = logo.concept(cid)
    from logo_maker.proc import ToolError

    execution = read(execution_path)
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
    archive_target = dest
    dest = dest.with_name(".archiving-" + uuid.uuid4().hex)
    dest.mkdir(parents=True)
    for name, path in inputs(logo, folder).items():
        target = dest / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    shutil.copy2(png, dest / "render.png")
    if (folder / "motif-sizes.png").exists():
        shutil.copy2(folder / "motif-sizes.png", dest / "motif-sizes.png")
    shutil.copy2(execution_path, dest / "execution.json")
    native_log = execution_path.with_suffix(".log")
    if native_log.exists():
        shutil.copy2(native_log, dest / "execution.log")
    if (folder / ".build").exists():
        shutil.copytree(
            folder / ".build",
            dest / "build",
            ignore=shutil.ignore_patterns("*.png", "*.exr", "attempt-*", "*.prior-*"),
        )
    if (execution_path.parent / "scene.json").exists():
        shutil.copy2(execution_path.parent / "scene.json", dest / "build" / "selected-scene.json")
    sampling = read(sampling_path) if sampling_path and sampling_path.exists() else {}
    if sampling:
        write(dest / "sampling.json", sampling)
    if (
        hashes != source_hashes(logo, folder)
        or any(digest(dest / "sources" / name) != value for name, value in hashes.items())
        or digest(dest / "render.png") != digest(png)
        or sampling.get("delivered_sha256") != digest(dest / "render.png")
    ):
        raise ToolError("sources or image changed during archival; prior revision retained")
    record = {
        "revision": revision,
        "concept": cid,
        "quality": quality,
        "previous": prior[-1]["revision"] if prior else None,
        "source_sha256": hashes,
        "concept_sha256": digest(folder / "concept.json"),
        "image_sha256": digest(png),
        "image": str((archive_target / "render.png").relative_to(logo.root)),
        "evidence": str(archive_target.relative_to(logo.root)),
        "construction": construction(folder),
        "execution": execution,
        "host_total_seconds": seconds,
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
    return {
        "record": record,
        "entries": [
            {"target": str(archive_target), "source": str(dest), "move": True},
            {"target": str(folder / "render-state.json"), "text": json.dumps(state)},
        ],
    }


def require_current(
    logo: LogoDir,
    cid: str,
    record: dict,
    *,
    budget: Budget | None = None,
    inspection_sha256: str | None = None,
) -> None:
    from logo_maker.pipeline import AuthoringNeeded

    check_image(logo, record)
    active = current(logo, cid, record["quality"], budget=budget)
    inspection = (logo.root / "concepts" / concept_slug(cid)) / (
        "inspection-final.json" if record["quality"] == "final" else "inspection.json"
    )
    inspection_changed = inspection_sha256 is not None and (
        inspection_binding(inspection) != inspection_sha256
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
    return inspection_snapshot(logo, cid, record)["data"]


@owned_io
def inspection_snapshot(logo: LogoDir, cid: str, record: dict) -> dict:
    path = logo.concept(cid) / (
        "inspection-final.json" if record["quality"] == "final" else "inspection.json"
    )
    raw = path.read_bytes() if path.exists() else b"{}"
    data = _inspected_data(logo, cid, record, json.loads(raw))
    return {"data": data, "sha256": hashlib.sha256(raw).hexdigest()}


def _inspected_data(logo: LogoDir, cid: str, record: dict, data: dict) -> dict:
    from logo_maker.pipeline import AuthoringNeeded

    path = logo.concept(cid) / (
        "inspection-final.json" if record["quality"] == "final" else "inspection.json"
    )
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


@owned_io
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
    return _judge_revision(logo, cid, record, inspection, client)[0]


def judge_revision_proof(logo, cid, record, inspection, inspection_sha256, client):
    answers, binding = _judge_revision(logo, cid, record, inspection, client)
    # This hashes the exact judgment admitted above, not a later filesystem read.
    judgment = json.dumps({"binding": binding, "answers": answers}, indent=2, sort_keys=True) + "\n"
    return {key: record[key] for key in ("revision", "image_sha256", "evidence")} | {
        "inspection_sha256": inspection_sha256,
        "judgment_sha256": hashlib.sha256(judgment.encode()).hexdigest(),
    }


def _judge_revision(
    logo: LogoDir, cid: str, record: dict, inspection: dict, client
) -> tuple[dict, str]:
    from logo_maker.jev.client import Image
    from logo_maker.jev.questions import creative_questions, creative_ready, noul_status
    from logo_maker.pipeline import AuthoringNeeded

    prepared = _judge_inputs(
        logo,
        record,
        inspection,
        [getattr(client, "model", type(client).__name__), getattr(client, "url", None)],
    )
    binding, cached = prepared["binding"], prepared["cached"]
    if cached.get("binding") == binding:
        answers = cached["answers"]
    else:
        answers = client.ask(
            {
                "brief": prepared["brief"],
                "construction": record["construction"],
                "render": Image(logo.root / record["image"]),
                "motif": Image(prepared["flat_image"]),
                "inspection": inspection,
            },
            creative_questions(),
            label=f"creative-{concept_slug(cid)}-{record['revision']}",
        )
        write(prepared["path"], {"binding": binding, "answers": answers})
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
    return answers, binding


def compare(logo: LogoDir, before: dict, after: dict, client) -> dict:
    from logo_maker.jev.client import Image
    from logo_maker.jev.questions import revision_questions

    prepared = _comparison_inputs(
        logo,
        before,
        after,
        [getattr(client, "model", type(client).__name__), getattr(client, "url", None)],
    )
    if prepared["cached"]:
        return prepared["cached"]
    binding, prior, current_review = (
        prepared["binding"],
        prepared["prior"],
        prepared["current_review"],
    )
    state = {
        "brief": prepared["brief"],
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
    _retain_comparison(logo, before, after, result)
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


@owned_io
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


@owned_io
def require_binding(logo: LogoDir, data: dict, stage: str) -> None:
    from logo_maker.pipeline import AuthoringNeeded, shortlist

    if not data.get("binding"):
        raise AuthoringNeeded(
            f"stale {stage} eligibility; rerun preview/refinement",
            [logo.root / "ideation/finalists.json"],
        )
    try:
        current_binding = campaign_key(logo, shortlist(logo))
    except ValueError:
        current_binding = None
    if not data.get("binding") or data["binding"] != current_binding:
        raise AuthoringNeeded(
            f"stale {stage} eligibility; rerun preview/refinement",
            [logo.ideation / "finalists.json"],
            details={"dimension": "stale_evidence"},
        )


@owned_io
def comparison_complete(path: Path) -> bool:
    from logo_maker.jev.questions import noul_status

    return (
        path.exists()
        and noul_status(float(read(path)["answers"]["critique_resolved"]["noul"])) == "yes"
    )


@owned_io
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


@owned_io
def check_image(logo: LogoDir, record: dict) -> None:
    from logo_maker.proc import ToolError

    image = logo.root / record["image"]
    if not image.is_file() or digest(image) != record["image_sha256"]:
        raise ToolError(
            "retained revision image changed or is missing; restore evidence before judging"
        )


@owned_io
def _judge_inputs(logo, record, inspection, judge):
    from logo_maker.brief import load
    from logo_maker.jev.questions import creative_questions

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
                *judge,
            ],
            "questions": creative_questions(),
        }
    )
    cached = read(path) if path.exists() else {}
    return {
        "binding": binding,
        "cached": cached,
        "flat_image": flat_image,
        "path": path,
        "brief": load(logo.brief).as_state(),
    }


@owned_io
def _comparison_inputs(logo, before, after, judge):
    from logo_maker.brief import load
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
                *judge,
            ],
        }
    )
    path = logo.qa / "comparisons.json"
    rows = read(path) if path.exists() else []
    cached = next((r for r in rows if r["binding"] == binding), None)
    return {
        "binding": binding,
        "cached": cached,
        "prior": prior,
        "current_review": current_review,
        "brief": load(logo.brief).as_state(),
    }


@owned_io
def _retain_comparison(logo, before, after, result):
    path = logo.qa / "comparisons.json"
    rows = read(path) if path.exists() else []
    after_dir = logo.root / after["evidence"]
    binding = result["binding"]
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


@owned_io
def prepare(logo):
    from logo_maker import pipeline

    frozen = pipeline._require_brief(logo)
    ids = pipeline.shortlist(logo)
    for cid in ids:
        from logo_maker.briefing import PLAN_TEMPLATE

        plan = logo.concept(cid) / "plan.toml"
        if not plan.exists():
            plan.write_text(PLAN_TEMPLATE.format(revision=frozen["requirements_revision"]))
        pipeline._require_plan(logo, cid)
        construction(logo.concept(cid))
    pipeline.motifs(logo)
    return ids


def selection_bindings(logo, campaign_binding, results, quality, *, check_machine=True):
    from logo_maker.pipeline import AuthoringNeeded

    if _campaign_for_shortlist(logo) != campaign_binding:
        raise AuthoringNeeded("campaign changed during final judging", [logo.brief])
    for cid, result in results.items():
        if check_machine:
            active = current(logo, cid, quality)
        else:
            # The export process is already owned. Do not create nested sessions
            # with fresh budgets while checking the pinned on-disk proof.
            from logo_maker.render import _artifact_current_local

            active = _current_record(logo, cid, quality)
            if active and not _artifact_current_local(
                logo.root / "concepts" / concept_slug(cid),
                quality,
                inspection_only=quality == "preview",
            ):
                active = None
        if active is not None:
            check_image(logo, active)
        inspection = (logo.root / "concepts" / concept_slug(cid)) / (
            "inspection-final.json" if quality == "final" else "inspection.json"
        )
        judgment = logo.root / result["evidence"] / "judgment.json"
        if (
            not active
            or active["revision"] != result["revision"]
            or active["image_sha256"] != result["image_sha256"]
            or inspection_binding(inspection) != result["inspection_sha256"]
            or inspection_binding(judgment) != result["judgment_sha256"]
        ):
            raise AuthoringNeeded(f"{quality} eligibility changed while judging", [inspection])


def final_bindings(logo, campaign_binding, results, *, check_machine=True):
    selection_bindings(logo, campaign_binding, results, "final", check_machine=check_machine)


def verify_selection(
    logo: LogoDir, binding: str, proofs: dict, quality: str, eligibility: dict
) -> None:
    """Verify staged selection proofs locally inside the publication worker."""
    from logo_maker.brief import load
    from logo_maker.eligibility import require_current

    selection_bindings(logo, binding, proofs, quality, check_machine=False)
    brief = load(logo.brief)
    for cid, proof in eligibility.items():
        require_current(logo, brief, cid, proof, stage=quality)


def verify_winner(logo, data, *, check_machine=True):
    from logo_maker.pipeline import AuthoringNeeded

    if not isinstance(data.get("creative"), dict) or not data["creative"].get("evidence"):
        raise AuthoringNeeded(
            "stale creative winner proof; rerun finalize", [logo.root / "ideation/winner.json"]
        )
    require_binding(logo, data, "finalize")
    final_bindings(
        logo, data["binding"], {data["winner"]: data["creative"]}, check_machine=check_machine
    )


@owned_io
def _capture_inputs(logo, folder):
    from logo_maker.proc import ToolError
    from logo_maker.scene import load_scene

    if load_scene(folder / "scene.toml")["render"]["renderer"] != "cycles":
        raise ToolError(
            "creative refinement requires Cycles Metal GPU-only rendering; alternate renderer is unverified"
        )
    return source_hashes(logo, folder)


@owned_io
def inspection_binding(path):
    return digest(path) if path.exists() else ""


@owned_io
def _campaign_for_shortlist(logo):
    from logo_maker.pipeline import shortlist

    return campaign_key(logo, shortlist(logo))
