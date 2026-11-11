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
        if key not in _OPEN:
            _OPEN[key] = RunLog(key, budget=budget)
        return _OPEN[key]


class RunLog:
    """Append-safe view of run.json. Every write rewrites the file atomically under a process lock."""

    def __init__(self, path: Path, *, budget: Budget | None = None):
        self.path = path
        if budget is not None:
            from logo_maker import host

            self.data = host.run({"operation": "runlog_load", "path": str(path)}, budget, [])[
                "data"
            ]
            return
        self.data: dict[str, Any] = (
            json.loads(path.read_text())
            if path.exists()
            else {
                "seeds": {},
                "stages": {},
                "jev": {"requests": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0},
                "assets": {},
                "versions": {},
                "events": [],
            }
        )

    def _save(self, budget: Budget | None = None) -> None:
        if budget is not None:
            from logo_maker import host

            host.run(
                {"operation": "write_json", "path": str(self.path), "data": self.data}, budget, []
            )
            return
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True))
        tmp.replace(self.path)

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
        self, name: str, entries: list[dict], journal: Path, budget: Budget, **detail: Any
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
            )
            self.data = data
            return result

    def jev_usage(self, usage: dict[str, Any], *, budget: Budget | None = None) -> None:
        with _locked(budget):
            jev = self.data["jev"]
            jev["requests"] += 1
            jev["cost_usd"] = round(jev["cost_usd"] + float(usage.get("cost", 0.0) or 0.0), 6)
            jev["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
            jev["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
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
