"""Persistent Codex branding work, with separate review and production outcomes."""

from __future__ import annotations

import fcntl
import json
import math
import platform
import threading
import time
from hashlib import sha256 as hash_bytes
from pathlib import Path

from PIL import Image, ImageOps

from logo_maker import pipeline, study, study_render
from logo_maker.paths import LogoDir
from logo_maker.sampling import Budget, SamplingLimit
from logo_maker.sampling_diagnostics import sha256

ACTIONS = (
    "init",
    "preflight",
    "status",
    "approve-brief",
    "approve-directions",
    "prototype",
    "select",
    "estimate",
    "preview",
    "flat-preview",
    "flat-accept",
    "flat-deliver",
    "render",
    "review",
    "diagnose",
    "evaluate",
    "references",
    "fetch-photo",
    "author",
    "check-construction",
    "repair",
    "compare-repair",
    "accept",
    "deliver",
    "qualify",
    "extend",
)
DEFAULT_LIMITS = {
    "wall_seconds": 14400,
    "renders": 64,
    "requests": 600,
    "repair_rounds": 3,
    "max_usd": None,
    "request_max_usd": None,
}
MEDIA = ("modeled", "flat", "typographic")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _read(path: Path) -> dict:
    row = json.loads(path.read_text())
    if not isinstance(row, dict):
        raise ValueError(f"expected an object: {path}")
    return row


def _needed(message: str, files=(), **details):
    raise pipeline.AuthoringNeeded(message, list(files), details=details)


def _brief_binding(logo: LogoDir) -> str:
    research = logo.root / "research.md"
    if not research.is_file() or not research.read_text().strip():
        _needed(
            "Research the brand before brainstorming and record the cited findings.", [research]
        )
    return study_render.digest({"brief": sha256(logo.brief), "research": sha256(research)})


def _source_binding(logo: LogoDir, folder: Path) -> str:
    names = (
        "source.blend",
        "scene.toml",
        "motif.svg",
        "motif.py",
        "mono.svg",
        "compact.svg",
        "compact-dark.svg",
        "construction.json",
        "concept.json",
        "references.json",
        "identity.png",
        "sampling-regions.json",
    )
    hashes = {n: sha256(folder / n) for n in names if (folder / n).is_file()}
    if (folder / "construction.json").exists():
        for name in _read(folder / "construction.json").get("sources", []):
            hashes[f"construction:{name}"] = sha256(study._safe(folder, name))
    if (folder / "references.json").exists():
        for row in _read(folder / "references.json").get("photos", []):
            name = row["path"]
            hashes[f"photo:{name}"] = sha256(study._safe(logo.root, name))
    return study_render.digest(hashes)


def _limits(row: dict) -> dict:
    if set(row) - DEFAULT_LIMITS.keys():
        raise ValueError("unknown campaign budget field")
    value = {**DEFAULT_LIMITS, **row}
    for name in ("wall_seconds", "renders", "requests", "repair_rounds"):
        v = value[name]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{name} must be positive and finite")
        if name != "wall_seconds" and type(v) is not int:
            raise ValueError(f"{name} must be an integer")
    for name in ("max_usd", "request_max_usd"):
        v = value[name]
        if v is not None and (
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0
        ):
            raise ValueError(f"{name} must be null or a nonnegative finite amount")
    return value


class CampaignBudget(Budget):
    """Reserve work durably before workers can spend it, including interrupted calls."""

    def __init__(self, path: Path, state: dict):
        self.path, self.state, self.lock = path, state, threading.Lock()
        self.progress: Path | None = None
        remaining = state["limits"]["wall_seconds"] - state["usage"]["wall_seconds"]
        if remaining <= 0:
            raise SamplingLimit("campaign time limit reached; approve an extension")
        super().__init__(remaining, attempt_limit=64)
        self.checkpoint = time.monotonic()
        state["active_lease"] = {"started": time.time(), "seconds": remaining}
        _write(path, state)

    def _save(self):
        now = time.monotonic()
        self.state["usage"]["wall_seconds"] += now - self.checkpoint
        self.checkpoint = now
        self.state["active_lease"] = {"started": time.time(), "seconds": self.remaining}
        _write(self.path, self.state)

    def begin_attempt(self) -> int:
        with self.lock:
            usage = self.state["usage"]
            if usage["renders"] >= self.state["limits"]["renders"]:
                raise SamplingLimit("campaign render limit reached; approve an extension")
            result = super().begin_attempt()
            usage["renders"] += 1
            self._save()
            return result

    def reserve_request(self, maximum_attempts: int) -> None:
        with self.lock:
            self.check()
            usage, limits = self.state["usage"], self.state["limits"]
            if usage["requests_reserved"] + maximum_attempts > limits["requests"]:
                raise SamplingLimit("campaign review request limit reached")
            upper = limits["request_max_usd"]
            if limits["max_usd"] is not None:
                if upper is None:
                    raise SamplingLimit(
                        "cash ceiling needs a documented conservative per-attempt price bound"
                    )
                if usage["reserved_usd"] + upper * maximum_attempts > limits["max_usd"]:
                    raise SamplingLimit("campaign cash reservation limit reached")
            usage["requests_reserved"] += maximum_attempts
            usage["reserved_usd"] += (upper or 0) * maximum_attempts
            usage["unpriced_requests"] += 1
            self._save()

    def record_usage(self, usage: dict) -> None:
        with self.lock:
            cost = usage.get("cost")
            if (
                isinstance(cost, (int, float))
                and not isinstance(cost, bool)
                and math.isfinite(cost)
                and cost >= 0
            ):
                self.state["usage"]["reported_usd"] += cost
                self.state["usage"]["unpriced_requests"] -= 1
            self._save()

    def close(self):
        with self.lock:
            self._save()
            self.state.pop("active_lease", None)
            _write(self.path, self.state)

    def render_progress(self, design: str, view: str, status: str, **details) -> None:
        if self.progress is None:
            return
        progress = _read(self.progress)
        if design in progress["designs"] and view in progress["designs"][design]:
            progress["designs"][design][view] = {"status": status, **details}
            _write(self.progress, progress)


def reference_coverage(logo: LogoDir, folder: Path, consumed: list[str]) -> dict:
    construction_file, references_file = folder / "construction.json", folder / "references.json"
    if not construction_file.is_file() or not references_file.is_file():
        _needed(
            "Author construction features and photographic reference coverage.",
            [construction_file, references_file],
        )
    construction = _read(construction_file)
    features = construction.get("critical_features", [])
    if (
        not isinstance(features, list)
        or not features
        or not all(isinstance(f, str) and f.strip() for f in features)
    ):
        raise ValueError("construction.json needs critical_features as a nonempty list of names")
    sources = construction.get("sources", [])
    if not (folder / "source.blend").is_file():
        _needed(
            "Save a self-contained packed source.blend for the selected design.",
            [folder / "source.blend"],
        )
    materials = construction.get("material_classes", [])
    if (
        not isinstance(materials, list)
        or not materials
        or not all(isinstance(m, str) and m.strip() for m in materials)
    ):
        raise ValueError("construction.json needs material_classes as a nonempty list")
    if (
        not isinstance(sources, list)
        or not sources
        or not all(isinstance(s, str) and study._safe(folder, s).is_file() for s in sources)
    ):
        _needed(
            "Retain the generator or documented build inputs in construction.sources.",
            [construction_file],
        )
    references = _read(references_file)
    rows = references.get("photos", [])
    if not isinstance(rows, list):
        raise ValueError("references.json needs photos as a list")
    captures, pixels, near, fingerprints = set(), set(), [], []
    covered = {feature: {"craft": [], "holdout": []} for feature in features}
    holdouts, problems, angles, lighting, development_sources, holdout_sources = (
        [],
        [],
        set(),
        set(),
        set(),
        set(),
    )
    for row in rows:
        required = ("capture_id", "capture_source", "angle", "lighting", "url", "coverage", "note")
        if not isinstance(row, dict) or not all(
            isinstance(row.get(k), str) and row[k].strip() for k in required
        ):
            problems.append(
                "each photo needs capture_id, capture_source, angle, lighting, URL, coverage and note"
            )
            continue
        path = study._safe(logo.root, row["path"])
        digest = sha256(path)
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            pixel_hash = study_render.digest(
                {"size": image.size, "pixels": hash_bytes(image.tobytes()).hexdigest()}
            )
            small = list(image.convert("L").resize((9, 8)).tobytes())
            fingerprint = sum(
                (small[y * 9 + x] > small[y * 9 + x + 1]) << (y * 8 + x)
                for y in range(8)
                for x in range(8)
            )
        if row["capture_id"] in captures or pixel_hash in pixels:
            problems.append(f"duplicate capture: {row['capture_id']}")
            continue
        for other, previous in fingerprints:
            if (fingerprint ^ previous).bit_count() <= 3:
                near.append([other, row["capture_id"]])
        fingerprints.append((row["capture_id"], fingerprint))
        captures.add(row["capture_id"])
        pixels.add(pixel_hash)
        angles.add(row["angle"].strip().casefold())
        lighting.add(row["lighting"].strip().casefold())
        role = row.get("use", "research")
        if role == "holdout":
            if digest in consumed or row["capture_id"] in consumed or pixel_hash in consumed:
                problems.append(f"replace consumed holdout: {row['capture_id']}")
            holdouts.extend((digest, row["capture_id"], pixel_hash))
            holdout_sources.add(row["capture_source"].strip().casefold())
        else:
            development_sources.add(row["capture_source"].strip().casefold())
        if role in {"craft", "holdout"}:
            if row.get("review_allowed") is not True:
                problems.append(f"record permission for provider review: {row['capture_id']}")
            if not row.get("match"):
                problems.append(f"match the photo to a verified view/crop: {row['capture_id']}")
            assignments = row.get("features", [])
            if (
                not isinstance(assignments, list)
                or len(assignments) != 1
                or not isinstance(assignments[0], str)
                or assignments[0] not in covered
            ):
                problems.append(
                    f"bind each review crop to one specific critical feature: {row['capture_id']}"
                )
                continue
            covered[assignments[0]][role].append(digest)
    if len(captures) < 40:
        problems.append(f"need 40 distinct captures; found {len(captures)}")
    if len(angles) < 2 or len(lighting) < 2:
        problems.append("include distinct camera angles and lighting conditions")
    if holdout_sources & development_sources:
        problems.append("use independent capture sources for holdouts and development")
    for feature, roles in covered.items():
        for role, hashes in roles.items():
            if not hashes:
                problems.append(f"{feature}: missing {role} coverage")
    if near and not references.get("distinct_capture_review"):
        problems.append("inspect near-duplicate pairs and record distinct_capture_review")
    if problems:
        _needed(
            "Complete reference coverage before rendering the final study.",
            [references_file],
            problems=problems,
            near_duplicates=near,
        )
    return {
        "captures": len(captures),
        "features": covered,
        "holdouts": holdouts,
        "near_duplicates": near,
    }


def _current(logo, state):
    if state.get("brief_approval", {}).get("binding") != _brief_binding(logo):
        _needed("Approve the current researched brief before proceeding.", [logo.brief])


def _modeled(state):
    if state.get("brief_approval", {}).get("medium", "modeled") != "modeled":
        _needed("Use the approved flat or typographic asset recipe for this brief.")


def _direction(logo, concepts, *, pitch=False):
    fields = ("label", "identity_note", "metaphor_text", "treatment_text", "material_text")
    directions = {}
    for cid in concepts:
        if not pipeline.is_concept_id(cid):
            raise ValueError(f"invalid concept ID: {cid}")
        path = study._safe(logo.root, f"concepts/{logo.concept_path(cid).name}/concept.json")
        if not path.is_file():
            _needed("Describe the direction before recording approval.", [path])
        info = _read(path)
        directions[cid] = {key: info.get(key) for key in fields}
        if pitch:
            description = info.get("pitch", info.get("description", ""))
            if not isinstance(description, str) or not description.strip():
                _needed("Write the proposed direction before requesting approval.", [path])
            directions[cid]["pitch"] = description.strip()
    return directions


def _selected_current(logo, state):
    selection = state.get("selection", {})
    if (
        selection.get("brief") != state["brief_approval"]["binding"]
        or selection.get("direction")
        != _direction(logo, state["selected"], pitch=state["schema"] >= 2)
        or (state["schema"] >= 2 and selection.get("medium") != state["brief_approval"]["medium"])
    ):
        _needed("Record owner selection of the current directions against the approved brief.")


def _directions_current(logo, state, concepts):
    if state["schema"] < 2:
        return
    approval = state.get("direction_approval", {})
    if (
        approval.get("brief") != state["brief_approval"]["binding"]
        or approval.get("medium") != state["brief_approval"]["medium"]
        or any(
            approval.get("directions", {}).get(cid) != direction
            for cid, direction in _direction(logo, concepts, pitch=True).items()
        )
    ):
        _needed("Approve the researched directions before modeling previews.")


def _estimate(logo, state, concepts):
    if not concepts or len(set(concepts)) != len(concepts):
        raise ValueError("name the proposed selected designs for an estimate")
    preview = state.get("preview")
    if not preview:
        _needed("Render previews before estimating production work.")
    directory = logo.root / "studies" / preview["study_id"]
    rounds = state["limits"]["repair_rounds"] + 1
    per_design = {}
    for cid in concepts:
        if cid not in preview["sources"]:
            _needed(f"Render a preview for {cid} before estimating it.")
        folder = logo.concept_path(cid)
        report = _read(directory / folder.name / "preview-execution.json")
        measured = report["seconds"]
        construction = folder / "construction.json"
        features = (
            len(_read(construction).get("critical_features", [])) if construction.exists() else 3
        )
        # Pixel scaling supplies a planning estimate. Adaptive stopping, setup and
        # diagnostic work can change actual timing considerably.
        per_design[cid] = {
            "preview_seconds": measured,
            "projected_seconds": rounds * (16 + len(study.VIEWS)) * measured,
            "renders": rounds * (1 + len(study.VIEWS)),
            "review_calls": rounds * (4 * max(1, features) + 3),
        }
    from logo_maker.jev.client import MAX_TRIES

    usage = state["usage"]
    return {
        "designs": per_design,
        "scope": "hero and four inspection views per revision, paired craft and holdout review",
        "recommendation": {
            **state["limits"],
            "wall_seconds": math.ceil(
                usage["wall_seconds"]
                + 1.5 * sum(r["projected_seconds"] for r in per_design.values())
                + 600
            ),
            "renders": usage["renders"] + sum(r["renders"] for r in per_design.values()) + 4,
            "requests": usage["requests_reserved"]
            + sum(r["review_calls"] for r in per_design.values()) * MAX_TRIES,
        },
    }


def _study_current(logo, state):
    _current(logo, state)
    _selected_current(logo, state)
    _directions_current(logo, state, state["selected"])
    item = state.get("latest")
    if not item or item.get("preview"):
        _needed("Render the selected designs first.")
    if item["sources"] != {
        cid: _source_binding(logo, logo.concept_path(cid)) for cid in state["selected"]
    }:
        _needed("Sources changed; render and review the new revision.")
    return item


def _note(note):
    if not note.strip():
        raise ValueError("record the owner's actual approval or explicit delegation in note")


def execute(
    logo: LogoDir,
    action: str,
    *,
    concepts: list[str] | None = None,
    note: str = "",
    record: dict | None = None,
) -> dict:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Codex 3D campaigns require Apple Silicon macOS")
    if action not in ACTIONS:
        raise ValueError("unknown campaign action")
    if action == "status":
        from contextlib import suppress

        with (logo.root / ".campaign.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                data = {"active": True, "render_progress": None}
                with suppress(FileNotFoundError):
                    data["render_progress"] = _read(logo.root / "render-progress.json")
                return data
            return _execute(logo, action, concepts or [], note, record or {})
    with (logo.root / ".campaign.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("a campaign action is already running in this logo folder") from exc
        return _execute(logo, action, concepts or [], note, record or {})


def _execute(logo, action, concepts, note, record):
    path = logo.root / "campaign.json"
    if action == "init" and not path.exists():
        state = {
            "schema": 2,
            "host": "codex",
            "selected": [],
            "limits": _limits(record),
            "usage": {
                "wall_seconds": 0,
                "renders": 0,
                "requests_reserved": 0,
                "reported_usd": 0,
                "reserved_usd": 0,
                "unpriced_requests": 0,
            },
            "repairs": {},
            "history": [],
            "consumed_holdouts": [],
        }
        _write(path, state)
    if not path.exists():
        _needed("Initialize the campaign first.", [path])
    state = _read(path)
    if lease := state.pop("active_lease", None):
        state["usage"]["wall_seconds"] += min(
            lease["seconds"], max(0, time.time() - lease["started"])
        )
        state["history"].append({"action": "recovered_interruption", "lease": lease})
        _write(path, state)
        progress_path = logo.root / "render-progress.json"
        if progress_path.is_file():
            progress = _read(progress_path)
            if progress["status"] == "rendering":
                progress["status"] = "incomplete"
                for views in progress["designs"].values():
                    for view in views.values():
                        if view["status"] == "rendering":
                            view["status"] = "interrupted"
                _write(progress_path, progress)
    if action in {"init", "status"}:
        progress = logo.root / "render-progress.json"
        return {
            **state,
            "path": str(path),
            "render_progress": _read(progress) if progress.is_file() else None,
            "next": "approve-brief"
            if not state.get("brief_approval")
            else "approve-directions"
            if state["schema"] >= 2 and not state.get("direction_approval")
            else "flat-preview/select/flat-accept/flat-deliver"
            if state["brief_approval"].get("medium") in ("flat", "typographic")
            else "preview/select/render/review/deliver",
        }
    if action == "estimate":
        _current(logo, state)
        return _estimate(logo, state, concepts)
    if action == "approve-brief":
        _note(note)
        medium = record.get("medium", "modeled")
        if medium not in MEDIA:
            raise ValueError("medium must be modeled, flat or typographic")
        state["brief_approval"] = {
            "binding": _brief_binding(logo),
            "note": note,
            "medium": medium,
        }
    elif action == "approve-directions":
        _current(logo, state)
        _note(note)
        if not concepts or len(set(concepts)) != len(concepts):
            raise ValueError("name each proposed direction once")
        directions = _direction(logo, concepts, pitch=True)
        state["direction_approval"] = {
            "brief": state["brief_approval"]["binding"],
            "directions": directions,
            "note": note,
            "medium": state["brief_approval"]["medium"],
        }
    elif action == "extend":
        _note(note)
        limits = _limits({**state["limits"], **record})
        for key in ("wall_seconds", "renders", "requests", "repair_rounds"):
            if limits[key] < state["limits"][key]:
                raise ValueError("extensions preserve previously authorized work")
        state["limits"] = limits
    elif action == "select":
        _current(logo, state)
        _note(note)
        study._designs(logo, concepts)
        _directions_current(logo, state, concepts)
        modeled = state["brief_approval"].get("medium", "modeled") == "modeled"
        preview = state.get("preview" if modeled else "flat_preview", {})
        archive = None
        if state["schema"] >= 2:
            if (
                preview.get("brief") != state["brief_approval"]["binding"]
                or any(
                    preview.get("directions", {}).get(cid) != direction
                    for cid, direction in _direction(logo, concepts, pitch=True).items()
                )
                or not set(concepts) <= preview.get("sources", {}).keys()
            ):
                _needed("Render previews of the approved directions before selecting artwork.")
            if modeled:
                directory = logo.root / "studies" / preview["study_id"]
                _, archive = study._verify_manifest(directory, preview["study_id"], kind="preview")
                if archive != preview.get("manifest_sha256"):
                    raise ValueError("the modeled preview differs from the verified revision")
            else:
                directory = Path(preview["directory"])
                manifest = _read(directory / "manifest.json")
                archive = study._verify_archive(
                    directory / "branding.zip", manifest, sha256(directory / "manifest.json")
                )
                if archive != preview["archive_sha256"]:
                    raise ValueError("the flat preview differs from the verified revision")
            if not archive:
                _needed("Restore the verified rendered previews before selecting artwork.")
        if record:
            state["limits"] = _limits(record)
        state["selected"] = concepts
        binding = {
            "note": note,
            "brief": state["brief_approval"]["binding"],
            "direction": _direction(logo, concepts, pitch=state["schema"] >= 2),
            "preview_study_id": preview.get("study_id"),
            "preview_archive_sha256": archive,
            "medium": state["brief_approval"].get("medium", "modeled"),
        }
        previous = state.get("selection", {})
        if (
            previous.get("direction") != binding["direction"]
            or previous.get("brief") != binding["brief"]
            or previous.get("preview_archive_sha256") != binding["preview_archive_sha256"]
        ):
            state.pop("latest", None)
        state["selection"] = binding
    elif action in {"flat-preview", "flat-accept", "flat-deliver"}:
        from logo_maker import campaign_flat

        _current(logo, state)
        if state["brief_approval"].get("medium", "modeled") == "modeled":
            _needed("Use the modeled campaign recipe for this approved brief.")
        if action == "flat-preview":
            from logo_maker.campaign_runtime import _policy

            _policy()
            _directions_current(logo, state, concepts)
            result = campaign_flat.preview(logo, concepts)
            state["flat_preview"] = {
                **result,
                "brief": state["brief_approval"]["binding"],
                "directions": _direction(logo, concepts, pitch=True),
            }
            _write(path, state)
            return result
        _selected_current(logo, state)
        preview = state.get("flat_preview", {})
        digest = state["selection"]["preview_archive_sha256"]
        if not preview or preview["archive_sha256"] != digest:
            _needed("Select the current verified flat preview.")
        if action == "flat-deliver":
            accepted = state.get("flat_acceptance", {})
            return campaign_flat.deliver(
                logo,
                state["selected"],
                preview,
                accepted.get("archive_sha256")
                if accepted.get("selected") == state["selected"]
                else None,
            )
        _note(note)
        if record.get("archive_sha256") != digest:
            _needed("Accept the exact verified flat archive.", archive_sha256=digest)
        state["flat_acceptance"] = {
            "archive_sha256": digest,
            "note": note,
            "selected": state["selected"],
        }
    elif action in {"repair", "compare-repair"}:
        _current(logo, state)
        item = state.get("latest")
        if not item or len(concepts) != 1 or concepts[0] not in state["selected"]:
            raise ValueError("repair needs one selected concept and a previous study")
        cid = concepts[0]
        repairs = state["repairs"].setdefault(cid, [])
        if action == "compare-repair":
            if (
                not repairs
                or repairs[-1]["before"] == item["sources"][cid]
                or (repairs[-1].get("after") and repairs[-1]["after"]["outcome"] != "inconclusive")
                or repairs[-1]["study_id"] == item["study_id"]
            ):
                raise ValueError("render a revision before recording its repair comparison")
            if record.get("outcome") not in (
                "improved",
                "unchanged",
                "worse",
                "inconclusive",
            ) or not record.get("observations"):
                raise ValueError("record the actual observed repair outcome and observations")
            new_comparison = {
                "study_id": item["study_id"],
                "outcome": record["outcome"],
                "observations": record["observations"],
            }
            if previous_comparison := repairs[-1].get("after"):
                if new_comparison == previous_comparison:
                    _needed("Supply new observations to resolve the previous comparison.")
                repairs[-1].setdefault("comparisons", []).append(previous_comparison)
            repairs[-1]["after"] = new_comparison
            _write(path, state)
            return {"action": action, "repair": repairs[-1]}
        for key in ("diagnosis", "evidence", "change", "comparison"):
            if not record.get(key):
                raise ValueError(f"repair record needs {key}")
        if repairs and not repairs[-1].get("after"):
            _needed("Record the comparison for the previous repair before starting another.")
        if repairs and repairs[-1]["after"]["outcome"] == "inconclusive":
            _needed(
                "Resolve the inconclusive comparison with better evidence before repairing again."
            )
        if len(repairs) >= state["limits"]["repair_rounds"]:
            _needed("Repair rounds exhausted; present remaining findings and request continuation.")
        if _source_binding(logo, logo.concept_path(cid)) != item["sources"][cid]:
            _needed("Start the repair from the retained revision before editing its files.")
        repairs.append({**record, "study_id": item["study_id"], "before": item["sources"][cid]})
        state["consumed_holdouts"] = sorted(
            set(
                state["consumed_holdouts"]
                + [f"{cid}:{entry}" for entry in item.get("holdouts", {}).get(cid, [])]
            )
        )
    elif action == "references":
        _current(logo, state)
        chosen = concepts or state["selected"]
        if not chosen:
            _needed("Name a design to check its photographic coverage.")
        return {
            cid: reference_coverage(
                logo,
                folder,
                [
                    entry.removeprefix(f"{cid}:")
                    for entry in state["consumed_holdouts"]
                    if entry.startswith(f"{cid}:")
                ],
            )
            for cid, folder in study._designs(logo, chosen)
        }
    elif action in {"fetch-photo", "author", "evaluate"}:
        from logo_maker.campaign_runtime import _policy

        _policy()
        budget = CampaignBudget(path, state)
        try:
            if action == "fetch-photo":
                from logo_maker.campaign_references import fetch

                result = fetch(logo, record, budget)
            elif action == "evaluate":
                from logo_maker.campaign_calibration import evaluate
                from logo_maker.jev.client import BudgetedJevClient, JevClient

                panel = study._safe(logo.root, record["panel"])
                client = BudgetedJevClient(JevClient(LogoDir(panel / "run"), budget=budget), budget)
                result = evaluate(
                    panel,
                    client,
                    rubric=study.review_rubric(True),
                    variant=record.get("variant", "baseline"),
                )
                target = panel / f"evaluation-{study_render.digest(result)[:16]}.json"
                _write(target, result)
                if result["partition"] == "held_out" and result["variant"] == "baseline":
                    state["evaluator"] = {
                        "panel": panel.relative_to(logo.root).as_posix(),
                        "result": target.name,
                        "sha256": sha256(target),
                    }
                result = {**result, "record": str(target)}
            else:
                import sys

                from logo_maker import owned_process

                script = study._safe(logo.root, record["script"])
                if script.suffix != ".py" or not script.is_file():
                    raise ValueError("author requires a Python generator inside the logo directory")
                args = record.get("args", [])
                if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                    raise ValueError("author arguments must be a list of strings")
                process = owned_process.run(
                    [
                        sys.executable,
                        "-m",
                        "logo_maker.campaign_runtime",
                        "--author",
                        str(script),
                        *args,
                    ],
                    cwd=logo.root,
                    budget=budget,
                    timeout=900,
                    label="sandboxed construction generator",
                )
                if process.returncode:
                    raise RuntimeError(process.stderr.strip() or process.stdout.strip())
                result = {"script": str(script), "output": process.stdout}
            state["history"].append({"action": action, "result": result})
            return result
        finally:
            budget.close()
    elif action == "check-construction":
        import sys

        from logo_maker import owned_process
        from logo_maker.campaign_runtime import _policy

        _policy()
        item = _study_current(logo, state)
        if len(concepts) != 1 or concepts[0] not in state["selected"]:
            raise ValueError("name one selected concept for construction checks")
        cid = concepts[0]
        directory = logo.root / "studies" / item["study_id"]
        manifest, binding = study._verify_manifest(directory, item["study_id"])
        slug = manifest["concepts"][cid]
        scene = directory / slug / "scene.blend"
        rays = record.get("rays")
        if not isinstance(rays, list) or not 1 <= len(rays) <= 128:
            raise ValueError(
                "provide between 1 and 128 construction ray checks in model coordinates"
            )
        budget = CampaignBudget(path, state)
        try:
            proc = owned_process.run(
                [sys.executable, "-m", "logo_maker.blender.construction"],
                input_text=json.dumps({"source": str(scene), "rays": rays}),
                budget=budget,
                timeout=120,
                label=f"construction checks for {cid}",
            )
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
            result = json.loads(proc.stdout.splitlines()[-1])
            if result["scene_sha256"] != manifest["files"][f"{slug}/scene.blend"]["sha256"]:
                raise ValueError("construction checks opened a different scene")
            target = logo.root / "qa" / "studies" / item["study_id"] / f"{slug}-construction.json"
            proof = {**result, "study_manifest_sha256": binding, "rays": rays}
            _write(target, proof)
            return {**proof, "record": str(target)}
        finally:
            budget.close()
    elif action in {
        "prototype",
        "preview",
        "render",
        "review",
        "diagnose",
        "accept",
        "deliver",
        "qualify",
    }:
        _current(logo, state)
        _modeled(state)
        from logo_maker.campaign_runtime import GPU_ACTIONS, JEV_ACTIONS, _policy

        if action in GPU_ACTIONS or action in JEV_ACTIONS:
            _policy()
        return _work(logo, path, state, action, concepts, note, record)
    state["history"].append({"action": action, "note": note, "record": record})
    _write(path, state)
    return {"action": action, "path": str(path), "selected": state["selected"]}


def _work(logo, path, state, action, concepts, note, record):
    if action in {"render", "preview", "prototype"}:
        chosen = state["selected"] if action == "render" else concepts
        if not chosen:
            _needed("Select the designs and their campaign budget before rendering.")
        if action == "render":
            _selected_current(logo, state)
        if action == "prototype":
            if (
                len(chosen) != 1
                or not isinstance(record.get("risk"), str)
                or not record["risk"].strip()
            ):
                raise ValueError(
                    "name one prototype and the construction or material risk it tests"
                )
        else:
            _directions_current(logo, state, chosen)
        for _, folder in study._designs(logo, chosen):
            pipeline.prepare_motif(folder)
        inspection_only = record.get("inspection_only") is True
        coverage = (
            {
                cid: reference_coverage(
                    logo,
                    logo.concept_path(cid),
                    [
                        entry.removeprefix(f"{cid}:")
                        for entry in state["consumed_holdouts"]
                        if entry.startswith(f"{cid}:")
                    ],
                )
                for cid in chosen
            }
            if action == "render" and not inspection_only
            else {}
        )
        bindings = {cid: _source_binding(logo, logo.concept_path(cid)) for cid in chosen}
        previous = state.get("latest", {})
        if action == "render" and previous and not previous.get("preview"):
            for cid in chosen:
                before = previous.get("sources", {}).get(cid)
                if before and before != bindings[cid]:
                    repairs = state["repairs"].get(cid, [])
                    if not repairs or repairs[-1]["study_id"] != previous["study_id"]:
                        _needed("Record the diagnosis and intended change before a repair render.")
        budget = CampaignBudget(path, state)
        try:
            environment = study_render.environment(budget)
            if (
                action == "render"
                and previous.get("sources") == bindings
                and previous.get("environment") == environment
                and previous.get("calibrate") == bool(record.get("calibrate"))
                and previous.get("inspection_only") == inspection_only
            ):
                study_id = previous["study_id"]
                directory = logo.root / "studies" / study_id
                manifest, binding = study._verify_manifest(directory, study_id)
                if study._verify_archive(directory / "study.zip", manifest, binding):
                    return {
                        "study_id": study_id,
                        "directory": directory,
                        "overview": directory / "overview.png",
                        "reused": True,
                    }
            budget.progress = logo.root / "render-progress.json"
            views = ("hero-transparent", *study.VIEWS) if action == "render" else ("preview",)
            _write(
                budget.progress,
                {
                    "status": "rendering",
                    "sources": bindings,
                    "designs": {
                        logo.concept_path(cid).name: {view: {"status": "pending"} for view in views}
                        for cid in chosen
                    },
                },
            )
            result = study.build(
                logo,
                chosen,
                preview=action != "render",
                budget=budget,
                render_options=environment,
                render_cache=logo.root / ".render-cache",
                calibrate=bool(record.get("calibrate")),
            )
            if bindings != {cid: _source_binding(logo, logo.concept_path(cid)) for cid in chosen}:
                raise ValueError(
                    "campaign sources changed while rendering; retained study is superseded"
                )
            item = {
                "study_id": result["study_id"],
                "manifest_sha256": sha256(result["manifest"]),
                "brief": state["brief_approval"]["binding"],
                "directions": _direction(
                    logo, chosen, pitch=state["schema"] >= 2 and action != "prototype"
                ),
                "sources": bindings,
                "environment": environment,
                "preview": action != "render",
                "inspection_only": inspection_only,
                "calibrate": bool(record.get("calibrate")),
                "holdouts": {cid: row["holdouts"] for cid, row in coverage.items()},
                "coverage": coverage,
            }
            if action == "prototype":
                item["risk"] = record["risk"]
                state.setdefault("prototypes", {})[chosen[0]] = item
            else:
                state["preview" if action == "preview" else "latest"] = item
            state["history"].append({"action": action, **item})
            progress = _read(budget.progress)
            _write(
                budget.progress,
                {
                    **progress,
                    "status": "verified",
                    "study_id": result["study_id"],
                    "overview": str(result["overview"]),
                },
            )
            return {
                **result,
                "qualification": "pending",
                "inspection_only": inspection_only,
                "budget": budget.record(),
            }
        except BaseException:
            if budget.progress and budget.progress.is_file():
                progress = _read(budget.progress)
                _write(budget.progress, {**progress, "status": "incomplete"})
            raise
        finally:
            budget.close()
    item = _study_current(logo, state)
    if action in {"review", "diagnose", "accept"}:
        if action == "accept":
            _note(note)
            if state["schema"] >= 2:
                directory = logo.root / "studies" / item["study_id"]
                manifest, binding = study._verify_manifest(directory, item["study_id"])
                archive = study._verify_archive(directory / "study.zip", manifest, binding)
                if (
                    record.get("study_id") != item["study_id"]
                    or not archive
                    or record.get("archive_sha256") != archive
                ):
                    _needed(
                        "Record acceptance against the exact verified study and archive digest.",
                        study_id=item["study_id"],
                        archive_sha256=archive,
                    )
        budget = CampaignBudget(path, state)
        try:
            result = study.review(
                logo,
                item["study_id"],
                visual=action != "accept",
                accepted=state["selected"] if action == "accept" else None,
                owner_note=note,
                budget=budget,
                matched_only=True,
                diagnostic=action == "diagnose",
            )
            state["history"].append({"action": action, "study_id": item["study_id"], "note": note})
            return result
        finally:
            budget.close()
    if action == "qualify":
        from logo_maker.campaign_qualification import prepare

        budget = CampaignBudget(path, state)
        try:
            return prepare(logo, state, item, record, note, budget)
        finally:
            budget.close()
    from logo_maker.campaign_delivery import deliver

    budget = CampaignBudget(path, state)
    try:
        return deliver(logo, state, item, record, budget)
    finally:
        budget.close()
