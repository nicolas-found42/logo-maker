"""Deliver owner-selected 3D studies and resume review of the delivered bytes."""

from __future__ import annotations

import json
import math
import platform
import shutil
import sys
import uuid
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw

from logo_maker import checks, host, motif, owned_process, pipeline, scene
from logo_maker.brief import Brief, load
from logo_maker.export import _contact_sheet, _ink, _paper, _sha256, _svgs, optimize_svg
from logo_maker.paths import LogoDir, concept_slug
from logo_maker.publication import publish
from logo_maker.sampling import Budget

VIEWS = ("front", "grazing", "rear", "underside")
SIZES = (16, 32, 48, 180, 512)
STUDY_ID = "study-"
DESCRIPTION = {
    "label": "",
    "description": "",
    "metaphor_text": "",
    "material_text": "",
    "treatment_text": "",
    "treatment": "extruded_solid",
    "material": "matte_plastic",
}


def _read(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _safe(root: Path, relative: str) -> Path:
    file = root / relative
    if Path(relative).is_absolute() or not file.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path must remain within {root}: {relative}")
    return file


def summaries(logo: LogoDir) -> list[dict]:
    result = []
    for root in sorted((logo.root / "studies").glob(f"{STUDY_ID}*")):
        file = root / "manifest.json"
        if not file.is_file():
            continue
        record = logo.root / "qa" / "studies" / root.name / "review.json"
        result.append(
            {
                "study_id": root.name,
                "manifest": str(file),
                "overview": str(root / "overview.png"),
                "archive": str(root / "study.zip") if (root / "study.zip").is_file() else None,
                "review": str(record) if record.is_file() else None,
            }
        )
    return result


def _designs(logo: LogoDir, ids: list[str]) -> list[tuple[str, Path]]:
    if not ids or not all(pipeline.is_concept_id(cid) for cid in ids):
        raise ValueError("name at least one concept with --concept")
    folders = [logo.concept_path(cid) for cid in ids]
    if len(set(folders)) != len(folders):
        raise ValueError("each study concept must name a distinct folder")
    missing = []
    for cid, folder in zip(ids, folders, strict=True):
        _safe(logo.root / "concepts", folder.name)
        info = folder / "concept.json"
        if not info.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            try:
                with info.open("x") as handle:
                    json.dump({"id": cid, **DESCRIPTION}, handle, indent=2)
            except FileExistsError:
                pass
        description = _read(info).get("description", "")
        if not isinstance(description, str) or not description.strip():
            missing.append(info)
        if not (folder / "motif.svg").exists() and not (folder / "motif.py").exists():
            missing.append(folder / "motif.py")
    if missing:
        raise pipeline.AuthoringNeeded(
            "Describe each named design and author its motif. Supply a scene recipe or a packed Blender scene.",
            missing,
        )
    return list(zip(ids, folders, strict=True))


def _source(
    folder: Path, staged: Path, brief: Brief, cid: str, budget: Budget
) -> tuple[Path, bool]:
    pipeline.prepare_motif(folder)
    for name in ("motif.svg", "motif.json"):
        shutil.copyfile(folder / name, staged / name)
    custom = folder / "source.blend"
    if custom.is_file():
        shutil.copyfile(custom, staged / "source.blend")
        return staged / "source.blend", False
    recipe = folder / "scene.toml"
    if not recipe.is_file():
        info = _read(folder / "concept.json")
        recipe.write_text(
            scene.from_treatment(
                info.get("treatment", "extruded_solid"),
                motif_json=folder / "motif.json",
                palette=brief.palette,
                material_id=info.get("material", "matte_plastic"),
                seed=0,
            )
        )
        raise pipeline.AuthoringNeeded(
            f"Tune the starter scene for {cid}, then rerun the study.", [recipe]
        )
    # Compile from a private snapshot so a concurrent study cannot replace its meshes.
    staged_recipe = staged / "scene.toml"
    shutil.copyfile(recipe, staged_recipe)
    recipe_sha256 = _sha256(staged_recipe)
    config = scene.load_scene(staged_recipe)
    for component in config["components"]:
        if component["kind"] == "bpy":
            raise pipeline.AuthoringNeeded(
                "Save the custom construction as a packed source.blend for the study.", [custom]
            )
        if component["kind"] == "mesh":
            mesh = (folder / component["path"]).resolve()
            if not mesh.is_file():
                raise ValueError(f"missing scene mesh: {mesh}")
    import tomlkit

    doc = tomlkit.parse(staged_recipe.read_text())
    for component in doc["components"]:
        if component.get("kind") == "mesh":
            component["path"] = str((folder / component["path"]).resolve())
        if component.get("kind") == "ring_text":
            component["font"] = str(scene.resolve_font(component["font"], folder).resolve())
    staged_recipe.write_text(tomlkit.dumps(doc))
    compiled = host.run(
        {"operation": "compile", "concept_dir": str(staged), "quality": "preview"}, budget, []
    )
    _write(
        staged / "scene-inputs.json",
        {
            "recipe_sha256": recipe_sha256,
            "motif_svg_sha256": _sha256(staged / "motif.svg"),
            "motif_json_sha256": _sha256(staged / "motif.json"),
            "assets": [
                {key: value for key, value in row.items() if key != "path"}
                for row in compiled["assets"]
            ],
        },
    )
    return Path(compiled["scene_json"]), True


def _render(
    source: Path, compiled: bool, out: Path, name: str, budget: Budget, *, diagnostics=False
) -> dict:
    budget.begin_attempt()
    large = name in {"hero-transparent", "independent-seed", "lower-threshold"}
    payload = {
        "source": str(source),
        "compiled": compiled,
        "output": str(out),
        "view": name,
        "resolution": 2000 if large else 768,
        "samples": 768 if large else 80,
        "diagnostics": diagnostics,
    }
    result = owned_process.run(
        [sys.executable, "-m", "logo_maker.blender.study"],
        input_text=json.dumps(payload),
        budget=budget,
        timeout=900,
        label=f"study {name}",
    )
    if result.returncode:
        raise RuntimeError(f"study {name}: {host.failure(result.stderr or result.stdout)}")
    evidence = json.loads(result.stdout.splitlines()[-1])
    png = out / f"{name}.png"
    if (
        evidence.get("status") != "verified"
        or evidence.get("png_sha256") != _sha256(png)
        or evidence.get("inputs_sha256", {}).get("source") != _sha256(source)
        or evidence.get("log_sha256") != _sha256(out / f"{name}-execution.log")
    ):
        raise RuntimeError(f"study {name}: render verification failed")
    return evidence


def _flat(folder: Path, work: Path, out: Path, brief: Brief) -> dict[str, Path]:
    master = work / "motif.svg"
    paths = _svgs(master, out, _ink(brief.palette))
    mono = folder / "mono.svg"
    if mono.is_file():
        copy = work / mono.name
        shutil.copyfile(mono, copy)
        if problems := motif.validate(copy):
            raise pipeline.AuthoringNeeded("Fix mono.svg: " + "; ".join(problems), [mono])
        optimize_svg(copy, paths["mark-mono"])
    for size in (256, 1024):
        paths[f"flat-{size}"] = motif.rasterize(master, size, out / f"mark-flat-{size}.png")
    for suffix in ("", "-dark"):
        compact = folder / f"compact{suffix}.svg"
        if suffix and not compact.is_file():
            continue
        source = master
        if compact.is_file():
            source = work / compact.name
            shutil.copyfile(compact, source)
            if problems := motif.validate(source):
                raise pipeline.AuthoringNeeded(
                    f"Fix {compact.name}: " + "; ".join(problems), [compact]
                )
        paths[f"mark-compact{suffix}"] = optimize_svg(source, out / f"mark-compact{suffix}.svg")
        icons = {
            size: motif.rasterize(source, size, out / f"favicon{suffix}-{size}.png")
            for size in SIZES
        }
        paths.update({f"favicon{suffix}-{size}": file for size, file in icons.items()})
        with (
            Image.open(icons[48]) as large,
            Image.open(icons[16]) as small,
            Image.open(icons[32]) as medium,
        ):
            paths[f"favicon{suffix}-ico"] = out / f"favicon{suffix}.ico"
            large.save(
                paths[f"favicon{suffix}-ico"],
                sizes=[(16, 16), (32, 32), (48, 48)],
                append_images=[small, medium],
            )
    return paths


def _compact_sheet(paths: dict[str, Path], destination: Path) -> None:
    sheet = Image.new("RGB", (400, 176), "#FFFFFF")
    draw = ImageDraw.Draw(sheet)
    for y, surface, caption, ink, suffix in (
        (0, "#F7F7F7", "Light surface", "#171717", ""),
        (88, "#171717", "Dark surface", "#F7F7F7", "-dark"),
    ):
        draw.rectangle((0, y, 399, y + 87), fill=surface)
        draw.text((16, y + 36), caption, fill=ink)
        for x, size in ((154, 16), (272, 32)):
            with Image.open(paths.get(f"favicon{suffix}-{size}", paths[f"favicon-{size}"])) as icon:
                image = icon.convert("RGBA")
                sheet.paste(image, (x, y + 36 - size // 2), image)
            draw.text((x + 42, y + 30), f"{size} px", fill=ink)
    sheet.save(destination)


def _references(logo: LogoDir, brief: Brief, folder: Path, out: Path) -> list[dict]:
    from logo_maker.jev.questions import MATCHED_FEATURES

    authored = folder / "references.json"
    extra = _read(authored).get("photos", []) if authored.exists() else []
    if not isinstance(extra, list):
        raise ValueError(f"{authored}: photos must be a list")
    rows = [{"path": str(ref.path), "note": ref.note, "use": ref.use} for ref in brief.references]
    for row in extra:
        if not isinstance(row, dict) or not all(
            isinstance(row.get(k), str) and row[k].strip()
            for k in ("path", "url", "note", "coverage")
        ):
            raise ValueError(f"{authored}: each photo needs path, url, note and coverage")
        if (
            urlparse(row["url"]).scheme not in ("http", "https")
            or not urlparse(row["url"]).hostname
        ):
            raise ValueError(f"{authored}: use the photo's HTTP source URL")
        use = row.get("use", "craft")
        if use not in {"craft", "holdout", "research"}:
            raise ValueError(f"{authored}: use must be craft, holdout or research")
        match = row.get("match")
        if match is not None:
            if (
                not isinstance(match, dict)
                or match.get("feature") not in MATCHED_FEATURES
                or match.get("view") not in (*VIEWS, "hero-transparent")
                or use == "research"
            ):
                raise ValueError(
                    f"{authored}: match needs a supported feature and render view on a craft or holdout photo"
                )
            for name in ("render_region", "photo_region"):
                box = match.get(name, [0, 0, 1, 1])
                if not _valid_region(box):
                    raise ValueError(
                        f"{authored}: {name} needs a normalized [left, top, right, bottom] box"
                    )
        rows.append(
            {
                "path": str(_safe(logo.root, row["path"])),
                "url": row["url"],
                "note": row["note"],
                "coverage": row["coverage"],
                "use": use,
                **({"match": match} if match is not None else {}),
            }
        )
    photos = out / "references"
    photos.mkdir()
    records, seen = [], {}
    for row in rows:
        source = Path(row["path"])
        if not source.is_file():
            records.append({**row, "path": source.name, "state": "missing"})
            continue
        digest = _sha256(source)
        if digest in seen:
            if row["use"] == "holdout" and seen[digest] != "holdout":
                records.append({**row, "path": source.name, "state": "duplicate", "sha256": digest})
            continue
        with Image.open(source) as photo:
            kind = (photo.format or "").lower()
            if kind not in ("jpeg", "png", "webp"):
                raise ValueError(f"reference must be a JPEG, PNG or WebP: {source}")
            photo.verify()
        seen[digest] = row["use"]
        destination = photos / f"{len(records) + 1:02d}.{kind}"
        shutil.copyfile(source, destination)
        if _sha256(destination) != digest:
            raise ValueError(f"reference changed during study: {source}")
        records.append(
            {
                **row,
                "path": destination.relative_to(out).as_posix(),
                "state": "available",
                "sha256": digest,
            }
        )
    return records


def _local_checks(png: Path) -> dict:
    with Image.open(png) as image:
        if image.mode != "RGBA" or image.size != (2000, 2000):
            raise ValueError("study hero must be a 2000 px square RGBA image")
        low, high = image.getchannel("A").getextrema()
        if low == high:
            raise ValueError("study hero needs visible artwork and a transparent background")
    return {
        "alpha": checks.alpha_report(png),
        "margin": checks.margin_report(png),
        "edges": checks.edge_report(png),
    }


def _valid_region(box) -> bool:
    return (
        isinstance(box, list)
        and len(box) == 4
        and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


def _seed_check(hero: Path, alternate: Path, folder: Path) -> dict:
    import numpy as np

    with Image.open(hero) as first, Image.open(alternate) as second:
        a, b = np.array(first, dtype=np.int16), np.array(second, dtype=np.int16)
    if a.shape != b.shape:
        raise ValueError("seed comparison requires matching image sizes")
    height, width = a.shape[:2]
    regions = {"full": [0, 0, 1, 1]}
    if (folder / "sampling-regions.json").exists():
        regions.update(_read(folder / "sampling-regions.json"))
    evidence = {}
    for name, box in regions.items():
        if not _valid_region(box):
            raise ValueError(f"sampling region {name!r} must be a normalized box")
        x0, y0, x1, y1 = [
            round(v * axis) for v, axis in zip(box, (width, height, width, height), strict=True)
        ]
        p, q = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
        solid = (p[..., 3] >= 253) & (q[..., 3] >= 253)
        delta = np.max(np.abs(p[..., :3] - q[..., :3]), axis=-1)[solid]
        evidence[name] = {
            "opaque_pixels": int(delta.size),
            "mean_max_channel_delta": float(delta.mean()) if delta.size else None,
            "p95_max_channel_delta": float(np.percentile(delta, 95)) if delta.size else None,
        }
    return {
        "regions": evidence,
        "hero_sha256": _sha256(hero),
        "alternate_sha256": _sha256(alternate),
    }


def _package_design(logo, brief, cid, folder, work, out, source, compare_seed, calibrate, budget):
    info = _read(folder / "concept.json")
    identity = folder / "identity.png"
    identity_note = info.get("identity_note", "")
    if identity.is_file() or identity_note:
        if (
            not identity.is_file()
            or not isinstance(identity_note, str)
            or not identity_note.strip()
        ):
            raise pipeline.AuthoringNeeded(
                "Supply identity.png and describe the permitted adaptation in concept.json's identity_note.",
                [identity, folder / "concept.json"],
            )
        with Image.open(identity) as im:
            if im.format != "PNG":
                raise ValueError(f"expected a PNG: {identity}")
            im.verify()
        shutil.copyfile(identity, out / "identity.png")
    paths = _flat(folder, work, out, brief)
    _compact_sheet(paths, out / "compact-light-dark.png")
    references = _references(logo, brief, folder, out)
    hero_report = _render(*source, out, "hero-transparent", budget, diagnostics=calibrate)
    blend = out / "scene.blend"
    if hero_report.get("inputs_sha256", {}).get("editable_scene") != _sha256(blend):
        raise RuntimeError("the editable scene does not match the hero execution evidence")
    if source[1]:
        shutil.copyfile(work / "scene-inputs.json", out / "scene-inputs.json")
        shutil.copyfile(work / "motif.svg", out / "motif-source.svg")
        shutil.copyfile(work / "motif.json", out / "motif-source.json")
    hero = out / "hero-transparent.png"
    report = _local_checks(hero)
    for view in VIEWS:
        _render(blend, False, out, view, budget)
    _contact_sheet(
        [(label, out / f"{label}.png") for label in VIEWS],
        out / "inspection-views.png",
        columns=2,
    )
    _contact_sheet(
        [
            ("Hero", hero),
            ("Flat mark", paths["mark-color"]),
            ("Monochrome", paths["mark-mono"]),
            ("Compact 32 px", paths["favicon-32"]),
        ],
        out / "contact-sheet.png",
        mono_background=_paper(brief.palette),
        columns=2,
    )
    available = [
        row
        for row in references
        if row["state"] == "available" and row["use"] in {"craft", "holdout"}
    ]
    if available:
        _contact_sheet(
            [("Hero", hero)]
            + [
                (row["use"] + " photo " + str(i), out / row["path"])
                for i, row in enumerate(available, 1)
            ],
            out / "reference-sheet.png",
            mono_background=_paper(brief.palette),
        )
    if compare_seed or calibrate:
        other = _render(blend, False, out, "independent-seed", budget)
        if hero_report["sampling"]["seed"] == other["sampling"]["seed"]:
            raise RuntimeError("seed comparison used the same seed twice")
        comparison = _seed_check(hero, out / "independent-seed.png", folder)
        comparison["executions"] = [
            {"sampling": row["sampling"], "seconds": row["seconds"]} for row in (hero_report, other)
        ]
        if calibrate:
            control = _render(blend, False, out, "lower-threshold", budget, diagnostics=True)
            settings = hero_report["sampling"]
            control_settings = dict(control["sampling"])
            threshold = control_settings.pop("adaptive_threshold")
            if (
                control_settings != {k: v for k, v in settings.items() if k != "adaptive_threshold"}
                or threshold >= settings["adaptive_threshold"]
            ):
                raise RuntimeError("calibration must change only the adaptive threshold")
            comparison["lower_threshold"] = {
                **_seed_check(hero, out / "lower-threshold.png", folder),
                "sampling": control["sampling"],
                "seconds": control["seconds"],
                "diagnostics": [hero_report["diagnostics"], control["diagnostics"]],
            }
        _write(out / "sampling-comparison.json", comparison)
    authored = folder / "inspection"
    if authored.is_dir():
        for file in sorted(authored.iterdir()):
            if file.is_file() and file.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".json",
                ".md",
            }:
                with_image = file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                if with_image:
                    with Image.open(file) as image:
                        image.verify()
                target = out / "inspection" / file.name
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(file, target)
    _write(
        out / "design.json",
        {
            "id": cid,
            "concept": info,
            "references": references,
            "motif_source_sha256": _sha256(work / "motif.svg"),
            "local_checks": report,
            "sampling": "local render study",
            "review": "see the review receipt for this study",
        },
    )
    return info.get("label") or cid


def _zip(directory: Path, output: Path) -> None:
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=2) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(directory).as_posix())


def _inventory(root: Path) -> dict[str, dict]:
    return {
        file.relative_to(root).as_posix(): {"sha256": _sha256(file), "bytes": file.stat().st_size}
        for file in sorted(root.rglob("*"))
        if file.is_file()
    }


def build(
    logo: LogoDir,
    concepts: list[str],
    *,
    preview=False,
    compare_seed=False,
    calibrate=False,
    wall_seconds=1800,
    budget: Budget | None = None,
) -> dict:
    """Render named concepts from the brief, with no model credentials required."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("3D studies require Apple Silicon macOS")
    if preview and (compare_seed or calibrate):
        raise ValueError("sampling comparisons require the full study")
    attempt_count = len(concepts) * (
        1 if preview else 5 + int(compare_seed or calibrate) + int(calibrate)
    )
    budget = budget or Budget(wall_seconds, attempt_limit=64)
    if attempt_count > budget.attempt_limit:
        raise ValueError(
            f"study needs {attempt_count} renders; the job allows {budget.attempt_limit}"
        )
    designs = _designs(logo, concepts)
    root = logo.root / "studies"
    root.mkdir(exist_ok=True)
    study_id = STUDY_ID + uuid.uuid4().hex[:12]
    target = root / study_id
    with TemporaryDirectory(prefix=".study-", dir=root) as directory:
        staging = Path(directory)
        assets = staging / "deliverables"
        assets.mkdir()
        work_root = staging / "work"
        work_root.mkdir()
        brief_bytes = logo.brief.read_bytes()
        brief = load(logo.brief, content=brief_bytes)
        (assets / "brief.toml").write_bytes(brief_bytes)
        sheet_entries = []
        prepared = []
        for cid, folder in designs:
            slug = concept_slug(cid)
            work, out = work_root / slug, assets / slug
            work.mkdir()
            out.mkdir()
            source = _source(folder, work, brief, cid, budget)
            prepared.append((cid, folder, work, out, source))
        for cid, folder, work, out, source in prepared:
            if preview:
                _render(*source, out, "preview", budget)
                label, png = _read(folder / "concept.json").get("label") or cid, out / "preview.png"
            else:
                label = _package_design(
                    logo, brief, cid, folder, work, out, source, compare_seed, calibrate, budget
                )
                png = out / "hero-transparent.png"
            sheet_entries.append((label, png))
        budget.check()
        columns = 2 if len(sheet_entries) == 4 else min(3, len(sheet_entries))
        _contact_sheet(sheet_entries, assets / "overview.png", columns=columns)
        manifest = {
            "schema": 1,
            "study_id": study_id,
            "kind": "preview" if preview else "3d-study",
            "concepts": {cid: concept_slug(cid) for cid, _ in designs},
            "files": _inventory(assets),
        }
        _write(assets / "manifest.json", manifest)
        if not preview:
            _zip(assets, staging / "study.zip")
            (staging / "study.zip").replace(assets / "study.zip")
        publish(
            [{"source": str(assets), "target": str(target), "move": True}],
            root / f".{study_id}-publication.json",
            budget,
            [],
        )
    return {
        "study_id": study_id,
        "directory": target,
        "overview": target / "overview.png",
        "manifest": target / "manifest.json",
        **({"archive": target / "study.zip"} if not preview else {}),
    }


def _verify_manifest(root: Path, study_id: str) -> tuple[dict, str]:
    manifest_file = root / "manifest.json"
    data = manifest_file.read_bytes()
    manifest = json.loads(data)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != 1
        or manifest.get("study_id") != study_id
        or manifest.get("kind") != "3d-study"
    ):
        raise ValueError("review requires a delivered 3D study")
    concepts, files = manifest.get("concepts"), manifest.get("files")
    if not isinstance(files, dict) or not isinstance(concepts, dict) or not concepts:
        raise ValueError("study manifest needs concepts and a file inventory")
    required = {"brief.toml", "overview.png"}
    for cid, slug in concepts.items():
        if not pipeline.is_concept_id(cid) or concept_slug(cid) != slug:
            raise ValueError("study manifest contains an invalid concept path")
        required.update(
            f"{slug}/{name}" for name in ("design.json", "hero-transparent.png", "mark-color.svg")
        )
    if not required.issubset(files):
        raise ValueError("study manifest is missing required review inputs")
    for name, record in manifest["files"].items():
        file = _safe(root, name)
        if (
            not isinstance(record, dict)
            or not file.is_file()
            or file.stat().st_size != record.get("bytes")
            or _sha256(file) != record.get("sha256")
        ):
            raise ValueError(f"study file changed: {file}")
    return manifest, sha256(data).hexdigest()


def _verify_archive(path: Path, manifest: dict, binding: str) -> str | None:
    if not path.exists():
        return None
    from zipfile import BadZipFile

    before = _sha256(path)
    files = manifest["files"]
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(files) + 1 or set(names) != {"manifest.json", *files}:
                raise ValueError("study ZIP contents differ from the manifest")
            if sha256(archive.read("manifest.json")).hexdigest() != binding:
                raise ValueError("study ZIP manifest changed")
            for name, evidence in files.items():
                if archive.getinfo(name).file_size != evidence["bytes"]:
                    raise ValueError(f"study ZIP entry changed: {name}")
                with archive.open(name) as entry:
                    digest = sha256()
                    for chunk in iter(lambda: entry.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != evidence["sha256"]:
                    raise ValueError(f"study ZIP entry changed: {name}")
    except BadZipFile as exc:
        raise ValueError(f"study ZIP is damaged: {path}") from exc
    if _sha256(path) != before:
        raise ValueError("study ZIP changed during verification")
    return before


def _brief_for_review(root: Path, folder: Path, design: dict, files: dict) -> Brief:
    import tomlkit

    from logo_maker.brief import Reference

    # The archived brief may name original-machine reference paths. The review
    # uses the copied files whose digests are in the study manifest.
    raw = tomlkit.parse((root / "brief.toml").read_text())
    raw.pop("references", None)
    brief = load(root / "brief.toml", content=tomlkit.dumps(raw).encode())
    refs = []
    for row in design["references"]:
        if row["state"] != "available" or row["use"] not in {"craft", "holdout"}:
            continue
        path = _safe(folder, row["path"])
        if files.get(path.relative_to(root).as_posix(), {}).get("sha256") != row["sha256"]:
            raise ValueError(f"photo is outside the study inventory: {path}")
        refs.append(Reference(path, "craft", row["note"]))
    intended = design["concept"].get("intended_appearance") or brief.intended_appearance
    return replace(brief, references=tuple(refs), intended_appearance=intended)


def _review_evidence(folder: Path, design: dict, files: dict, brief: Brief, dest: Path) -> dict:
    from PIL import ImageOps

    def verified(relative):
        path = _safe(folder, relative)
        if f"{folder.name}/{relative}" not in files:
            raise ValueError(f"review evidence is outside the study inventory: {path}")
        return path

    evidence = {"matches": {}}
    if note := design["concept"].get("identity_note"):
        evidence["identity"] = {"path": verified("identity.png"), "note": note}
    for row in design["references"]:
        if row["state"] != "available" or not (match := row.get("match")):
            continue
        view = verified(match["view"] + ".png")
        report = _read(verified(match["view"] + "-execution.json"))
        if report.get("status") != "verified" or report.get("png_sha256") != _sha256(view):
            raise ValueError(f"review view lacks matching render evidence: {view}")
        entry = {
            "feature": match["feature"],
            "view": match["view"],
            "view_sha256": _sha256(view),
            "regions": {},
            "intended_appearances": {
                "candidate": brief.intended_appearance,
                "reference": row["note"],
            },
        }
        for name, path, field in (
            ("candidate_detail", view, "render_region"),
            ("reference_detail", verified(row["path"]), "photo_region"),
        ):
            box = match.get(field, [0, 0, 1, 1])
            with Image.open(path) as original:
                im = ImageOps.exif_transpose(original).convert("RGBA")
                pixels = tuple(round(v * axis) for v, axis in zip(box, im.size * 2, strict=True))
                if pixels[0] >= pixels[2] or pixels[1] >= pixels[3]:
                    raise ValueError(f"review crop has no pixels: {path}")
                crop = im.crop(pixels)
                target = dest / f"{row['sha256']}-{name}.png"
                Image.alpha_composite(Image.new("RGBA", crop.size, "#EDECE8"), crop).convert(
                    "RGB"
                ).save(target)
            entry[name] = target
            entry["regions"][name] = {"normalized": box, "pixels": pixels}
        evidence["matches"][row["sha256"]] = entry
    return evidence


def review(
    logo: LogoDir,
    study_id: str,
    *,
    accepted: list[str] | None = None,
    owner_note: str = "",
    visual=True,
    budget: Budget | None = None,
) -> dict:
    """Run the unchanged visual rubric, or record owner acceptance of named designs."""
    import fcntl

    if not study_id.startswith(STUDY_ID) or concept_slug(study_id) != study_id:
        raise ValueError("use the study ID printed by logo-maker study")
    root = _safe(logo.root / "studies", study_id)
    if not (root / "manifest.json").is_file():
        raise ValueError(f"study {study_id} is missing its manifest")
    directory = logo.root / "qa" / "studies" / study_id
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".review.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"review is already running for {study_id}") from exc
        return _review(root, study_id, directory, accepted, owner_note, visual, budget or Budget())


def _review(root, study_id, directory, accepted, owner_note, visual, budget):
    from logo_maker.eligibility import compare_visual
    from logo_maker.jev import questions
    from logo_maker.jev.client import BudgetedJevClient, JevClient, JevError

    manifest, binding = _verify_manifest(root, study_id)
    archive = root / "study.zip"
    archive_hash = _verify_archive(archive, manifest, binding)
    concepts = manifest["concepts"]
    accepted = accepted or []
    if not visual and not accepted:
        raise ValueError("owner-only review requires at least one accepted concept")
    if owner_note and not accepted:
        raise ValueError("an owner note requires at least one accepted concept")
    if set(accepted) - concepts.keys():
        raise ValueError("owner acceptance must name concepts in this study")
    record_path = directory / "review.json"
    previous = _read(record_path) if record_path.exists() else {}
    from logo_maker import eligibility
    from logo_maker.jev import client as transport

    rubric = sha256(
        "".join(
            _sha256(Path(path))
            for path in (__file__, questions.__file__, eligibility.__file__, transport.__file__)
        ).encode()
    ).hexdigest()
    if previous.get("manifest_sha256", binding) != binding:
        raise ValueError("study manifest changed since review")
    if previous.get("archive_sha256") not in (None, archive_hash):
        raise ValueError("study ZIP changed since review")
    rows = deepcopy(previous.get("designs", {}))
    provider_error = None
    for cid, slug in concepts.items():
        folder = _safe(root, slug)
        design = _read(folder / "design.json")
        row = rows.setdefault(
            cid, {"visual": {"status": "pending"}, "owner": {"status": "pending"}}
        )
        row["reference_coverage"] = {
            role: sum(
                ref["use"] == role and ref["state"] == "available" for ref in design["references"]
            )
            for role in ("craft", "holdout", "research")
        }
        if cid in accepted:
            row["owner"] = {
                "status": "accepted",
                "note": owner_note,
                "hero_sha256": manifest["files"][f"{slug}/hero-transparent.png"]["sha256"],
            }
        if not visual:
            continue
        brief = _brief_for_review(root, folder, design, manifest["files"])
        if not brief.intended_appearance or not any(
            ref["state"] == "available" and ref["use"] == "craft" and ref["note"].strip()
            for ref in design["references"]
        ):
            row["visual"] = {
                "status": "missing_evidence",
                "message": "Supply intended appearance and a craft photo with a finish note.",
            }
            continue
        info = design["concept"]
        concept = questions.concept_state(
            brief,
            metaphor=info.get("metaphor_text", ""),
            treatment=info.get("treatment_text", ""),
            material=info.get("material_text", ""),
            treatment_id=info.get("treatment", ""),
            material_id=info.get("material", ""),
        )["concept"]
        concept["description"] = info.get("description", "")
        try:
            if provider_error is None:
                client = BudgetedJevClient(
                    JevClient(LogoDir(directory / slug), budget=budget), budget
                )
                judge = {"model": client.model, "endpoint": client.url}
                if (
                    row["visual"].get("rubric_sha256") == rubric
                    and row["visual"].get("judge") == judge
                    and row["visual"]["status"] in {"pass", "fail", "unsettled", "missing_evidence"}
                ):
                    continue
                flat_name = (
                    "favicon-32.png"
                    if f"{slug}/favicon-32.png" in manifest["files"]
                    else "mark-color.svg"
                )
                with TemporaryDirectory(prefix="logo-study-review-") as tmp:
                    evidence = _review_evidence(folder, design, manifest["files"], brief, Path(tmp))
                    result = compare_visual(
                        brief,
                        concept,
                        folder / "hero-transparent.png",
                        client,
                        label=f"{study_id}-{slug}",
                        flat_mark=folder / flat_name,
                        budget=budget,
                        study_evidence=evidence,
                    )
                hero_hash = manifest["files"][f"{slug}/hero-transparent.png"]["sha256"]
                flat_hash = manifest["files"][f"{slug}/{flat_name}"]["sha256"]
                if result["flat_source_sha256"] != flat_hash or any(
                    item["candidate_sha256"] != hero_hash for item in result["craft"]
                ):
                    raise ValueError("study images changed while Jev was reviewing them")
                photo_roles = {
                    ref["sha256"]: ref["use"]
                    for ref in design["references"]
                    if ref["state"] == "available"
                }
                for comparison in result["craft"]:
                    comparison["reference_role"] = photo_roles[comparison["reference_sha256"]]
                row["visual"] = {**result, "rubric_sha256": rubric, "judge": judge}
        except JevError as exc:
            provider_error = str(exc)
        if provider_error is not None:
            last = row["visual"]
            if last.get("status") == "pending":
                last = last.get("previous_review")
            row["visual"] = {"status": "pending", "provider_error": provider_error}
            if last and "rubric_sha256" in last:
                row["visual"]["previous_review"] = last
    _, current = _verify_manifest(root, study_id)
    if current != binding:
        raise ValueError("study manifest changed during review")
    if archive_hash is not None and _sha256(archive) != archive_hash:
        raise ValueError("study ZIP changed during review")
    record = {
        "study_id": study_id,
        "manifest_sha256": binding,
        "archive_sha256": archive_hash,
        "designs": rows,
    }
    if previous and previous != record:
        history = directory / "history"
        history.mkdir(exist_ok=True)
        snapshot = sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        host.run(
            {
                "operation": "write_json",
                "path": str(history / f"{snapshot}.json"),
                "data": previous,
            },
            budget,
            [],
        )
    host.run({"operation": "write_json", "path": str(record_path), "data": record}, budget, [])
    return {**record, "record": record_path}
