#!/usr/bin/env python3
"""Validate agent skill files (`skills/**/SKILL.md`): YAML frontmatter, metadata, and relative links."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml
import yaml.resolver

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*(?:\n|\Z)", re.DOTALL)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"`+[^`]*`+")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
ALLOWED_KEYS = {"name", "description", "disable-model-invocation"}


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML SafeLoader that rejects duplicate mapping keys."""


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.MarkedYAMLError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _outside_code_lines(markdown: str) -> list[str]:
    """Return markdown lines outside fenced code blocks with inline code spans stripped."""
    kept: list[str] = []
    fence_char = ""
    fence_len = 0
    for line in markdown.splitlines():
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if not fence_char:
                fence_char = marker[0]
                fence_len = len(marker)
                continue
            if (
                marker[0] == fence_char
                and len(marker) >= fence_len
                and not line[match.end() :].strip()
            ):
                fence_char = ""
                fence_len = 0
                continue
        if not fence_char:
            kept.append(INLINE_CODE.sub("", line))
    return kept


def validate_skill(path: Path) -> list[str]:
    """Validate a single SKILL.md file and return human-readable error strings."""
    label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{label}: cannot read file: {exc}"]

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    match = FRONTMATTER.match(text)
    if not match:
        return [f"{label}: missing opening/closing '---' YAML frontmatter block at top of file"]

    frontmatter_text = match.group(1)
    try:
        meta = yaml.load(frontmatter_text, Loader=UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        context = getattr(exc, "context", None)
        mark = getattr(exc, "problem_mark", None)
        where = f" at line {mark.line + 1} column {mark.column + 1}" if mark else ""
        detail = f"{problem} {context}".strip() if context else str(problem)
        return [f"{label}: invalid YAML frontmatter: {detail}{where}"]

    if not isinstance(meta, dict):
        return [f"{label}: YAML frontmatter must be a mapping"]

    errors: list[str] = []
    unknown = sorted(str(key) for key in meta if key not in ALLOWED_KEYS)
    if unknown:
        errors.append(f"{label}: unknown frontmatter keys: {', '.join(unknown)}")

    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{label}: frontmatter 'name' must be a non-empty string")
    elif path.parent.name and name != path.parent.name:
        errors.append(
            f"{label}: frontmatter name {name!r} does not match skill directory {path.parent.name!r}"
        )

    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{label}: frontmatter 'description' must be a non-empty string")

    if "disable-model-invocation" in meta and not isinstance(
        meta["disable-model-invocation"], bool
    ):
        errors.append(f"{label}: frontmatter 'disable-model-invocation' must be a boolean")

    body = text[match.end() :]
    if not body.strip():
        errors.append(f"{label}: skill body after frontmatter must not be empty")

    # Link text may wrap across lines, so match over the joined prose.
    prose = "\n".join(_outside_code_lines(body))
    for link_match in MARKDOWN_LINK.finditer(prose):
        raw_target = link_match.group(1).strip()
        if raw_target.startswith("<"):  # CommonMark <...> destinations may hold spaces
            target = raw_target[1:].split(">", 1)[0]
        else:
            target = raw_target.split()[0] if raw_target else ""
        target_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not target_path or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target_path):
            continue
        try:
            exists = (path.parent / target_path).resolve().exists()
        except (OSError, ValueError) as exc:  # a name too long, or a decoded NUL byte
            errors.append(f"{label}: unusable relative link target {target!r}: {exc}")
            continue
        if not exists:
            errors.append(f"{label}: broken relative link target {target!r}")

    return errors


def validate_all(paths: list[Path] | None = None, *, root: Path = ROOT) -> list[str]:
    skill_files = paths if paths is not None else sorted((root / "skills").glob("**/SKILL.md"))
    if not skill_files:
        return [f"{root / 'skills'}: no SKILL.md files found"]
    errors: list[str] = []
    for skill_file in skill_files:
        errors.extend(validate_skill(skill_file))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", type=Path, help="SKILL.md paths (default: skills/**/SKILL.md)"
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.paths or None)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
