"""Prepare and verify owner-reviewed Metal sampling profiles for packed Blender scenes."""

from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from logo_maker import study, study_render
from logo_maker.campaign import _note, _read, _write
from logo_maker.sampling_diagnostics import sha256

ROLES = {
    "positive": "hero-transparent",
    "degraded": "degraded-threshold",
    "held_out": "hero-transparent",
    "held_out_control": "lower-threshold",
}
DECISIONS = {"positive": "accepted", "degraded": "rejected", "held_out": "accepted"}


def _review_packet(root: Path, directory: Path, profile: dict) -> Path:
    profile_sha = sha256(directory / "profile.json")
    target = root / f"review-{profile_sha[:16]}.zip"
    with TemporaryDirectory(prefix=".control-packet-", dir=root) as temporary:
        staging = Path(temporary) / "packet"
        shutil.copytree(directory, staging, ignore=shutil.ignore_patterns("approval.json"))
        _validate_results(staging, profile)
        if sha256(staging / "profile.json") != profile_sha:
            raise ValueError("profile changed while preparing the control packet")
        manifest = {"files": study._inventory(staging)}
        _write(staging / "manifest.json", manifest)
        archive = Path(temporary) / "packet.zip"
        study._zip(staging, archive)
        study._verify_archive(archive, manifest, sha256(staging / "manifest.json"))
        archive.replace(target)
    return target


def _scope(logo, item):
    return sorted(
        {
            material
            for cid in item["sources"]
            for material in _read(logo.concept_path(cid) / "construction.json")["material_classes"]
        }
    )


def _registry(logo) -> Path:
    from logo_maker.campaign_runtime import RUNTIME_DIR

    project = next(
        (parent for parent in (logo.root, *logo.root.parents) if (parent / RUNTIME_DIR).is_dir()),
        logo.root,
    )
    return project / ".logo-maker-work" / "sampling-profiles"


def _register(logo, directory: Path, profile: dict, approval: dict) -> None:
    root = _registry(logo)
    root.mkdir(parents=True, exist_ok=True)
    target = root / approval["profile_sha256"]
    if target.exists():
        return
    with TemporaryDirectory(prefix=".profile-", dir=root) as temporary:
        staging = Path(temporary) / "profile"
        shutil.copytree(directory, staging)
        _validate_results(staging, profile)
        if sha256(staging / "profile.json") != approval["profile_sha256"]:
            raise ValueError("profile changed before registration")
        with suppress(FileExistsError):
            staging.rename(target)


def _validate_results(directory: Path, profile: dict) -> None:
    manifest = profile["files"]
    inventory = study._inventory(directory)
    for metadata in ("profile.json", "approval.json"):
        inventory.pop(metadata, None)
    if inventory != manifest:
        raise ValueError("qualification evidence changed")
    for role, name in ROLES.items():
        item = directory / role
        report = _read(item / f"{name}-execution.json")
        if (
            not study_render.verified_execution(report, name)
            or report["png_sha256"] != sha256(item / f"{name}.png")
            or report["log_sha256"] != sha256(item / f"{name}-execution.log")
            or report["scene_inventory"]["contract"] != "packed-static-v1"
            or report["inputs_sha256"]["source"] != profile["source_sha256"][role]
        ):
            raise ValueError(f"qualification control failed verification: {role}")


def prepare(logo, state, item, record, note, budget):
    """Prepare controls on two different scenes, or record the review of those exact bytes."""
    root = logo.root / "sampling-qualification"
    if not record and not note:
        environment = study_render.environment(budget)
        if status(logo, state, item, environment) == "qualified":
            directory = root / state["sampling_approval"]["qualification_id"]
            return {"qualification": "qualified", "profile": directory / "profile.json"}
        registry = _registry(logo)
        for path in sorted(registry.glob("*/profile.json")):
            try:
                profile = _read(path)
                if profile["environment"] != environment or not set(_scope(logo, item)) <= set(
                    profile["material_classes"]
                ):
                    continue
                return prepare(logo, state, item, {"approved_profile": str(path)}, "", budget)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return {
            "qualification": "controls_needed",
            "material_classes": _scope(logo, item),
            "required": ["candidate", "holdout"],
        }
    if record.get("approved_profile"):
        packet = Path(record["approved_profile"]).expanduser().resolve().parent
        profile = _read(packet / "profile.json")
        approval = _read(packet / "approval.json")
        _validate_results(packet, profile)
        if approval["decisions"] != DECISIONS or approval["profile_sha256"] != sha256(
            packet / "profile.json"
        ):
            raise ValueError(
                "import requires an owner-approved profile and its exact control packet"
            )
        _note(approval["note"])
        environment = study_render.environment(budget)
        if profile["environment"] != environment or (
            not set(_scope(logo, item)) <= set(profile["material_classes"])
        ):
            raise ValueError("approved profile does not cover this runtime and material scope")
        root.mkdir(exist_ok=True)
        target = root / ("packed-" + approval["profile_sha256"][:16])
        if not target.exists():
            with TemporaryDirectory(prefix=".qualification-", dir=root) as temporary:
                staging = Path(temporary) / target.name
                shutil.copytree(packet, staging)
                _validate_results(staging, profile)
                budget.check()
                staging.rename(target)
        state["sampling_approval"] = {"qualification_id": target.name, **approval}
        return {
            "qualification": status(logo, state, item, environment),
            "profile": target / "profile.json",
        }
    if note:
        _note(note)
        directory = study._safe(root, record["qualification_id"])
        profile = _read(directory / "profile.json")
        _validate_results(directory, profile)
        if record.get("profile_sha256") != sha256(directory / "profile.json"):
            raise ValueError("record the hash of the reviewed control packet")
        labels = record.get("decisions")
        if labels != DECISIONS:
            raise ValueError(
                "qualification requires accepted positives and held-out images and a rejected control"
            )
        approval = {"decisions": labels, "profile_sha256": record["profile_sha256"], "note": note}
        _write(directory / "approval.json", approval)
        state["sampling_approval"] = {"qualification_id": directory.name, **approval}
        environment = study_render.environment(budget)
        result = status(logo, state, item, environment)
        if result == "qualified":
            _register(logo, directory, profile, approval)
        return {"qualification": result, "profile": directory / "profile.json"}
    candidate = record.get("candidate")
    holdout = record.get("holdout")
    if not isinstance(candidate, str) or not isinstance(holdout, str):
        raise ValueError("provide a production-like candidate and an independent authored holdout")
    study._designs(logo, [candidate, holdout])
    candidate_source = logo.concept_path(candidate) / "source.blend"
    holdout_source = logo.concept_path(holdout) / "source.blend"
    sources = {
        "positive": candidate_source,
        "degraded": candidate_source,
        "held_out": holdout_source,
        "held_out_control": holdout_source,
    }
    source_hashes = {role: sha256(file) for role, file in sources.items()}
    if source_hashes["positive"] == source_hashes["held_out"]:
        raise ValueError("holdout must use a different scene")
    scope = _scope(logo, item)
    holdout_classes = _read(holdout_source.parent / "construction.json")["material_classes"]
    candidate_classes = _read(candidate_source.parent / "construction.json")["material_classes"]
    if set(scope) - (set(holdout_classes) & set(candidate_classes)):
        raise ValueError(
            "positive and independent holdout scenes must each exercise all claimed material classes"
        )
    environment = study_render.environment(budget)
    binding = {
        "environment": environment,
        "material_classes": scope,
        "source_sha256": source_hashes,
    }
    target = root / ("packed-" + study_render.digest(binding)[:16])
    root.mkdir(exist_ok=True)
    if not target.exists():
        with TemporaryDirectory(prefix=".qualification-", dir=root) as temporary:
            staging = Path(temporary)
            images = []
            for role, view in ROLES.items():
                directory = staging / role
                directory.mkdir()
                snapshot = directory / "input.blend"
                shutil.copyfile(sources[role], snapshot)
                if sha256(snapshot) != source_hashes[role]:
                    raise ValueError("qualification scene changed before rendering")
                study_render.render(
                    snapshot,
                    False,
                    directory,
                    view,
                    budget,
                    options=environment,
                    cache=logo.root / ".render-cache",
                )
                images.append((role, directory / f"{view}.png"))
            study._contact_sheet(images, staging / "comparison.png", columns=2)
            comparisons = {}
            for name, left, right in (("degraded", 0, 1), ("held_out", 2, 3)):
                first, second = images[left][1], images[right][1]
                comparisons[name] = study._seed_check(first, second, candidate_source.parent)
            _write(staging / "comparison.json", comparisons)
            _write(
                staging / "profile.json",
                {
                    "schema": 1,
                    "contract": "packed-static-v1",
                    **binding,
                    "controls": study_render.CONTROLS,
                    "files": study._inventory(staging),
                },
            )
            budget.check()
            staging.rename(target)
    profile = _read(target / "profile.json")
    _validate_results(target, profile)
    return {
        "qualification": "owner_review_needed",
        "qualification_id": target.name,
        "comparison": target / "comparison.png",
        "profile": target / "profile.json",
        "profile_sha256": sha256(target / "profile.json"),
        "review_packet": _review_packet(root, target, profile),
    }


def status(logo, state, item, environment):
    approval = state.get("sampling_approval")
    if not approval:
        return "pending"
    directory = study._safe(logo.root / "sampling-qualification", approval["qualification_id"])
    try:
        profile_path = directory / "profile.json"
        profile = _read(profile_path)
        if approval["profile_sha256"] != sha256(profile_path) or approval["decisions"] != DECISIONS:
            return "stale"
        _validate_results(directory, profile)
    except (ValueError, OSError, KeyError, TypeError):
        return "stale"
    if (
        profile["environment"] != environment
        or item["environment"] != environment
        or profile["controls"] != study_render.CONTROLS
        or not set(_scope(logo, item)) <= set(profile["material_classes"])
    ):
        return "out_of_scope"
    return "qualified"
