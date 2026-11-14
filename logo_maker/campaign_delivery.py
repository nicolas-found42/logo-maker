"""Build separate shareable and private archives from a verified campaign revision."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from logo_maker import (
    campaign_calibration,
    campaign_qualification,
    owned_process,
    study,
    study_render,
)
from logo_maker.campaign import _read, _source_binding, _write
from logo_maker.sampling_diagnostics import sha256


def _copy_bound(source: Path, target: Path, digest: str) -> None:
    shutil.copyfile(source, target)
    if sha256(target) != digest:
        raise ValueError(f"delivery asset changed: {source.name}")


ASSETS = (
    "hero-transparent.png",
    "scene.blend",
    "mark-color.svg",
    "mark-mono.svg",
    "mark-compact.svg",
    "mark-flat-256.png",
    "mark-flat-1024.png",
    "favicon.ico",
    "favicon-16.png",
    "favicon-32.png",
    "favicon-48.png",
    "favicon-180.png",
    "favicon-512.png",
    "compact-light-dark.png",
    "contact-sheet.png",
    "inspection-views.png",
    *(f"{view}.png" for view in study.VIEWS),
)


def _verify_delivery(directory, report, manifest, root, budget):
    """Check exact members and reopen each packed scene from archive bytes."""
    archive = directory / "branding.zip"
    with ZipFile(archive) as share:
        contents = share.read("manifest.json")
        inventory = json.loads(contents)
        with TemporaryDirectory(prefix=".delivery-reopen-", dir=directory.parent) as temporary:
            checked = {}
            for cid, slug in manifest["concepts"].items():
                for name in ASSETS:
                    member = f"{slug}/{name}"
                    if inventory["files"][member] != manifest["files"][member]:
                        raise ValueError(f"delivery member differs from reviewed artwork: {member}")
                scene = Path(temporary) / "scene.blend"
                with share.open(f"{slug}/scene.blend") as src, scene.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                if sha256(scene) != manifest["files"][f"{slug}/scene.blend"]["sha256"]:
                    raise ValueError(f"delivery scene differs from reviewed artwork: {cid}")
                result = owned_process.run(
                    [sys.executable, "-m", "logo_maker.blender.study"],
                    input_text=json.dumps(
                        {"operation": "inspect_packed_scene", "source": str(scene)}
                    ),
                    budget=budget,
                    timeout=120,
                    label=f"reopen packaged scene {cid}",
                )
                if result.returncode:
                    raise ValueError(f"cannot reopen {cid}: {result.stderr or result.stdout}")
                checked[cid] = json.loads(result.stdout.splitlines()[-1])
    study._verify_archive(archive, inventory, study_render.sha256(contents).hexdigest())
    with ZipFile(directory / "evidence.zip") as private:
        contents = private.read("manifest.json")
        inventory = json.loads(contents)
        handoff = json.loads(private.read("handoff.json"))
        if handoff["branding.zip"] != sha256(archive) or (
            inventory["files"]["study.zip"]["sha256"] != report["study_sha256"]
        ):
            raise ValueError("private evidence differs from the reviewed handoff")
        if report["review_sha256"] and (
            inventory["files"]["review/review.json"]["sha256"] != report["review_sha256"]
        ):
            raise ValueError("private evidence differs from the review")
    study._verify_archive(
        directory / "evidence.zip", inventory, study_render.sha256(contents).hexdigest()
    )
    if (
        study._verify_archive(root / "study.zip", manifest, sha256(root / "manifest.json"))
        != (report["study_sha256"])
    ):
        raise ValueError("the underlying study changed during verification")
    return checked


def deliver(logo, state, item, record, budget):
    study_id = item["study_id"]
    root = logo.root / "studies" / study_id
    manifest, binding = study._verify_manifest(root, study_id)
    archive_hash = study._verify_archive(root / "study.zip", manifest, binding)
    if not archive_hash or set(manifest["concepts"]) != set(state["selected"]):
        raise ValueError("delivery needs the verified archive for all selected designs")
    qa = logo.root / "qa" / "studies" / study_id
    review_path = qa / "review.json"
    review = _read(review_path) if review_path.is_file() else {}
    if review and (
        review["manifest_sha256"] != binding or review["archive_sha256"] != archive_hash
    ):
        raise ValueError("the review belongs to different artwork")
    environment = study_render.environment(budget)
    sampling = campaign_qualification.status(logo, state, item, environment)
    evaluator = campaign_calibration.qualification(logo, state)
    outcomes = {}
    for cid, slug in manifest["concepts"].items():
        folder = root / slug
        for view in ("hero-transparent", *study.VIEWS):
            report = _read(folder / f"{view}-execution.json")
            if not study_render.verified_execution(report, view):
                raise ValueError(f"unverified execution in {cid}/{view}")
        hero_report = _read(folder / "hero-transparent-execution.json")
        if (
            hero_report["inputs_sha256"]["editable_scene"] != sha256(folder / "scene.blend")
            or hero_report["scene_inventory"]["contract"] != "packed-static-v1"
        ):
            raise ValueError(f"scene differs from the verified render: {cid}")
        row = review.get("designs", {}).get(cid, {})
        visual = row.get("visual", {})
        if evaluator == "qualified":
            calibration = state["evaluator"]
            evaluator_path = study._safe(
                logo.root, f"{calibration['panel']}/{calibration['result']}"
            )
            if visual.get("judge") != _read(evaluator_path)["judge"]:
                evaluator = "out_of_scope"
        expected_craft = {
            (role, image)
            for feature in item.get("coverage", {}).get(cid, {}).get("features", {}).values()
            for role, images in feature.items()
            for image in images
        }
        observed_craft = {
            (pair.get("reference_role"), pair.get("reference_sha256"))
            for pair in visual.get("craft", [])
            if pair.get("status") == "pass"
        }
        owner = row.get("owner", {})
        local = study._local_checks(folder / "hero-transparent.png")
        repairs = state["repairs"].get(cid, [])
        outcomes[cid] = {
            "technical": "review_needed"
            if local["alpha"]["veil"] or local["margin"]["cut_off"] or local["edges"]["aliased"]
            else "verified",
            "visual": visual.get("status", "pending")
            if visual.get("rubric_sha256") == study.review_rubric(True)
            else "pending",
            "craft_coverage": "verified"
            if expected_craft and expected_craft <= observed_craft
            else "incomplete",
            "repair": (
                repairs[-1].get("after", {}).get("outcome", "pending") if repairs else "none"
            ),
            "owner": "accepted"
            if owner.get("hero_sha256") == sha256(folder / "hero-transparent.png")
            and owner.get("status") == "accepted"
            else "pending",
        }
    qualified = (
        not item.get("inspection_only")
        and sampling == "qualified"
        and evaluator == "qualified"
        and all(
            row["technical"] == "verified"
            and row["craft_coverage"] == "verified"
            and row["visual"] == "pass"
            and row["owner"] == "accepted"
            and row["repair"] in ("none", "improved")
            for row in outcomes.values()
        )
    )
    status = "qualified" if qualified else "review_needed"
    guidance = record.get("usage_guidance", "")
    if qualified and not (isinstance(guidance, str) and guidance.strip()):
        raise ValueError("provide the approved usage guidance for the asset family")
    report = {
        "schema": 2,
        "status": status,
        "sampling": sampling,
        "evaluator": evaluator,
        "reference_coverage": "incomplete" if item.get("inspection_only") else "verified",
        "designs": outcomes,
        "study_id": study_id,
        "study_sha256": archive_hash,
        "review_sha256": sha256(review_path) if review_path.is_file() else None,
        "usage_guidance": guidance,
    }
    target = logo.exports / (status.replace("_", "-") + "-" + study_render.digest(report)[:16])
    if target.exists():
        existing = _read(target / "receipt.json")
        if any(sha256(target / name) != digest for name, digest in existing["archives"].items()):
            raise ValueError("an existing delivery archive has changed")
        if record.get("verify"):
            _verify_delivery(target, report, manifest, root, budget)
        return {
            **existing,
            "directory": target,
            "shareable": target / "branding.zip",
            "private": target / "evidence.zip",
        }
    with TemporaryDirectory(prefix=".campaign-delivery-", dir=logo.exports) as temporary:
        staging = Path(temporary)
        share, private, output = (staging / name for name in ("share", "private", "delivery"))
        for folder in (share, private, output):
            folder.mkdir()
        _copy_bound(
            root / "overview.png",
            share / "overview.png",
            manifest["files"]["overview.png"]["sha256"],
        )
        for cid, slug in manifest["concepts"].items():
            budget.check()
            dest = share / slug
            dest.mkdir()
            for name in ASSETS:
                before = manifest["files"][f"{slug}/{name}"]["sha256"]
                _copy_bound(root / slug / name, dest / name, before)
            for name in (
                "mark-compact-dark.svg",
                "favicon-dark.ico",
                "favicon-dark-16.png",
                "favicon-dark-32.png",
                "favicon-dark-48.png",
                "favicon-dark-180.png",
                "favicon-dark-512.png",
            ):
                if f"{slug}/{name}" in manifest["files"]:
                    _copy_bound(
                        root / slug / name,
                        dest / name,
                        manifest["files"][f"{slug}/{name}"]["sha256"],
                    )
            folder = logo.concept_path(cid)
            construction = _read(folder / "construction.json")
            for name in construction["sources"]:
                source = study._safe(folder, name)
                out = study._safe(dest / "construction", name)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, out)
            if _source_binding(logo, folder) != item["sources"][cid]:
                raise ValueError(f"construction changed during delivery: {cid}")
        (share / "USAGE.md").write_text(
            guidance.strip() + "\n"
            if guidance
            else "Use the transparent hero for large placements and the compact mark at icon sizes.\n"
            "Open scene.blend to edit the object. See qualification.json for review status.\n"
        )
        _write(
            share / "qualification.json", {k: v for k, v in report.items() if k != "usage_guidance"}
        )
        _write(share / "manifest.json", {"files": study._inventory(share)})
        shutil.copyfile(root / "study.zip", private / "study.zip")
        if sha256(private / "study.zip") != archive_hash:
            raise ValueError("the private study archive changed")
        shutil.copyfile(logo.root / "research.md", private / "research.md")
        shutil.copyfile(logo.root / "campaign.json", private / "campaign.json")
        if qa.exists():
            shutil.copytree(qa, private / "review", ignore=shutil.ignore_patterns("*.lock"))
            if (
                report["review_sha256"]
                and sha256(private / "review" / "review.json") != report["review_sha256"]
            ):
                raise ValueError("review changed during delivery")
        if approval := state.get("sampling_approval"):
            profile = study._safe(
                logo.root / "sampling-qualification", approval["qualification_id"]
            )
            shutil.copytree(profile, private / "sampling", dirs_exist_ok=True)
        budget.check()
        study._zip(share, output / "branding.zip")
        archive_hashes = {"branding.zip": sha256(output / "branding.zip")}
        _write(private / "handoff.json", {**report, **archive_hashes})
        _write(private / "manifest.json", {"files": study._inventory(private)})
        study._zip(private, output / "evidence.zip")
        archive_hashes["evidence.zip"] = sha256(output / "evidence.zip")
        reopened = _verify_delivery(output, report, manifest, root, budget)
        receipt = {**report, "archives": archive_hashes, "reopened": reopened}
        _write(output / "receipt.json", receipt)
        budget.check()
        output.rename(target)
    return {
        **receipt,
        "directory": target,
        "shareable": target / "branding.zip",
        "private": target / "evidence.zip",
    }
