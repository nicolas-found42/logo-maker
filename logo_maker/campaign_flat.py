"""Versioned flat and typographic campaign previews and handoffs."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from logo_maker import pipeline, study, study_render
from logo_maker.brief import load
from logo_maker.campaign import _read, _write
from logo_maker.sampling_diagnostics import sha256


def preview(logo, concepts: list[str]) -> dict:
    designs = study._designs(logo, concepts)
    identity = {}
    for cid, folder in designs:
        pipeline.prepare_motif(folder)
        identity[cid] = {
            name: sha256(folder / name)
            for name in ("motif.svg", "mono.svg", "compact.svg", "compact-dark.svg")
            if (folder / name).is_file()
        }
    revision = study_render.digest(
        {
            "sources": identity,
            "brief": sha256(logo.brief),
            "code": study_render.code_identity(),
        }
    )
    target = logo.exports / f"flat-{revision[:16]}"
    if not target.exists():
        with TemporaryDirectory(prefix=".flat-campaign-", dir=logo.exports) as temporary:
            scratch = Path(temporary)
            output = scratch / "output"
            output.mkdir()
            images = []
            brief = load(logo.brief)
            for cid, folder in designs:
                dest = output / folder.name
                dest.mkdir()
                work = scratch / folder.name
                work.mkdir()
                for name, digest in identity[cid].items():
                    target_input = work / name
                    target_input.write_bytes((folder / name).read_bytes())
                    if sha256(target_input) != digest:
                        raise ValueError(f"flat source changed during packaging: {cid}/{name}")
                paths = study._flat(work, work, dest, brief)
                study._compact_sheet(paths, dest / "compact-light-dark.png")
                images.append((folder.name, paths["mark-color"]))
            study._contact_sheet(images, output / "overview.png")
            _write(output / "manifest.json", {"files": study._inventory(output)})
            archive = scratch / "branding.zip"
            study._zip(output, archive)
            archive.rename(output / archive.name)
            output.rename(target)
    manifest = _read(target / "manifest.json")
    archive = target / "branding.zip"
    binding = study._verify_archive(archive, manifest, sha256(target / "manifest.json"))
    if not binding:
        raise ValueError("flat campaign archive is missing")
    return {
        "revision": revision,
        "directory": str(target),
        "archive": str(archive),
        "archive_sha256": binding,
        "overview": str(target / "overview.png"),
        "concepts": concepts,
        "sources": identity,
    }


def deliver(logo, selection, artwork, approval) -> dict:
    source = Path(artwork["directory"])
    manifest = _read(source / "manifest.json")
    digest = study._verify_archive(
        source / "branding.zip", manifest, sha256(source / "manifest.json")
    )
    if digest != artwork["archive_sha256"]:
        raise ValueError("the selected flat preview changed")
    selected = {logo.concept_path(cid).name for cid in selection}
    report = {
        "status": "qualified" if approval == digest else "review_needed",
        "revision": artwork["revision"],
        "selected": selection,
        "reviewed_preview_sha256": digest,
        "technical": "verified",
        "owner": "accepted" if approval == digest else "pending",
    }
    target = logo.exports / ("flat-delivery-" + study_render.digest(report)[:16])
    if not target.exists():
        from shutil import copyfile

        with TemporaryDirectory(prefix=".flat-delivery-", dir=logo.exports) as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            included = [name for name in manifest["files"] if name.split("/")[0] in selected]
            for name in included:
                dst = study._safe(output, name)
                dst.parent.mkdir(parents=True, exist_ok=True)
                copyfile(study._safe(source, name), dst)
                if sha256(dst) != manifest["files"][name]["sha256"]:
                    raise ValueError(f"flat artwork changed: {name}")
            study._contact_sheet(
                [(slug, output / slug / "mark-color.svg") for slug in sorted(selected)],
                output / "overview.png",
            )
            _write(output / "qualification.json", report)
            _write(output / "manifest.json", {"files": study._inventory(output)})
            archive = Path(temporary) / "branding.zip"
            study._zip(output, archive)
            archive.rename(output / archive.name)
            output.rename(target)
    manifest = _read(target / "manifest.json")
    archive = target / "branding.zip"
    return {
        **report,
        "overview": str(target / "overview.png"),
        "shareable": str(archive),
        "archive_sha256": study._verify_archive(
            archive, manifest, sha256(target / "manifest.json")
        ),
    }
