"""brief.toml: what the logo is for. Written by the agent at intake; read by every stage."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
PALETTE_ROLES = ("primary", "secondary", "accent", "highlight", "background", "ink")
FONT_ROLES = ("display", "text")
REFERENCE_USES = ("style", "geometry", "craft")

TEMPLATE = """# What the logo is for. Fill every required field; leave optional tables out rather than guessing.
name = "{name}"                 # required: the brand, project, product, or profile name
summary = ""                    # required: what it is and who it serves, 1-3 sentences
audience = ""                   # optional: who sees the logo
tone = []                       # required: 1-5 adjectives, e.g. ["playful", "precise"]
initials = ""                   # optional: letters a monogram may use
uses = ["favicon", "social_avatar", "app_icon"]   # where the logo must work
avoid = []                      # optional: things the logo must not suggest
intended_appearance = ""         # required before selection: finish, gloss/reflections, edge character

# Optional. Omit to have logo-maker propose palettes and let jev pick one.
# [palette]                     # roles: primary, secondary, accent, highlight, background, ink
# primary = "#000000"

# Optional. Omit to have logo-maker propose pairings from google/fonts and let jev pick one.
# [fonts]                       # "Family Name:axis=value,..." from github.com/google/fonts
# display = "Family:wght=700"
# text = "Family:wght=400"

# Optional, repeatable. use = "style" (jev reads its style) or "geometry" (traced into shapes; only for
# images the owner of this brief made or licensed).
# [[references]]
# path = "inputs/reference.png"
# use = "style"
# note = ""
# A separate execution-quality floor (no palette/shape/material transfer):
# [[references]]
# path = "inputs/craft-floor.png"
# use = "craft"
# note = "Describe this reference's own intended finish, not the candidate's design."
"""


class BriefError(ValueError):
    """brief.toml is missing a required field or holds an invalid value."""


@dataclass(frozen=True)
class Reference:
    path: Path
    use: str
    note: str = ""


@dataclass(frozen=True)
class Brief:
    name: str
    summary: str
    tone: tuple[str, ...]
    audience: str = ""
    initials: str = ""
    uses: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    palette: dict[str, str] = field(default_factory=dict)
    fonts: dict[str, str] = field(default_factory=dict)
    references: tuple[Reference, ...] = ()
    intended_appearance: str = ""

    def as_state(self) -> dict:
        """The brief as jev state: named fields, no empty values (an empty list reads as a signal)."""
        state: dict = {"name": self.name, "summary": self.summary, "tone": list(self.tone)}
        for key in ("audience", "initials", "intended_appearance"):
            if getattr(self, key):
                state[key] = getattr(self, key)
        for key in ("uses", "avoid"):
            if getattr(self, key):
                state[key] = list(getattr(self, key))
        if self.palette:
            state["palette"] = dict(self.palette)
        if self.fonts:
            state["fonts"] = dict(self.fonts)
        return state


def load(path: Path) -> Brief:
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError as exc:
        raise BriefError(f"no brief at {path}; run `logo-maker new <slug>` first") from exc
    problems: list[str] = []
    for key in ("name", "summary"):
        if not str(data.get(key, "")).strip():
            problems.append(f"{key} is required")
    tone = tuple(data.get("tone", ()))
    if not 1 <= len(tone) <= 5:
        problems.append("tone needs 1-5 adjectives")
    palette = dict(data.get("palette", {}))
    for role, value in palette.items():
        if role not in PALETTE_ROLES:
            problems.append(f"palette role {role!r} is not one of {PALETTE_ROLES}")
        if not HEX.match(str(value)):
            problems.append(f"palette.{role} = {value!r} is not #RRGGBB")
    fonts = dict(data.get("fonts", {}))
    for role in fonts:
        if role not in FONT_ROLES:
            problems.append(f"font role {role!r} is not one of {FONT_ROLES}")
    refs = []
    for raw in data.get("references", ()):
        use = raw.get("use", "style")
        if use not in REFERENCE_USES:
            problems.append(f"reference use {use!r} is not one of {REFERENCE_USES}")
        ref_path = (path.parent / raw.get("path", "")).resolve()
        if use != "craft" and not ref_path.is_file():
            problems.append(f"reference {raw.get('path')!r} does not exist")
        refs.append(Reference(ref_path, use, raw.get("note", "")))
    if problems:
        raise BriefError(f"{path}: " + "; ".join(problems))
    return Brief(
        name=data["name"].strip(),
        summary=data["summary"].strip(),
        tone=tone,
        audience=data.get("audience", "").strip(),
        initials=data.get("initials", "").strip(),
        uses=tuple(data.get("uses", ())),
        avoid=tuple(data.get("avoid", ())),
        palette={k: v.upper() for k, v in palette.items()},
        fonts=fonts,
        references=tuple(refs),
        intended_appearance=str(data.get("intended_appearance", "")).strip(),
    )


def write_template(path: Path, name: str) -> None:
    if path.exists():
        raise BriefError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(name=name.replace('"', "'")))
