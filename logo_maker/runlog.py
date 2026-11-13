"""run.json: seeds, tool versions, stage status, jev usage, and asset licenses for one logo folder."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from contextlib import contextmanager
from importlib import metadata
from pathlib import Path
from typing import Any

from logo_maker.sampling import Budget, SamplingLimit

_LOCK = threading.Lock()
_OPEN: dict[Path, RunLog] = {}


@contextmanager
def _locked(budget: Budget | None = None):
    if budget is None:
        _LOCK.acquire()
    elif not _LOCK.acquire(timeout=budget.remaining):
        raise SamplingLimit("time_limit: runlog lock deadline exhausted")
    try:
        yield
    finally:
        _LOCK.release()


def runlog(path: Path, *, budget: Budget | None = None) -> RunLog:
    """The one RunLog per run.json in this process, so concurrent stages never clobber each other."""
    key = path.absolute() if budget else path.resolve()
    with _locked(budget):
        cached = _OPEN.get(key)
        # A log that already wrote its file but finds it gone (folder deleted or recreated, run.json
        # moved aside as the error text advises) must not resurrect that state.
        if cached is not None and cached._saved and not key.exists():
            cached = None
        if cached is None:
            _OPEN[key] = cached = RunLog(key, budget=budget)
        return cached


# (usage field, total, reported subtotal, requests missing that field) as jev_usage keeps them.
TELEMETRY_FIELDS = (
    ("cost", "cost_usd", "reported_cost_usd", "unpriced_requests"),
    ("input_tokens", "input_tokens", "reported_input_tokens", "uncounted_input_requests"),
    ("output_tokens", "output_tokens", "reported_output_tokens", "uncounted_output_requests"),
)
TELEMETRY_KEYS = tuple(key for _, _, *keys in TELEMETRY_FIELDS for key in keys)


def _load(path: Path) -> dict[str, Any]:
    fresh: dict[str, Any] = {
        "seeds": {},
        "stages": {},
        "jev": {"requests": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
        "assets": {},
        "versions": {},
        "events": [],
    }
    if not path.exists():
        return fresh
    try:
        data = json.loads(path.read_text())
        for key, value in fresh.items():
            if not isinstance(data.setdefault(key, value), type(value)):
                raise ValueError(f"{key} has the wrong type")
        for key, value in fresh["jev"].items():
            data["jev"].setdefault(key, value)
        for name, stage in data["stages"].items():
            if not isinstance(stage, dict) or not isinstance(stage.get("status", ""), str):
                raise ValueError(f"stages.{name} must be an object with a string status")
        for name, seed in data["seeds"].items():
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ValueError(f"seeds.{name} must be an integer")
        for key, default in fresh["jev"].items():
            value = data["jev"].setdefault(key, default)
            if value is None and key != "requests":
                continue  # jev_usage records an unknown total as null when telemetry is missing
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"jev.{key} must be a number")
        if "reported_cost_usd" in data["jev"]:  # the per-field telemetry jev_usage keeps
            for key in TELEMETRY_KEYS:
                value = data["jev"].get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"jev.{key} must be a number")
        entries = data["jev"].get("request_usage", {})
        if not isinstance(entries, dict) or not all(isinstance(e, dict) for e in entries.values()):
            raise ValueError("jev.request_usage must map request ids to objects")
    except (ValueError, AttributeError) as exc:  # truncated save, hand edit, not an object
        raise RuntimeError(
            f"{path} is not a valid run record ({exc}); move it aside to start a new one"
        ) from exc
    return data


class RunLog:
    """Append-safe view of run.json. Every write rewrites the file atomically under a process lock."""

    def __init__(self, path: Path, *, budget: Budget | None = None):
        self.path = path
        self._saved = path.exists()
        if budget is not None:
            from logo_maker import host

            self.data = host.run({"operation": "runlog_load", "path": str(path)}, budget, [])[
                "data"
            ]
            return
        self.data: dict[str, Any] = _load(path)

    def _save(self, budget: Budget | None = None) -> None:
        if budget is not None:
            from logo_maker import host

            host.run(
                {"operation": "write_json", "path": str(self.path), "data": self.data}, budget, []
            )
            self._saved = True
            return
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True))
        tmp.replace(self.path)
        self._saved = True

    def seed(self, name: str) -> int:
        """Stable seed per name: derived once from the folder and name, then read back from run.json."""
        with _LOCK:
            seeds = self.data["seeds"]
            if name not in seeds:
                digest = hashlib.sha256(f"{self.path.parent.name}:{name}".encode()).digest()
                seeds[name] = int.from_bytes(digest[:4], "big") % 2_000_000
                self._save()
            return seeds[name]

    def stage(self, name: str, status: str, *, budget: Budget | None = None, **detail: Any) -> None:
        with _locked(budget):
            self.data["stages"][name] = {
                "status": status,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                **detail,
            }
            self._save(budget)

    def stage_status(self, name: str) -> str | None:
        return self.data["stages"].get(name, {}).get("status")

    def publish_stage(
        self,
        name: str,
        entries: list[dict],
        journal: Path,
        budget: Budget,
        *,
        preconditions: list[dict] | None = None,
        **detail: Any,
    ) -> dict:
        """Commit completed stage bookkeeping with its output under one recovery journal."""
        from logo_maker.publication import publish

        with _locked(budget):
            data = copy.deepcopy(self.data)
            data["stages"][name] = {
                "status": "done",
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                **detail,
            }
            result = publish(
                [*entries, {"target": str(self.path), "text": json.dumps(data, indent=2)}],
                journal,
                budget,
                [],
                preconditions=preconditions,
            )
            self.data = data
            return result

    def jev_usage(
        self, usage: dict[str, Any], *, budget: Budget | None = None, request_id: str | None = None
    ) -> None:
        with _locked(budget):
            jev = self.data["jev"]
            fields = TELEMETRY_FIELDS
            if "reported_cost_usd" not in jev:
                # Old clients filled absent telemetry with zero/estimated prices. Preserve
                # the historical claims without asserting that those totals were complete.
                if jev["requests"]:
                    jev["legacy_usage"] = {
                        key: jev[key]
                        for key in ("requests", "cost_usd", "input_tokens", "output_tokens")
                    }
                for _, _, subtotal, missing in fields:
                    jev[subtotal] = 0
                    jev[missing] = jev["requests"]
            previous = None
            if request_id is not None:
                entries = jev.setdefault("request_usage", {})
                previous = entries.get(request_id)
                entries[request_id] = dict(usage)
            if previous is None:
                jev["requests"] += 1
            for field, total, subtotal, missing in fields:
                if previous is not None:
                    old = previous.get(field)
                    if old is None:
                        jev[missing] -= 1
                    else:
                        jev[subtotal] -= old
                value = usage.get(field)
                if value is None:
                    jev[missing] += 1
                else:
                    jev[subtotal] += value
                jev[total] = None if jev[missing] else jev[subtotal]
            self._save(budget)

    def asset(self, key: str, source: str, license: str, path: str) -> None:
        """Record a downloaded asset (font, HDRI, texture) and its license."""
        with _LOCK:
            self.data["assets"][key] = {"source": source, "license": license, "path": path}
            self._save()

    def event(self, text: str, *, budget: Budget | None = None, **detail: Any) -> None:
        with _locked(budget):
            self.data["events"].append(
                {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text, **detail}
            )
            self._save(budget)

    def record_versions(self) -> None:
        names = [
            "logo-maker",
            "bpy",
            "fonttools",
            "skia-pathops",
            "resvg-py",
            "pillow",
            "coloraide",
            "mitsuba",
            "pyluxcore",
            "manifold3d",
            "trimesh",
            "pymeshlab",
            "build123d",
            "vtracer",
        ]
        versions = {}
        for name in names:
            try:
                versions[name] = metadata.version(name)
            except metadata.PackageNotFoundError:
                versions[name] = None
        with _LOCK:
            self.data["versions"] = versions
            self._save()
