#!/usr/bin/env python3
"""Regenerate docs that mirror code: docs/adapters.md (adapter registry) and docs/jev-questions.md.

Run `uv run python scripts/gen_docs.py`; `--check` exits 1 when a doc is stale (used by tests).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from logo_maker.adapters import STAGES, all_adapters  # noqa: E402

ADAPTERS_HEADER = """# Adapters

Every external tool logo-maker runs, generated from `logo_maker/adapters/` by `scripts/gen_docs.py`.
`logo-maker doctor` runs each check; the fix column is what it prints when a check fails.
"""


def adapters_md() -> str:
    lines = [ADAPTERS_HEADER]
    adapters = all_adapters()
    for stage in STAGES:
        rows = [a for a in adapters if a.stage == stage]
        if not rows:
            continue
        lines.append(f"\n## {stage.replace('_', ' ').capitalize()}\n")
        lines.append("| Tool | License | Use | Entry | Fix |")
        lines.append("|---|---|---|---|---|")
        for a in rows:
            lines.append(f"| {a.name} | {a.license} | {a.summary} | `{a.entry}` | `{a.fix}` |")
    return "\n".join(lines) + "\n"


JEV_HEADER = """# Jev questions

Every question Jev answers, generated from `logo_maker/jev/questions.py` (`describe()`) by
`scripts/gen_docs.py`. Jev answers; the truth table named in the last column decides.
"""


def jev_md() -> str:
    from logo_maker.jev.questions import describe

    lines = [
        JEV_HEADER,
        "| question | type | options / levels | threshold | feeds |",
        "|---|---|---|---|---|",
    ]
    for row in describe():
        options = ", ".join(f"`{o}`" for o in row["options"])
        lines.append(
            f"| `{row['question']}` | {row['type']} | {options} | {row['threshold']} | "
            f"{row['feeds']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    targets = {
        ROOT / "docs" / "adapters.md": adapters_md(),
        ROOT / "docs" / "jev-questions.md": jev_md(),
    }
    stale = [
        path for path, text in targets.items() if not path.exists() or path.read_text() != text
    ]
    if "--check" in argv:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}; run scripts/gen_docs.py")
        return 1 if stale else 0
    for path, text in targets.items():
        path.write_text(text)
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
