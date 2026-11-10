"""run.json: seeds, tool versions, stage status, jev usage, and asset licenses for one logo folder."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from importlib import metadata
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_OPEN: dict[Path, RunLog] = {}


def runlog(path: Path) -> RunLog:
    """The one RunLog per run.json in this process, so concurrent stages never clobber each other."""
    key = path.resolve()
    with _LOCK:
        if key not in _OPEN:
            _OPEN[key] = RunLog(key)
        return _OPEN[key]


class RunLog:
    """Append-safe view of run.json. Every write rewrites the file atomically under a process lock."""

    def __init__(self, path: Path):
        self.path = path
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

    def _save(self) -> None:
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

    def stage(self, name: str, status: str, **detail: Any) -> None:
        with _LOCK:
            self.data["stages"][name] = {
                "status": status,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                **detail,
            }
            self._save()

    def stage_status(self, name: str) -> str | None:
        return self.data["stages"].get(name, {}).get("status")

    def jev_usage(self, usage: dict[str, Any]) -> None:
        with _LOCK:
            jev = self.data["jev"]
            jev["requests"] += 1
            jev["cost_usd"] = round(jev["cost_usd"] + float(usage.get("cost", 0.0) or 0.0), 6)
            jev["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
            jev["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
            self._save()

    def asset(self, key: str, source: str, license: str, path: str) -> None:
        """Record a downloaded asset (font, HDRI, texture) and its license."""
        with _LOCK:
            self.data["assets"][key] = {"source": source, "license": license, "path": path}
            self._save()

    def event(self, text: str, **detail: Any) -> None:
        with _LOCK:
            self.data["events"].append(
                {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text, **detail}
            )
            self._save()

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
