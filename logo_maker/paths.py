"""Where things live: the repo, the shared cache, and one logo's folder."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JS_DIR = REPO_ROOT / "js"
CATALOG_DIR = Path(__file__).resolve().parent / "catalog"


def cache_dir(*parts: str) -> Path:
    """Shared download cache (fonts, HDRIs, textures): $LOGO_MAKER_CACHE or ~/.cache/logo-maker."""
    configured = os.environ.get("LOGO_MAKER_CACHE")
    try:
        root = (
            Path(configured).expanduser().resolve()
            if configured
            else Path.home() / ".cache" / "logo-maker"
        )
        path = root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError) as exc:  # a file in the way, ~user that does not exist
        setting = f"LOGO_MAKER_CACHE={configured!r}" if configured else "the default ~/.cache"
        raise RuntimeError(f"cannot use {setting} as the download cache: {exc}") from exc
    return path


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot make a slug from {text!r}")
    return slug


def concept_slug(concept_id: str) -> str:
    """Concept ids are `metaphor|treatment|material`; folders use `metaphor--treatment--material`."""
    return "--".join(slugify(part) for part in concept_id.split("|"))


@dataclass(frozen=True)
class LogoDir:
    """One logo's folder. Every stage reads and writes only through these paths."""

    root: Path

    @classmethod
    def default(cls, slug: str) -> LogoDir:
        return cls(REPO_ROOT / "logos" / slug)

    @property
    def slug(self) -> str:
        return self.root.name

    @property
    def brief(self) -> Path:
        return self.root / "brief.toml"

    @property
    def run_json(self) -> Path:
        return self.root / "run.json"

    def _dir(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def inputs(self) -> Path:
        return self._dir("inputs")

    @property
    def ideation(self) -> Path:
        return self._dir("ideation")

    @property
    def metaphors(self) -> Path:
        return self.ideation / "metaphors.toml"

    @property
    def concepts(self) -> Path:
        return self._dir("concepts")

    def concept(self, concept_id: str) -> Path:
        path = self.concept_path(concept_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def concept_path(self, concept_id: str) -> Path:
        """Locate a concept directory without creating it."""
        return self.root / "concepts" / concept_slug(concept_id)

    @property
    def qa(self) -> Path:
        return self._dir("qa")

    @property
    def exports(self) -> Path:
        return self._dir("exports")


def resolve_logo(target: str, out: Path | None = None) -> LogoDir:
    if out is not None:
        return LogoDir(out.resolve())
    path = Path(target)
    if path.is_dir() and (path / "brief.toml").exists():
        return LogoDir(path.resolve())
    return LogoDir.default(slugify(target))
