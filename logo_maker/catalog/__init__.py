"""Catalog of 3D treatments, materials, and lighting rigs (TOML files beside this module)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from logo_maker.paths import CATALOG_DIR


@dataclass(frozen=True)
class Entry:
    id: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)


def _load(name: str) -> dict[str, Entry]:
    data = tomllib.loads((CATALOG_DIR / f"{name}.toml").read_text())
    entries = {}
    for key, raw in data.items():
        raw = dict(raw)
        description = raw.pop("description", "")
        if not description:
            raise ValueError(f"catalog/{name}.toml: [{key}] needs a description")
        entries[key] = Entry(key, description, raw)
    return entries


@cache
def treatments() -> dict[str, Entry]:
    return _load("treatments")


@cache
def materials() -> dict[str, Entry]:
    return _load("materials")


@cache
def lighting() -> dict[str, Entry]:
    return _load("lighting")
