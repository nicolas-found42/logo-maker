"""Stage orchestration: intake -> ideate -> preview -> finalize -> export, plus improve.

Each stage is resumable: it records its status in run.json and reuses outputs that already exist. When a
stage needs the agent to author something, it raises `AuthoringNeeded` naming the exact files to write.
"""

from __future__ import annotations

import json
import shutil
import time
import tomllib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit

from logo_maker import brief as brief_mod
from logo_maker import host
from logo_maker.jev.questions import qa_blocks
from logo_maker.paths import LogoDir, concept_slug
from logo_maker.runlog import runlog
from logo_maker.sampling import Budget

METAPHORS_TEMPLATE = """# Metaphors for this brand: 8-40 distinct ideas the mark could show, each in one or two sentences that
# say what it depicts and why it fits the brief. Ids are short slugs. Derive every idea from the brief.
#
# [[metaphor]]
# id = "slug"
# text = "What the mark shows, and what it says about the brand."
"""

PROPOSALS_TEMPLATE = """# Proposals for whatever brief.toml leaves out. logo-maker drops palettes that fail WCAG AA, then jev picks.
# Write 6 of each that brief.toml does not already define.
#
# [[palette]]          # roles: primary, secondary, accent, highlight, background, ink
# primary = "#RRGGBB"
# secondary = "#RRGGBB"
# accent = "#RRGGBB"
# background = "#RRGGBB"
# ink = "#RRGGBB"
#
# [[fonts]]            # families from github.com/google/fonts; "Family:axis=value,..."
# display = "Family:wght=700"
# text = "Family:wght=400"
"""

MAX_QA_ROUNDS = 5


class AuthoringNeeded(RuntimeError):
    """The agent must write files before the stage can continue. `files` lists them."""

    def __init__(self, message: str, files: list[Path]):
        super().__init__(message + "\n" + "\n".join(f"  - {f}" for f in files))
        self.files = files


@dataclass(frozen=True)
class Brand:
    palette: dict[str, str]
    fonts: dict[str, str]


def _client(logo: LogoDir, *, budget: Budget | None = None):
    from logo_maker.jev.client import JevClient

    return JevClient(logo, budget=budget)


def _bounded_inputs(logo: LogoDir, budget: Budget, *, brand_required: bool = False, **flags):
    data = host.run(
        {"operation": "pipeline_inputs", "root": str(logo.root), "brand": brand_required, **flags},
        budget,
        [],
    )
    fields = data["brief"]
    fields["references"] = tuple(
        brief_mod.Reference(Path(r["path"]), r["use"], r["note"]) for r in fields["references"]
    )
    brief = brief_mod.Brief(**fields)
    brand_ = Brand(**data["brand"]) if brand_required else None
    return brief, brand_, data


def _budgeted_client(client, budget: Budget):
    from logo_maker.proc import ToolError

    binder = getattr(client, "with_budget", None)
    if not callable(binder):
        raise ToolError(
            "budget_conflict: finalization requires a client with explicit budget binding"
        )
    return binder(budget)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------- new / intake


def new(logo: LogoDir, name: str) -> LogoDir:
    brief_mod.write_template(logo.brief, name)
    logo.inputs  # noqa: B018 - property creates the folder
    if not logo.metaphors.exists():
        logo.metaphors.write_text(METAPHORS_TEMPLATE)
    proposals = logo.ideation / "proposals.toml"
    if not proposals.exists():
        proposals.write_text(PROPOSALS_TEMPLATE)
    log = runlog(logo.run_json)
    log.record_versions()
    log.stage("new", "done")
    return logo


def brand(logo: LogoDir) -> Brand:
    """The palette and fonts every later stage uses: the brief's own, else intake's picks."""
    brief = brief_mod.load(logo.brief)
    palette = dict(brief.palette)
    fonts = dict(brief.fonts)
    picked_palette = logo.ideation / "palette.json"
    picked_fonts = logo.ideation / "fonts.json"
    if not palette and picked_palette.exists():
        palette = _read_json(picked_palette)["palette"]
    if not fonts and picked_fonts.exists():
        fonts = _read_json(picked_fonts)["fonts"]
    if not palette or not fonts:
        raise RuntimeError(
            f"{logo.slug}: palette or fonts missing; run `logo-maker intake {logo.slug}`"
        )
    return Brand(palette, fonts)


def _proposals(logo: LogoDir, key: str) -> list[dict[str, str]]:
    path = logo.ideation / "proposals.toml"
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    return [dict(p) for p in data.get(key, [])]


def intake(logo: LogoDir, client=None) -> dict[str, Any]:
    from logo_maker import fonts as fonts_mod
    from logo_maker import intake as intake_mod

    brief = brief_mod.load(logo.brief)
    client = client or _client(logo)
    log = runlog(logo.run_json)
    result: dict[str, Any] = {}
    if brief.references and not (logo.ideation / "intake.json").exists():
        result["references"] = intake_mod.judge_references(logo, brief, client)
    if not brief.palette and not (logo.ideation / "palette.json").exists():
        proposals = _proposals(logo, "palette")
        if len(proposals) < 2:
            raise AuthoringNeeded(
                "brief.toml has no [palette]: write 6 [[palette]] proposals",
                [logo.ideation / "proposals.toml"],
            )
        try:
            result["palette"] = intake_mod.pick_palette(logo, brief, proposals, client)
        except ValueError as exc:  # every proposal failed WCAG, or jev says none fits
            raise AuthoringNeeded(
                f"write new [[palette]] proposals: {exc}", [logo.ideation / "proposals.toml"]
            ) from exc
    if not brief.fonts and not (logo.ideation / "fonts.json").exists():
        proposals = _proposals(logo, "fonts")
        missing = sorted(
            {
                spec.split(":")[0]
                for p in proposals
                for spec in p.values()
                if not fonts_mod.family_exists(spec.split(":")[0])
            }
        )
        if len(proposals) < 2 or missing:
            note = f" (not in google/fonts: {', '.join(missing)})" if missing else ""
            raise AuthoringNeeded(
                f"brief.toml has no [fonts]: write 6 [[fonts]] proposals{note}",
                [logo.ideation / "proposals.toml"],
            )
        try:
            result["fonts"] = intake_mod.pick_fonts(logo, brief, proposals, client)
        except ValueError as exc:
            raise AuthoringNeeded(
                f"write new [[fonts]] proposals: {exc}", [logo.ideation / "proposals.toml"]
            ) from exc
    for role, spec in brand(logo).fonts.items():
        path = fonts_mod.resolve(spec, on_asset=log.asset)
        result.setdefault("font_files", {})[role] = str(path)
    log.stage("intake", "done")
    return result


# ---------------------------------------------------------------- ideate


def ideate(logo: LogoDir, client=None) -> list[str]:
    from logo_maker import ideate as ideate_mod

    if not logo.metaphors.exists() or "[[metaphor]]" not in logo.metaphors.read_text().replace(
        "# [[", ""
    ):
        raise AuthoringNeeded(
            "write 8-40 [[metaphor]] entries derived from the brief", [logo.metaphors]
        )
    brand(logo)  # intake must be complete
    client = client or _client(logo)
    log = runlog(logo.run_json)
    ideate_mod.build_pool(logo, brief_mod.load(logo.brief), client)
    shortlist = ideate_mod.run_chain(logo, client, shortlist=8)
    for concept in shortlist:
        folder = logo.concept(concept.id)
        info = {
            "id": concept.id,
            "metaphor": concept.metaphor,
            "metaphor_text": concept.metaphor_text,
            "treatment": concept.treatment,
            "treatment_text": concept.treatment_desc,
            "material": concept.material,
            "material_text": concept.material_desc,
        }
        _write_json(folder / "concept.json", info)
    log.stage("ideate", "done", shortlist=[c.id for c in shortlist])
    return [c.id for c in shortlist]


def shortlist(logo: LogoDir) -> list[str]:
    path = logo.ideation / "shortlist.json"
    if not path.exists():
        raise RuntimeError(f"{logo.slug}: no shortlist; run `logo-maker ideate {logo.slug}`")
    data = _read_json(path)
    return list(data["ids"])


# ---------------------------------------------------------------- motifs + preview


def prepare_motif(concept_dir: Path) -> Path:
    """motif.py (preferred) or motif.svg -> validated motif.svg + motif.json. Returns motif.json."""
    from logo_maker import motif

    script, svg, flat = (
        concept_dir / "motif.py",
        concept_dir / "motif.svg",
        concept_dir / "motif.json",
    )
    newest_source = max((p.stat().st_mtime for p in (script, svg) if p.exists()), default=None)
    if newest_source is None:
        raise AuthoringNeeded("author a motif", [script])
    if flat.exists() and flat.stat().st_mtime >= newest_source:
        return flat
    if script.exists() and (not svg.exists() or script.stat().st_mtime > svg.stat().st_mtime):
        motif.run_motif_script(concept_dir)
    problems = motif.validate(svg)
    if problems:
        raise AuthoringNeeded(
            f"{svg} breaks the motif contract: " + "; ".join(problems),
            [script if script.exists() else svg],
        )
    motif.flatten(svg, flat)
    return flat


def _parallel(fn: Callable[[Path], Any], items: list[Path]) -> list[Any]:
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(items)))) as pool:
        return list(pool.map(fn, items))


def _starter_scene(logo: LogoDir, concept_id: str, folder: Path) -> Path:
    """Write the treatment's layer-aware starting scene for a concept whose motif exists."""
    from logo_maker import scene as scene_mod

    info = _read_json(folder / "concept.json")
    doc = tomlkit.parse(
        scene_mod.from_treatment(
            info["treatment"],
            motif_json=folder / "motif.json",
            palette=brand(logo).palette,
            material_id=info["material"],
            seed=runlog(logo.run_json).seed(concept_id),
        )
    )
    doc["meta"]["concept"] = concept_id  # type: ignore[index]
    path = folder / "scene.toml"
    path.write_text(tomlkit.dumps(doc))
    return path


def motifs(logo: LogoDir) -> dict[str, dict[str, str]]:
    """Build every shortlisted motif, its size sheet, and (once) its starter scene.

    Stops with AuthoringNeeded while a motif is missing or broken, and once after writing starter
    scenes so the agent tunes them before anything renders.
    """
    from logo_maker import motif

    dirs = {cid: logo.concept(cid) for cid in shortlist(logo)}
    missing = [
        d / "motif.py"
        for d in dirs.values()
        if not (d / "motif.py").exists() and not (d / "motif.svg").exists()
    ]
    if missing:
        raise AuthoringNeeded(
            "create each listed motif.py from its folder's concept.json "
            "(or drop a motif.svg beside it), then run again",
            missing,
        )
    _parallel(prepare_motif, list(dirs.values()))
    new_scenes: list[Path] = []
    out: dict[str, dict[str, str]] = {}
    for cid, folder in dirs.items():
        svg, sizes = folder / "motif.svg", folder / "motif-sizes.png"
        if not sizes.exists() or sizes.stat().st_mtime < svg.stat().st_mtime:
            motif.size_sheet(svg, sizes)
        if not (folder / "scene.toml").exists():
            new_scenes.append(_starter_scene(logo, cid, folder))
        out[cid] = {"motif": str(svg), "sizes": str(sizes), "scene": str(folder / "scene.toml")}
    if new_scenes:
        raise AuthoringNeeded(
            "tune each starter scene.toml to its concept (references/scene-grammar.md), "
            "then run again",
            new_scenes,
        )
    from logo_maker import scene as scene_mod

    broken = []
    for folder in dirs.values():
        try:
            scene_mod.load_scene(folder / "scene.toml")
        except scene_mod.SceneError as exc:
            broken.append((folder / "scene.toml", str(exc)))
    if broken:
        raise AuthoringNeeded(
            "fix scene.toml: " + "; ".join(f"{p.name}: {e}" for p, e in broken),
            [p for p, _ in broken],
        )
    return out


def preview(logo: LogoDir, client=None, *, keep: int = 3) -> list[str]:
    from logo_maker import judging, render

    ids = shortlist(logo)
    dirs = [logo.concept(cid) for cid in ids]
    motifs(logo)
    todo = [d for d in dirs if not _fresh(d / "preview.png", d)]
    if todo:
        render.render_many(todo, "preview")
    log = runlog(logo.run_json)
    client = client or _client(logo)
    brief = brief_mod.load(logo.brief)
    previews = {cid: logo.concept(cid) / "preview.png" for cid in ids}
    try:
        finalists = judging.screen_previews(logo, brief, previews, client, keep=keep)
    except ValueError as exc:  # no preview survived screening
        raise AuthoringNeeded(
            f"revise the motifs and scenes: {exc}", [logo.concept(cid) / "motif.py" for cid in ids]
        ) from exc
    log.stage("preview", "done", finalists=finalists)
    return finalists


def _fresh(output: Path, concept_dir: Path) -> bool:
    """Only content-bound verified renders are reusable; mtime is insufficient."""
    from logo_maker.render import artifact_current

    return artifact_current(concept_dir, output.stem)


# ---------------------------------------------------------------- finalize + QA loop


def _apply_fixes(scene_path: Path, failures: set[str]) -> list[str]:
    """Map each failed check to one concrete scene edit. Returns what changed."""
    doc = tomlkit.parse(scene_path.read_text())
    changes: list[str] = []
    camera = doc.setdefault("camera", tomlkit.table())
    render_tbl = doc.setdefault("render", tomlkit.table())
    lighting = doc.setdefault("lighting", tomlkit.table())
    if failures & {"nothing_cut_off", "margin"}:
        framing = max(round(float(camera.get("framing", 0.84)) * 0.9, 3), 0.6)
        camera["framing"] = framing
        changes.append(f"camera.framing -> {framing}")
    if "motif_readable" in failures:
        for component in doc.get("components", []):
            if component.get("kind") in {"relief", "layers", "extrude", "inflate"}:
                height = min(round(float(component.get("height_scale", 1.0)) * 1.4, 3), 2.0)
                component["height_scale"] = height
                changes.append(f"{component.get('kind')}.height_scale -> {height}")
        if lighting.get("rig") != "raking":
            lighting["rig"] = "raking"
            changes.append("lighting.rig -> raking")
    if failures & {"no_veil_or_box", "veil"}:
        render_tbl["alpha_cleanup"] = True
        changes.append("render.alpha_cleanup -> true")
    pending = scene_path.with_suffix(".toml.pending")
    pending.write_text(tomlkit.dumps(doc))
    pending.replace(scene_path)
    return changes


def qa_concept(
    logo: LogoDir, concept_id: str, client, brand_: Brand, *, budget: Budget | None = None
) -> dict[str, Any]:
    """Render final, judge, fix, re-render: up to MAX_QA_ROUNDS. Returns the last round's record."""
    from logo_maker import judging, render

    budget = Budget(attempt_limit=4, parent=budget) if budget else Budget(attempt_limit=4)
    budget.check()
    client = _budgeted_client(client, budget)
    brief = _bounded_inputs(logo, budget)[0]
    folder = logo.root / "concepts" / concept_slug(concept_id)
    rounds_path = logo.root / "qa" / "rounds.jsonl"
    log = runlog(logo.run_json, budget=budget)
    record: dict[str, Any] = {}
    for round_no in range(1, MAX_QA_ROUNDS + 1):
        budget.check()
        if not render.artifact_current(folder, "final", budget=budget):
            render.render(folder, "final", budget=budget)
        final = folder / "final.png"
        verdicts = judging.qa_judgments(logo, brief, concept_id, final, client, budget=budget)
        host_stages: list[dict] = []
        code = host.run(
            {"operation": "qa_checks", "png": str(final), "palette": brand_.palette},
            budget,
            host_stages,
        )
        # Only clear fails block and get fixed (questions.qa_blocks); unsettled is recorded.
        failures = {name for name, v in verdicts.items() if qa_blocks(v.status)}
        failures |= {"veil"} if code["alpha"]["veil"] else set()
        failures |= {"margin"} if code["margin"]["cut_off"] else set()
        failures |= {"edges"} if code["edges"]["aliased"] else set()
        unsettled = sorted(name for name, v in verdicts.items() if v.status == "unsettled")
        record = {
            "concept": concept_id,
            "round": round_no,
            "failures": sorted(failures),
            "unsettled": unsettled,
            "verdicts": {k: {"status": v.status, "p": v.p} for k, v in verdicts.items()},
            "code": code,
            "host_stages": host_stages,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        budget.check()
        sampling_path = folder / ".build/final.sampling.json"
        sampling = host.run(
            {"operation": "read_json", "path": str(sampling_path), "default": {}}, budget, []
        )["data"]
        record["sampling"] = sampling.get("outcomes", {"noise": "unknown", "device": "unknown"})
        record["sampling_profile"] = sampling.get("profile", {"state": "profile_unqualified"})
        record["budget"] = budget.record()
        fixable = failures - {"recognizable_at_32px"}
        if failures & {"clean_edges", "edges"}:
            record["result"] = "refinement_needed"
            record["refinement"] = {
                "dimension": "edges_unknown_cause",
                "artifact": str(final),
                "source_key": sampling.get("source_key"),
                "image_sha256": sampling.get("delivered_sha256"),
                "next": "compare independent-seed noisy/denoised detail; distinguish noise, geometry, typography, filtering, resolution and alpha before repair",
            }
        elif not failures and (
            record["sampling_profile"]["state"] != "qualified"
            or record["sampling"].get("sampling") != "profile_baseline"
        ):
            record["result"] = "sampling_review_needed"
        elif not failures:
            record["result"] = "pass"
        elif not fixable:
            record["result"] = "needs_simpler_motif"
        else:
            record["changes"] = host.run(
                {
                    "operation": "apply_fixes",
                    "path": str(folder / "scene.toml"),
                    "failures": sorted(fixable),
                },
                budget,
                [],
            )["changes"]
            record["result"] = "fixing"
        host.run(
            {"operation": "append_jsonl", "path": str(rounds_path), "data": record}, budget, []
        )
        log.event(
            f"qa {concept_id} round {round_no}: {record['result']}",
            failures=sorted(failures),
            budget=budget,
        )
        if record["result"] != "fixing":
            break
    if record.get("result") == "fixing":
        record["result"] = "failed"
    return record


def finalize(logo: LogoDir, client=None, *, budget: Budget | None = None) -> str:
    from logo_maker import judging

    caller_budget = budget
    bootstrap = budget or Budget(attempt_limit=64)
    job_started = bootstrap.clock()
    bootstrap.check()
    brief, brand_, setup = _bounded_inputs(logo, bootstrap, brand_required=True, finalists=True)
    finalists = list(setup["finalists"])
    client = client or _client(logo, budget=bootstrap)
    # One finalist at a time: each final render saturates the GPU.
    budget = Budget(
        attempt_limit=min(64, max(1, len(finalists)) * 4),
        parent=caller_budget,
        clock=bootstrap.clock,
        started_at=job_started,
    )
    budget.check()
    results = {cid: qa_concept(logo, cid, client, brand_, budget=budget) for cid in finalists}
    passed = [cid for cid, r in results.items() if r["result"] == "pass"]
    log = runlog(logo.run_json, budget=budget)
    if not passed:
        log.stage(
            "finalize", "failed", budget=budget, qa={k: v["result"] for k, v in results.items()}
        )
        files = []
        for cid, result in results.items():
            folder = logo.root / "concepts" / concept_slug(cid)
            if result["result"] == "sampling_review_needed":
                files.extend([folder / ".build/final.sampling.json", folder / "scene.toml"])
            elif result["result"] == "refinement_needed":
                files.extend([folder / "scene.toml", folder / ".build/final.sampling.json"])
            else:
                files.append(folder / "motif.py")
        raise AuthoringNeeded(
            "no finalist qualified; inspect sampling/refinement outcomes in qa/rounds.jsonl",
            files,
        )
    if len(passed) == 1:
        winner = passed[0]
        winner_record = {"winner": winner, "reason": "only finalist to pass QA"}
    else:
        winner_record = judging.final_tournament_record(
            brief,
            {cid: (logo.root / "concepts" / concept_slug(cid)) / "final.png" for cid in passed},
            _budgeted_client(client, budget),
        )
        winner = winner_record["winner"]
    log.publish_stage(
        "finalize",
        [
            {
                "target": str(logo.root / "ideation" / "winner.json"),
                "text": json.dumps(winner_record, indent=2),
            },
        ],
        logo.root / "ideation" / (".finalize-publication-" + str(time.monotonic_ns()) + ".json"),
        budget,
        winner=winner,
        qa={k: v["result"] for k, v in results.items()},
    )
    return winner


def winner(logo: LogoDir) -> str:
    path = logo.root / "ideation" / "winner.json"
    if not path.exists():
        raise RuntimeError(f"{logo.slug}: no winner; run `logo-maker finalize {logo.slug}`")
    return _read_json(path)["winner"]


# ---------------------------------------------------------------- export, run, improve


def export(logo: LogoDir, *, budget: Budget | None = None) -> dict[str, Path]:
    from logo_maker import export as export_mod

    budget = budget or Budget()
    budget.check()
    brief, brand_, setup = _bounded_inputs(logo, budget, brand_required=True, winner=True)
    folder = logo.root / "concepts" / concept_slug(setup["winner"])
    from logo_maker.render import artifact_current

    if not artifact_current(folder, "final", budget=budget):
        raise AuthoringNeeded("final provenance changed; finalize again", [folder / "scene.toml"])
    sampling = host.run(
        {"operation": "read_json", "path": str(folder / ".build/final.sampling.json")}, budget, []
    )["data"]
    if (
        sampling.get("profile", {}).get("state") != "qualified"
        or sampling.get("outcomes", {}).get("sampling") != "profile_baseline"
    ):
        raise AuthoringNeeded(
            "sampling qualification unresolved; prior exports retained",
            [folder / ".build/final.sampling.json"],
        )
    manifest = export_mod.export_all(
        folder,
        logo.root / "exports",
        name=brief.name,
        palette=brand_.palette,
        motif_svg=folder / "motif.svg",
        budget=budget,
        publication_log=runlog(logo.run_json, budget=budget),
    )
    return manifest


def run(logo: LogoDir, client=None) -> dict[str, Path]:
    budget = Budget(attempt_limit=12)
    client = client or _client(logo, budget=budget)
    log = runlog(logo.run_json, budget=budget)
    if log.stage_status("intake") != "done":
        intake(logo, client)
    if log.stage_status("ideate") != "done":
        ideate(logo, client)
    if log.stage_status("preview") != "done":
        preview(logo, client)
    if log.stage_status("finalize") != "done":
        finalize(logo, client, budget=budget)
    return export(logo, budget=budget)


def improve(logo: LogoDir, client=None) -> dict[str, Any]:
    """Run a new round of ideas; the current logo is the floor and stays unless a new winner beats it.

    The first call archives the current round under history/ and resets ideation; the agent then adds new
    metaphors and motifs as each stage asks. Once the new round has a winner, it meets the floor
    head-to-head on images; only a win replaces the exports.
    """
    from logo_maker import judging

    client = client or _client(logo)
    log = runlog(logo.run_json)
    floor_dir = logo.root / "floor"
    floor_png = floor_dir / "hero-transparent.png"
    if not floor_png.exists():
        current = logo.exports / "hero-transparent.png"
        if not current.exists():
            raise RuntimeError(
                f"{logo.slug}: nothing to improve yet; run `logo-maker run {logo.slug}` first"
            )
        archive = logo.root / "history" / time.strftime("%Y%m%d-%H%M%S")
        archive.mkdir(parents=True)
        shutil.copytree(logo.exports, archive / "exports")
        for name in (
            "shortlist.json",
            "finalists.json",
            "winner.json",
            "stage1.jsonl",
            "stage2.jsonl",
            "tournament.jsonl",
            "pool.jsonl",
        ):
            src = logo.ideation / name
            if src.exists():
                shutil.move(src, archive / name)
        floor_dir.mkdir(exist_ok=True)
        shutil.copy2(current, floor_png)
        (floor_dir / "archive.txt").write_text(str(archive))
        for stage in ("ideate", "preview", "finalize"):
            log.stage(stage, "reset", by="improve")
        log.event("improve: archived current round as the floor", archive=str(archive))
    for stage, fn in (("ideate", ideate), ("preview", preview), ("finalize", finalize)):
        if log.stage_status(stage) != "done":
            fn(logo, client)
    candidate = logo.concept(winner(logo)) / "final.png"
    brief = brief_mod.load(logo.brief)
    won, detail = judging.beats_floor(logo, brief, candidate, floor_png, client)
    archive = Path((floor_dir / "archive.txt").read_text())
    if won:
        manifest = export(logo)
        shutil.rmtree(floor_dir)
        log.stage("improve", "replaced", detail=detail)
        return {
            "result": "replaced",
            "winner": winner(logo),
            "exports": {k: str(v) for k, v in manifest.items()},
        }
    # The floor held: keep its exports and winner; file the challenger beside the archive.
    shutil.move(logo.ideation / "winner.json", archive / "challenger-winner.json")
    shutil.copy2(archive / "winner.json", logo.ideation / "winner.json")
    shutil.rmtree(floor_dir)
    log.stage("improve", "floor_held", detail=detail)
    return {"result": "floor_held", "detail": detail}
