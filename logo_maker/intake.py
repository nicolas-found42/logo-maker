"""Intake: judge style references, pick a palette and font pairing via jev.

Reference geometry is traced, not judged; style references get one bundled
request each (style questions plus per-color brand questions share the state).
Palette/font proposals come from the agent; code drops WCAG failures first and
jev picks among survivors. A companion Noul that says nothing fits raises a
clear error asking the agent for new proposals instead of silently picking.
"""

from __future__ import annotations

import json
from typing import Any

from logo_maker.brief import Brief, load
from logo_maker.jev.client import Image, JevAsker
from logo_maker.jev.questions import (
    NOUL_NO,
    NOUL_YES,
    font_questions,
    intake_color_questions,
    intake_style_questions,
    palette_questions,
)
from logo_maker.palette import extract_colors, normalize, wcag_problems
from logo_maker.paths import LogoDir

#: A color counts as a brand color at this Noul probability.
BRAND_MIN = NOUL_YES
#: Companion-Noul floor: below this, no proposal fits and the agent must retry.
FITS_FLOOR = NOUL_NO


def judge_references(logo: LogoDir, brief: Brief, client: JevAsker) -> dict[str, Any]:
    """Judge each style reference; write `ideation/intake.json`; return it."""
    records = []
    for ref in brief.references:
        record: dict[str, Any] = {"path": str(ref.path), "use": ref.use, "note": ref.note}
        if ref.use == "style":
            colors = extract_colors(ref.path)
            hexes = [normalize(h) for h, _ in colors]
            state = {"brief": brief.as_state(), "reference": Image(ref.path)}
            questions = dict(intake_style_questions())
            questions.update(intake_color_questions(hexes))
            answers = client.ask(state, questions, label=f"intake-{ref.path.stem}")
            record["style"] = {qid: answers[qid] for qid in intake_style_questions()}
            record["colors"] = [
                {
                    "hex": h,
                    "share": round(share, 4),
                    "brand_p": answers[f"brand_{h.lstrip('#')}"]["noul"],
                    "brand": answers[f"brand_{h.lstrip('#')}"]["noul"] >= BRAND_MIN,
                }
                for (h, share) in zip(hexes, [s for _, s in colors], strict=True)
            ]
        records.append(record)
    doc = {"references": records}
    (logo.ideation / "intake.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return doc


def _norm_proposals(proposals: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{role: normalize(hexcode) for role, hexcode in p.items()} for p in proposals]


def pick_palette(
    logo: LogoDir, brief: Brief, proposals: list[dict[str, str]], client: JevAsker
) -> dict[str, str]:
    """Drop WCAG failures in code, let jev pick; write `ideation/palette.json`."""
    normed = _norm_proposals(proposals)
    dropped = {i: wcag_problems(p) for i, p in enumerate(normed)}
    survivors = [p for i, p in enumerate(normed) if not dropped[i]]
    if not survivors:
        detail = "; ".join(f"proposal {i}: {', '.join(ps)}" for i, ps in dropped.items())
        raise ValueError(
            f"every palette proposal fails WCAG; ask the agent for new proposals: {detail}"
        )
    questions = palette_questions(survivors)
    answers = client.ask(
        {"brief": brief.as_state(), "proposals": survivors}, questions, label="pick-palette"
    )
    fits_p = answers["any_palette_fits"]["noul"]
    if fits_p < FITS_FLOOR:
        raise ValueError(
            f"jev says no palette proposal fits the brief (any_palette_fits={fits_p:.2f}); "
            "ask the agent for new proposals"
        )
    from logo_maker.jev.questions import palette_option_name

    taken: set[str] = set()
    names = [palette_option_name(p, taken) for p in survivors]
    winner = survivors[names.index(answers["palette_pick"]["choice"])]
    doc = {
        "palette": winner,
        "any_fits_p": fits_p,
        "dropped_wcag": [dropped[i] for i, p in enumerate(normed) if dropped[i]],
    }
    (logo.ideation / "palette.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return winner


def pick_fonts(
    logo: LogoDir, brief: Brief, proposals: list[dict[str, str]], client: JevAsker
) -> dict[str, str]:
    """Same pattern as palettes (no WCAG step); writes `ideation/fonts.json`.

    Font existence is checked by the caller; jev only judges fit.
    """
    if not proposals:
        raise ValueError("no font proposals; ask the agent for pairings from google/fonts")
    questions = font_questions(proposals)
    answers = client.ask(
        {"brief": brief.as_state(), "proposals": proposals}, questions, label="pick-fonts"
    )
    fits_p = answers["any_font_fits"]["noul"]
    if fits_p < FITS_FLOOR:
        raise ValueError(
            f"jev says no font pairing fits the brief (any_font_fits={fits_p:.2f}); "
            "ask the agent for new proposals"
        )
    from logo_maker.jev.questions import font_option_name

    taken: set[str] = set()
    names = [font_option_name(p, taken) for p in proposals]
    winner = proposals[names.index(answers["font_pick"]["choice"])]
    doc = {"fonts": winner, "any_fits_p": fits_p}
    (logo.ideation / "fonts.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return winner


def main_intake(
    logo: LogoDir,
    palette_proposals: list[dict[str, str]],
    font_proposals: list[dict[str, str]],
    client: JevAsker,
) -> None:
    """Full intake stage: references, palette, fonts (skips what the brief sets)."""
    brief = load(logo.brief)
    judge_references(logo, brief, client)
    if brief.palette:
        (logo.ideation / "palette.json").write_text(
            json.dumps({"palette": brief.palette, "source": "brief"}, indent=2, sort_keys=True)
        )
    else:
        pick_palette(logo, brief, palette_proposals, client)
    if brief.fonts:
        (logo.ideation / "fonts.json").write_text(
            json.dumps({"fonts": brief.fonts, "source": "brief"}, indent=2, sort_keys=True)
        )
    else:
        pick_fonts(logo, brief, font_proposals, client)
