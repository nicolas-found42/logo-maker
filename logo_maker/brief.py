"""brief.toml: what the logo is for. Written by the agent at intake; read by every stage."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HEX = re.compile(r"^#[0-9A-Fa-f]{6}\Z")
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


def _text(data: dict, key: str, problems: list[str], *, required: bool = False) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        problems.append(f"{key} must be a string")
        return ""
    value = value.strip()
    if required and not value:
        problems.append(f"{key} is required")
    return value


def _strings(data: dict, key: str, problems: list[str]) -> tuple[str, ...] | None:
    """A TOML array of strings; a bare string would otherwise explode into characters."""
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        problems.append(f"{key} must be an array of strings")
        return None
    return tuple(value)


def _table(data: dict, key: str, problems: list[str]) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        problems.append(f"{key} must be a table")
        return {}
    return dict(value)


def load(path: Path) -> Brief:
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError as exc:
        raise BriefError(f"no brief at {path}; run `logo-maker new <slug>` first") from exc
    except UnicodeDecodeError as exc:
        raise BriefError(f"{path}: not valid UTF-8 ({exc.reason})") from exc
    except tomllib.TOMLDecodeError as exc:
        raise BriefError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:  # a directory, no permission
        raise BriefError(f"{path}: cannot read ({exc.strerror or exc})") from exc
    problems: list[str] = []
    name = _text(data, "name", problems, required=True)
    summary = _text(data, "summary", problems, required=True)
    audience = _text(data, "audience", problems)
    initials = _text(data, "initials", problems)
    intended_appearance = _text(data, "intended_appearance", problems)
    tone = _strings(data, "tone", problems)
    if tone is not None and not 1 <= len(tone) <= 5:
        problems.append("tone needs 1-5 adjectives")
    if tone is not None and not all(word.strip() for word in tone):
        problems.append("tone entries must not be blank")
    uses = _strings(data, "uses", problems)
    avoid = _strings(data, "avoid", problems)
    palette = _table(data, "palette", problems)
    for role, value in palette.items():
        if role not in PALETTE_ROLES:
            problems.append(f"palette role {role!r} is not one of {PALETTE_ROLES}")
        if not isinstance(value, str) or not HEX.match(value):
            problems.append(f"palette.{role} = {value!r} is not #RRGGBB")
    from logo_maker.fonts import FontSpecError, parse_spec  # fontTools only when fonts are read

    fonts = _table(data, "fonts", problems)
    for role, spec in fonts.items():
        if role not in FONT_ROLES:
            problems.append(f"font role {role!r} is not one of {FONT_ROLES}")
        if not isinstance(spec, str):
            problems.append(f"fonts.{role} must be a string")
            continue
        try:
            parse_spec(spec)
        except FontSpecError as exc:
            problems.append(f"fonts.{role}: {exc}")
    refs = []
    raw_refs = data.get("references", [])
    if not isinstance(raw_refs, list) or not all(isinstance(raw, dict) for raw in raw_refs):
        problems.append("references must be an array of tables ([[references]])")
        raw_refs = []
    for raw in raw_refs:
        use, ref_name, note = raw.get("use", "style"), raw.get("path", ""), raw.get("note", "")
        if not isinstance(ref_name, str) or not isinstance(note, str):
            problems.append("reference path and note must be strings")
            continue
        if use not in REFERENCE_USES:
            problems.append(f"reference use {use!r} is not one of {REFERENCE_USES}")
        if not ref_name.strip() or "\x00" in ref_name:
            problems.append(f"reference path {ref_name!r} must name a file")
            continue
        ref_path = (path.parent / ref_name).resolve()
        if use != "craft" and not ref_path.is_file():
            problems.append(f"reference {ref_name!r} does not exist")
        refs.append(Reference(ref_path, use, note))
    if problems:
        raise BriefError(f"{path}: " + "; ".join(problems))
    return Brief(
        name=name,
        summary=summary,
        tone=tone or (),
        audience=audience,
        initials=initials,
        uses=uses or (),
        avoid=avoid or (),
        palette={k: v.upper() for k, v in palette.items()},
        fonts=fonts,
        references=tuple(refs),
        intended_appearance=intended_appearance,
    )


def write_template(path: Path, name: str) -> None:
    if path.exists():
        raise BriefError(f"{path} already exists")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in name):
        raise BriefError(f"name {name!r} contains a control character")
    escaped = json.dumps(name, ensure_ascii=False)[1:-1]  # TOML basic strings share JSON escapes
    try:
        data = TEMPLATE.format(name=escaped).encode("utf-8")
    except UnicodeEncodeError as exc:  # lone surrogates from JSON escapes or undecodable argv
        raise BriefError(f"name {name!r} is not valid Unicode text") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
