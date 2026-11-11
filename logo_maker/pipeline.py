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
from logo_maker.paths import LogoDir
from logo_maker.runlog import runlog
from logo_maker.sampling import Budget, sampling_qualified

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


class AuthoringNeeded(RuntimeError):
    """The agent must write files before the stage can continue. `files` lists them."""

    def __init__(self, message: str, files: list[Path], *, details: dict | None = None):
        super().__init__(message + "\n" + "\n".join(f"  - {f}" for f in files))
        self.files = files
        self.details = details or {}


@dataclass(frozen=True)
class Brand:
    palette: dict[str, str]
    fonts: dict[str, str]


def _client(logo: LogoDir):
    from logo_maker.jev.client import JevClient

    return JevClient(logo)


def _budgeted_client(client, budget: Budget):
    from logo_maker.proc import ToolError

    binder = getattr(client, "with_budget", None)
    if not callable(binder):
        raise ToolError("budget_conflict: bounded judgments require explicit client budget binding")
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
    from logo_maker.refinement import concept_sources, digest

    if not script.exists() and not svg.exists():
        raise AuthoringNeeded("author a motif", [script])
    receipt = concept_dir / ".motif-state.json"
    previous = _read_json(receipt) if receipt.exists() else {}
    dependencies = {
        name: digest(path)
        for name, path in concept_sources(concept_dir, exclude={"motif.json", "motif.svg"}).items()
    }
    source_hashes = {p.name: digest(p) for p in (script, svg) if p.exists()}
    if (
        flat.exists()
        and previous.get("sources") == source_hashes
        and previous.get("flat") == digest(flat)
        and previous.get("dependencies") == dependencies
    ):
        return flat
    if script.exists() and (
        not svg.exists()
        or previous.get("sources", {}).get("motif.py") != digest(script)
        or previous.get("dependencies") != dependencies
    ):
        motif.run_motif_script(concept_dir)
    problems = motif.validate(svg)
    if problems:
        raise AuthoringNeeded(
            f"{svg} breaks the motif contract: " + "; ".join(problems),
            [script if script.exists() else svg],
        )
    motif.flatten(svg, flat)
    _write_json(
        receipt,
        {
            "sources": {p.name: digest(p) for p in (script, svg) if p.exists()},
            "flat": digest(flat),
            "dependencies": dependencies,
        },
    )
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
        from logo_maker.refinement import digest

        receipt = folder / ".sizes-state.json"
        if (
            not sizes.exists()
            or not receipt.exists()
            or _read_json(receipt).get("svg") != digest(svg)
        ):
            motif.size_sheet(svg, sizes)
            _write_json(receipt, {"svg": digest(svg)})
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


def refine(logo: LogoDir, client=None, *, budget: Budget | None = None) -> dict[str, Any]:
    """Inspect image-backed creative readiness before presenting finalists."""
    from logo_maker import refinement

    if budget is not None:
        budget.check()
    ids = shortlist(logo)
    for cid in ids:
        refinement.construction(logo.concept(cid))
    motifs(logo)
    records = []
    inspection_bindings = {}
    for cid in ids:
        record = refinement.capture(logo, cid, "preview", budget=budget)
        inspection_path = logo.concept(cid) / "inspection.json"
        inspection_binding = refinement.digest(inspection_path) if inspection_path.exists() else ""
        inspection = refinement.inspected(logo, cid, record)
        if client is None:
            client = _client(logo)
        if budget is not None and not records:
            client = _budgeted_client(client, budget)
        refinement.judge_revision(logo, cid, record, inspection, client)
        refinement.require_current(
            logo, cid, record, budget=budget, inspection_sha256=inspection_binding
        )
        inspection_bindings[cid] = inspection_binding
        records.append(record)
    refinement.alternatives(logo, records, client or _client(logo))
    for record in records:
        refinement.require_current(
            logo,
            record["concept"],
            record,
            budget=budget,
            inspection_sha256=inspection_bindings[record["concept"]],
        )
    return status(logo)


def status(logo: LogoDir) -> dict[str, Any]:
    """Separate ideation combinations, authored motifs, renders and refinement evidence."""
    from logo_maker import refinement

    ids = shortlist(logo) if (logo.ideation / "shortlist.json").exists() else []
    return refinement.report(logo, ids)


def preview(
    logo: LogoDir, client=None, *, keep: int = 3, budget: Budget | None = None
) -> list[str]:
    from logo_maker import judging, refinement

    ids = shortlist(logo)
    refine(logo, client, budget=budget)
    binding = refinement.campaign_key(logo, ids)
    existing = logo.ideation / "finalists.json"
    if existing.exists() and _read_json(existing).get("binding") == binding:
        return list(_read_json(existing)["ids"])
    log = runlog(logo.run_json)
    client = client or _client(logo)
    brief = brief_mod.load(logo.brief)
    previews = {cid: logo.concept(cid) / "preview.png" for cid in ids}
    if budget is not None:
        client = _budgeted_client(client, budget)
    try:
        finalists = judging.screen_previews(logo, brief, previews, client, keep=keep)
    except ValueError as exc:  # no preview survived screening
        raise AuthoringNeeded(
            f"revise the motifs and scenes: {exc}", [logo.concept(cid) / "motif.py" for cid in ids]
        ) from exc
    if refinement.campaign_key(logo, ids) != binding:
        raise AuthoringNeeded(
            "inputs changed while judging previews; refresh refinement",
            [logo.ideation / "finalists.json"],
        )
    doc = _read_json(logo.ideation / "finalists.json")
    doc["binding"] = binding
    qualification = {}
    for cid in finalists:
        active = refinement.current(logo, cid, "preview", budget=budget)
        if active is None:
            raise AuthoringNeeded(
                "inputs changed while judging previews; refresh refinement",
                [logo.concept(cid) / "inspection.json"],
            )
        qualification[cid] = {
            "creative": "ready",
            "sampling": active.get("sampling", {}).get("profile", {"state": "unknown"}),
        }
    doc["qualification"] = qualification
    _write_json(logo.ideation / "finalists.json", doc)
    log.stage("preview", "done", finalists=finalists)
    return finalists


# ---------------------------------------------------------------- finalize + diagnosis


def qa_concept(
    logo: LogoDir, concept_id: str, client, brand_: Brand, *, budget: Budget | None = None
) -> dict[str, Any]:
    """One retained final per revision; diagnosis returns work rather than guessing repairs."""
    from logo_maker import judging, refinement

    budget = Budget(attempt_limit=4, parent=budget)
    budget.check()
    client = _budgeted_client(client, budget)
    brief = brief_mod.load(logo.brief)
    folder = logo.concept(concept_id)
    record = refinement.capture(logo, concept_id, "final", budget=budget)
    final = folder / "final.png"
    verdicts = judging.qa_judgments(logo, brief, concept_id, final, client, budget=budget)
    host_stages: list[dict] = []
    code = host.run(
        {"operation": "qa_checks", "png": str(final), "palette": brand_.palette},
        budget,
        host_stages,
    )
    failures = {name for name, v in verdicts.items() if qa_blocks(v.status)}
    failures |= {"veil"} if code["alpha"]["veil"] else set()
    failures |= {"margin"} if code["margin"]["cut_off"] else set()
    failures |= {"edges"} if code["edges"]["aliased"] else set()
    result = {
        "concept": concept_id,
        "revision": record["revision"],
        "artifact": record["image"],
        "image_sha256": record["image_sha256"],
        "failures": sorted(failures),
        "unsettled": sorted(n for n, v in verdicts.items() if v.status == "unsettled"),
        "verdicts": {k: {"status": v.status, "p": v.p} for k, v in verdicts.items()},
        "code": code,
        "host_stages": host_stages,
        "result": "authoring_needed" if failures else "technical_pass",
        "sampling": record.get("sampling", {}),
        "budget": budget.record(),
        "diagnosis": {
            "cause": "unknown",
            "sampling_action": "none",
            "next_comparison": "independent-seed noisy/denoised detail for stochastic noise (#5); inspect persistent geometry, material, typography, filtering/resolution and alpha separately",
        },
    }
    result["diagnosis"] = refinement.diagnosis(logo, concept_id, record, result["diagnosis"])

    def retain() -> None:
        with (logo.qa / "rounds.jsonl").open("a") as fh:
            fh.write(json.dumps(result) + "\n")
        refinement.write(logo.root / record["evidence"] / "qa.json", result)

    if failures:
        retain()
        raise AuthoringNeeded(
            "technical diagnosis required; generic edge failure does not establish sampling noise",
            [
                folder / "diagnosis.json",
                folder / "inspection-final.json",
                folder / "scene.toml",
                folder / "construction.json",
            ],
            details=result,
        )
    if not sampling_qualified(record.get("sampling", {})):
        result["result"] = "sampling_review_needed"
        retain()
        raise AuthoringNeeded(
            "sampling qualification unresolved; creative validity cannot replace #5's profile gate",
            [folder / ".build/final.sampling.json", folder / "scene.toml"],
            details={
                "dimension": "sampling_profile",
                "sampling": record.get("sampling", {}),
                "artifact": record["image"],
            },
        )
    try:
        budget.check()
        inspection_path = folder / "inspection-final.json"
        inspection_binding = refinement.digest(inspection_path) if inspection_path.exists() else ""
        inspection = refinement.inspected(logo, concept_id, record)
        refinement.judge_revision(logo, concept_id, record, inspection, client)
        refinement.require_current(
            logo, concept_id, record, budget=budget, inspection_sha256=inspection_binding
        )
        result["inspection_sha256"] = inspection_binding
        budget.check()
    except AuthoringNeeded:
        result["result"] = "creative_review_needed"
        retain()
        raise
    result["result"] = "pass"
    retain()
    return result


def finalize(logo: LogoDir, client=None, *, budget: Budget | None = None) -> str:
    from logo_maker import judging

    caller_budget = budget
    bootstrap = budget or Budget(attempt_limit=64)
    job_started = bootstrap.clock()
    bootstrap.check()
    finalists_path = logo.ideation / "finalists.json"
    if not finalists_path.exists():
        raise RuntimeError(f"{logo.slug}: no finalists; run `logo-maker preview {logo.slug}`")
    from logo_maker import refinement

    data = _read_json(finalists_path)
    refinement.require_binding(logo, data, "preview")
    campaign_binding = data["binding"]
    finalists = list(data["ids"])
    client = client or _client(logo)
    brand_ = brand(logo)
    # One finalist at a time: each final render saturates the GPU.
    budget = Budget(
        attempt_limit=min(64, max(1, len(finalists)) * 4),
        parent=caller_budget,
        clock=bootstrap.clock,
        started_at=job_started,
    )
    budget.check()
    client = _budgeted_client(client, budget)
    results = {cid: qa_concept(logo, cid, client, brand_, budget=budget) for cid in finalists}
    passed = [cid for cid, r in results.items() if r["result"] == "pass"]
    log = runlog(logo.run_json)
    if not passed:
        log.stage("finalize", "failed", qa={k: v["result"] for k, v in results.items()})
        raise AuthoringNeeded(
            "no finalist passed QA; simplify the motifs named in qa/rounds.jsonl",
            [logo.concept(cid) / "motif.py" for cid in finalists],
        )

    def require_final_bindings() -> None:
        stale = refinement.campaign_key(logo, shortlist(logo)) != campaign_binding
        for cid in passed:
            active = refinement.current(logo, cid, "final", budget=budget)
            inspection = logo.concept(cid) / "inspection-final.json"
            if (
                not active
                or active["revision"] != results[cid]["revision"]
                or active["image_sha256"] != results[cid]["image_sha256"]
                or not inspection.exists()
                or refinement.digest(inspection) != results[cid]["inspection_sha256"]
            ):
                stale = True
        if stale:
            raise AuthoringNeeded(
                "final eligibility changed while judging; refresh the affected renders/inspections",
                [logo.concept(cid) / "inspection-final.json" for cid in passed],
                details={"dimension": "stale_final_judgment"},
            )

    winner_path = logo.ideation / "winner.json"
    prior_winner = winner_path.read_bytes() if winner_path.exists() else None
    try:
        require_final_bindings()
        brief = brief_mod.load(logo.brief)
        if len(passed) == 1:
            winner = passed[0]
            _write_json(
                logo.ideation / "winner.json",
                {"winner": winner, "reason": "only finalist to pass QA"},
            )
        else:
            winner = judging.final_tournament(
                logo, brief, {cid: logo.concept(cid) / "final.png" for cid in passed}, client
            )
        require_final_bindings()
        winner_doc = _read_json(logo.ideation / "winner.json")
        winner_doc["binding"] = campaign_binding
        winner_doc["final_sha256"] = results[winner]["image_sha256"]
        winner_doc["final_inspection_sha256"] = results[winner]["inspection_sha256"]
        _write_json(logo.ideation / "winner.json", winner_doc)
        budget.check()
        log.stage(
            "finalize", "done", winner=winner, qa={k: v["result"] for k, v in results.items()}
        )
        return winner
    except BaseException:
        if prior_winner is None:
            winner_path.unlink(missing_ok=True)
        else:
            winner_path.write_bytes(prior_winner)
        raise


def winner(logo: LogoDir) -> str:
    path = logo.ideation / "winner.json"
    if not path.exists():
        raise RuntimeError(f"{logo.slug}: no winner; run `logo-maker finalize {logo.slug}`")
    return _read_json(path)["winner"]


# ---------------------------------------------------------------- export, run, improve


def export(logo: LogoDir, *, budget: Budget | None = None) -> dict[str, Path]:
    from logo_maker import export as export_mod
    from logo_maker import refinement

    budget = budget or Budget()
    budget.check()
    winner_doc = _read_json(logo.ideation / "winner.json")
    refinement.require_binding(logo, winner_doc, "finalize")
    final = logo.concept(winner_doc["winner"]) / "final.png"
    inspection = final.parent / "inspection-final.json"
    if (
        not final.exists()
        or winner_doc.get("final_sha256") != refinement.digest(final)
        or not inspection.exists()
        or winner_doc.get("final_inspection_sha256") != refinement.digest(inspection)
    ):
        raise AuthoringNeeded("stale final image; rerun finalize", [final])
    from logo_maker.render import artifact_current

    folder = logo.concept(winner_doc["winner"])
    sampling_path = folder / ".build/final.sampling.json"
    if (
        not artifact_current(folder, "final", budget=budget)
        or not sampling_path.exists()
        or not sampling_qualified(_read_json(sampling_path))
    ):
        raise AuthoringNeeded(
            "sampling qualification unresolved; prior exports retained", [sampling_path]
        )
    brief = brief_mod.load(logo.brief)
    manifest = export_mod.export_all(
        folder,
        logo.exports,
        name=brief.name,
        palette=brand(logo).palette,
        motif_svg=folder / "motif.svg",
        budget=budget,
    )
    runlog(logo.run_json).stage("export", "done", files=len(manifest))
    return manifest


def run(logo: LogoDir, client=None) -> dict[str, Path]:
    client = client or _client(logo)
    log = runlog(logo.run_json)
    if log.stage_status("intake") != "done":
        intake(logo, client)
    if log.stage_status("ideate") != "done":
        ideate(logo, client)
    preview(logo, client)
    budget = Budget(attempt_limit=12)
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
    if log.stage_status("ideate") != "done":
        ideate(logo, client)
    preview(logo, client)
    budget = Budget(attempt_limit=12)
    finalize(logo, client, budget=budget)
    candidate = logo.concept(winner(logo)) / "final.png"
    brief = brief_mod.load(logo.brief)
    won, detail = judging.beats_floor(logo, brief, candidate, floor_png, client)
    archive = Path((floor_dir / "archive.txt").read_text())
    budget.check()
    if won:
        manifest = export(logo, budget=budget)
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
