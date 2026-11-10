"""Every jev question, threshold, and truth-table input in one place.

Jev judges; code decides. Each builder here returns a question set (a mapping of
question id to a `noul`/`choice`/`score` question). Each decision lives in a
named function or named constants beside it, so audits edit wording here and
logic in the open. `describe()` enumerates every question for docs/jev-questions.md.
"""

from __future__ import annotations

from typing import Any

#: Noul bands: >= YES reads as yes, < NO reads as no, between is unsettled
#: and gets its own row in every truth table.
NOUL_YES = 0.7
NOUL_NO = 0.3

Verdict = str  # 'yes' | 'no' | 'unsettled'


def noul_status(p: float) -> Verdict:
    """Bucket a Noul probability into yes / no / unsettled."""
    if p >= NOUL_YES:
        return "yes"
    if p < NOUL_NO:
        return "no"
    return "unsettled"


def concept_state(
    brief: Any,
    *,
    metaphor: str,
    treatment: str,
    material: str,
    treatment_id: str = "",
    material_id: str = "",
) -> dict[str, Any]:
    """Shared state for concept judgments: named fields, no empty values."""
    return {
        "brief": brief.as_state(),
        "concept": {
            "metaphor": metaphor,
            "treatment": treatment,
            "material": material,
            "treatment_id": treatment_id,
            "material_id": material_id,
        },
    }


# -- intake: reference style ------------------------------------------------


def intake_style_questions() -> dict[str, dict[str, Any]]:
    """How a style reference looks. State holds `brief` and `reference` (an Image)."""
    return {
        "rendering": {
            "type": "choice",
            "instructions": "Is the mark in `reference` flat or dimensional?",
            "criteria": {
                "flat_vector": "Flat vector shapes with solid fills and no shading or depth.",
                "dimensional_object": "A dimensional object with shading, shadow, or visible depth.",
            },
        },
        "lettering": {
            "type": "choice",
            "instructions": "What lettering does the mark in `reference` use?",
            "criteria": {
                "serif_lettering": "Letters with serifs or bracketed stroke endings.",
                "sans_lettering": "Plain letters without serifs.",
                "script_lettering": "Handwritten, calligraphic, or connected cursive letters.",
                "no_lettering": "No letters or words anywhere in the mark.",
            },
        },
        "ornament": {
            "type": "choice",
            "instructions": "Is the mark in `reference` ornate or minimal?",
            "criteria": {
                "ornate_detailed": "Dense decoration, fine lines, textures, or many small elements.",
                "minimal_plain": "A few plain shapes with generous empty space.",
            },
        },
        "color_mood": {
            "type": "choice",
            "instructions": "What is the color mood of the mark in `reference`?",
            "criteria": {
                "muted_earthy": "Muted earthy tones such as clay, moss, sand, or bark.",
                "bold_saturated": "Bold saturated colors with strong contrast.",
                "soft_pastel": "Soft pale tints with low contrast between them.",
                "monochrome_neutral": "Black, white, and grays only.",
                "deep_jewel": "Deep jewel tones such as emerald, sapphire, or garnet.",
            },
        },
    }


def intake_color_questions(hexes: list[str]) -> dict[str, dict[str, Any]]:
    """Per extracted color: is it a brand color of the mark, or background/shadow?

    Option names carry the hex so the model sees content, not positions.
    """
    questions = {}
    for hexcode in hexes:
        tag = hexcode.lstrip("#")
        questions[f"brand_{tag}"] = {
            "type": "noul",
            "instructions": f"Is the color {hexcode} in `reference` a brand color of the mark itself?",
            "criteria": {
                "true": f"The mark itself is painted {hexcode}; removing it would change the design.",
                "false": f"{hexcode} is only a background, shadow, highlight, or photo artifact.",
            },
        }
    return questions


# -- intake: palette and font picks ------------------------------------------


def palette_option_name(palette: dict[str, str], taken: set[str]) -> str:
    """Content-descriptive option name from the primary (else first) color."""
    seed = palette.get("primary") or next(iter(palette.values()))
    base = f"palette_{seed.lstrip('#').lower()}"
    name, i = base, 2
    while name in taken:
        name = f"{base}_{i}"
        i += 1
    taken.add(name)
    return name


def palette_questions(proposals: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Pick one palette; the companion Noul tells code when none fits."""
    taken: set[str] = set()
    criteria = {}
    for palette in proposals:
        name = palette_option_name(palette, taken)
        roles = ", ".join(f"{role} {hexcode}" for role, hexcode in sorted(palette.items()))
        criteria[name] = f"A palette of {roles}."
    return {
        "palette_pick": {
            "type": "choice",
            "instructions": "Which palette in `proposals` best fits the brand in `brief`?",
            "criteria": criteria,
        },
        "any_palette_fits": {
            "type": "noul",
            "instructions": "Does any palette in `proposals` fit the brand in `brief`?",
            "criteria": {
                "true": "At least one palette suits the brand and its tone.",
                "false": "Every palette clashes with the brand, its tone, or its uses.",
            },
        },
    }


def font_option_name(pairing: dict[str, str], taken: set[str]) -> str:
    """Content-descriptive option name from the display family's slug."""
    from logo_maker.paths import slugify

    family = pairing.get("display", next(iter(pairing.values()))).split(":")[0]
    base = f"typeface_{slugify(family)}"
    name, i = base, 2
    while name in taken:
        name = f"{base}_{i}"
        i += 1
    taken.add(name)
    return name


def font_questions(proposals: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Pick one font pairing; the companion Noul tells code when none fits."""
    taken: set[str] = set()
    criteria = {}
    for pairing in proposals:
        name = font_option_name(pairing, taken)
        roles = ", ".join(f"{role} {spec}" for role, spec in sorted(pairing.items()))
        criteria[name] = f"A pairing of {roles}."
    return {
        "font_pick": {
            "type": "choice",
            "instructions": "Which font pairing in `proposals` best fits the brand in `brief`?",
            "criteria": criteria,
        },
        "any_font_fits": {
            "type": "noul",
            "instructions": "Does any font pairing in `proposals` fit the brand in `brief`?",
            "criteria": {
                "true": "At least one pairing suits the brand and its tone.",
                "false": "Every pairing clashes with the brand, its tone, or its uses.",
            },
        },
    }


# -- ideation: pre-pool scoring ------------------------------------------------


def treatment_fit_questions(
    metaphor_text: str, treatments: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Per treatment: would it suit this metaphor? State holds `brief` and `metaphor`."""
    questions = {}
    for tid, desc in treatments.items():
        questions[f"fits_{tid}"] = {
            "type": "noul",
            "instructions": (
                f"The motif for `brief` is described in `metaphor`. "
                f"Would this treatment suit it: {desc}"
            ),
            "criteria": {
                "true": "The treatment suits the brand and keeps the motif recognizable.",
                "false": "The treatment clashes with the brand or hides the motif.",
            },
        }
    return questions


def material_fit_questions(materials: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Per material: would it suit the brief? State holds `brief`."""
    questions = {}
    for mid, desc in materials.items():
        questions[f"fits_{mid}"] = {
            "type": "noul",
            "instructions": f"The brand is described in `brief`. Would this material suit its logo: {desc}",
            "criteria": {
                "true": "The material suits the brand and its tone.",
                "false": "The material clashes with the brand, its tone, or its uses.",
            },
        }
    return questions


# -- ideation: stage 1 screen ---------------------------------------------------

#: Fits that survive stage 1 (anything else drops the concept).
STAGE1_KEEP_FITS = ("strong_fit", "weak_fit")


def stage1_questions() -> dict[str, dict[str, Any]]:
    """Brand fit, buildability, small-size legibility for one concept."""
    return {
        "concept_fit": {
            "type": "choice",
            "instructions": "How well does the motif in `concept` fit the brand in `brief`?",
            "criteria": {
                "strong_fit": "The motif clearly expresses the brand and its tone.",
                "weak_fit": "The motif loosely relates to the brand but needs interpretation.",
                "off_brand": "The motif misrepresents the brand or contradicts its tone or avoid list.",
            },
        },
        "feasible_as_object": {
            "type": "noul",
            "instructions": "Could the motif in `concept` be built as a physical 3D object?",
            "criteria": {
                "true": "The motif has clear separable shapes the treatment can form in depth.",
                "false": "The motif depends on fine print, gradients, or photographic detail no geometry can form.",
            },
        },
        "legible_at_size": {
            "type": "noul",
            "instructions": "Would the motif in `concept` still read at favicon size?",
            "criteria": {
                "true": "The silhouette stays recognizable when shrunk to a small icon.",
                "false": "Details merge into a blob when the motif is shrunk.",
            },
        },
    }


def stage1_decision(answers: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    """Truth table: off-brand, unbuildable, or illegible concepts drop; the rest pass.

    Unsettled Nouls pass with a flag so stage 2, not a threshold, resolves doubt.
    """
    fit = answers["concept_fit"]["choice"]
    feas = noul_status(answers["feasible_as_object"]["noul"])
    leg = noul_status(answers["legible_at_size"]["noul"])
    if fit not in STAGE1_KEEP_FITS:
        return False, f"fit is {fit}"
    if feas == "no":
        return False, "not feasible as a 3D object"
    if leg == "no":
        return False, "illegible at small size"
    flags = " ".join(
        f"[{q} {noul_status(answers[q]['noul'])}]"
        for q in ("feasible_as_object", "legible_at_size")
        if noul_status(answers[q]["noul"]) == "unsettled"
    )
    return True, f"fit is {fit}" + (f" {flags}" if flags else "")


# -- ideation: stage 2 standout ---------------------------------------------------

STAGE2_DOUBLE_MEANING_BONUS = 0.5
STAGE2_MEMORABLE_BONUS = 0.5


def stage2_questions() -> dict[str, dict[str, Any]]:
    """Distinctiveness, second meaning, memorability for one surviving concept."""
    return {
        "standout": {
            "type": "score",
            "instructions": "How distinctive is the motif in `concept` for the brand in `brief`?",
            "criteria": [
                "Generic: could belong to any brand.",
                "Familiar: a common idea with a small twist.",
                "Distinctive: memorable among comparable marks.",
                "Striking: immediately catches the eye.",
                "Iconic: one of a kind.",
            ],
        },
        "double_meaning": {
            "type": "noul",
            "instructions": "Does the motif in `concept` carry a second meaning or visual twist?",
            "criteria": {
                "true": "A viewer can point to the second meaning in the shapes.",
                "false": "The motif shows one idea only.",
            },
        },
        "memorable": {
            "type": "noul",
            "instructions": "Would a viewer remember the motif in `concept` after one glance?",
            "criteria": {
                "true": "The motif sticks in memory after a single brief look.",
                "false": "The motif is forgettable among other marks.",
            },
        },
    }


def stage2_composite(answers: dict[str, dict[str, Any]]) -> float:
    """Expected standout score plus half-point bonuses for yes (quarter for unsettled)."""
    total = float(answers["standout"]["score"])
    for qid, bonus in (
        ("double_meaning", STAGE2_DOUBLE_MEANING_BONUS),
        ("memorable", STAGE2_MEMORABLE_BONUS),
    ):
        status = noul_status(answers[qid]["noul"])
        total += bonus if status == "yes" else (bonus / 2 if status == "unsettled" else 0.0)
    return total


# -- tournaments (ideation and final), beats-floor ---------------------------------


def head_to_head_questions(
    name_a: str, desc_a: str, name_b: str, desc_b: str, subject: str
) -> dict[str, dict[str, Any]]:
    """Pairwise Choice between two descriptively named options (ask both orders)."""
    return {
        "preferred_mark": {
            "type": "choice",
            "instructions": f"Which mark {subject}?",
            "criteria": {name_a: desc_a, name_b: desc_b},
        },
    }


def head_to_head_table(pick_ab: str, pick_ba: str, name_a: str, name_b: str) -> tuple[str, str]:
    """Truth table over both orders: unanimous wins, splits go to `name_a`'s rival.

    Returns (winner, reason); winner is 'split' when the orders disagree, and
    code treats a split as not-beats / half-a-win, never as a silent win.
    """
    if pick_ab == pick_ba:
        return pick_ab, "unanimous in both orders"
    return "split", f"orders disagree ({pick_ab} vs {pick_ba}); treated as no decision"


# -- preview screen -------------------------------------------------------------------

#: Minimum probability that a preview is at least "Pleasant" (level 2 of `appealing`).
#: Jev's appeal levels run compressed: a hand-finished, owner-approved 3D mark scored
#: an expected 1.8 of 4 with P(>= Pleasant) of 0.64-0.69, so an expected-value floor
#: of 2.0 rejected it. "More likely pleasant than not" keeps it and drops plain renders.
PREVIEW_MIN_PLEASANT = 0.5
PLEASANT_LEVEL = 2


def pleasant_probability(appealing: dict[str, Any]) -> float:
    """P(appeal >= Pleasant) from an `appealing` score answer's level probabilities."""
    return sum(
        float(p) for level, p in appealing["probabilities"].items() if int(level) >= PLEASANT_LEVEL
    )


def preview_screen_questions() -> dict[str, dict[str, Any]]:
    """Concept match, readability, and appeal for one preview render."""
    return {
        "matches_concept": {
            "type": "noul",
            "instructions": "Does the render in `preview` show the motif described in `concept`?",
            "criteria": {
                "true": "The render clearly shows the described motif and treatment.",
                "false": "The render shows a different motif, or the treatment is unrecognizable.",
            },
        },
        "readable_mark": {
            "type": "noul",
            "instructions": "Does the mark in `preview` read clearly at a glance?",
            "criteria": {
                "true": "The mark's shape is immediately clear.",
                "false": "The mark is muddled, lost in its backdrop, or hard to parse.",
            },
        },
        "appealing": {
            "type": "score",
            "instructions": "How visually appealing is the render in `preview`?",
            "criteria": [
                "Unappealing: unpleasant to look at.",
                "Plain: inoffensive but forgettable.",
                "Pleasant: well-crafted and nice to look at.",
                "Beautiful: striking craft and finish.",
                "Gorgeous: a mark worth keeping for years.",
            ],
        },
    }


def preview_decision(answers: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    """Truth table: mismatches and unreadable marks drop; P(>= Pleasant) below cutoff drops."""
    match = noul_status(answers["matches_concept"]["noul"])
    read = noul_status(answers["readable_mark"]["noul"])
    appeal = float(answers["appealing"]["score"])
    pleasant = pleasant_probability(answers["appealing"])
    if match == "no":
        return False, "does not match its concept"
    if read == "no":
        return False, "mark unreadable"
    if pleasant < PREVIEW_MIN_PLEASANT:
        return (
            False,
            f"P(pleasant) {pleasant:.2f} below {PREVIEW_MIN_PLEASANT} (appeal {appeal:.2f})",
        )
    flags = " ".join(
        f"[{q} unsettled]"
        for q in ("matches_concept", "readable_mark")
        if noul_status(answers[q]["noul"]) == "unsettled"
    )
    return True, f"P(pleasant) {pleasant:.2f}, appeal {appeal:.2f}" + (f" {flags}" if flags else "")


# -- creative refinement ---------------------------------------------------------------

CREATIVE_SPECS = {
    "craftsmanship": "Does `render` show deliberate, coherent construction with well-resolved junctions, edges and secondary details, relative to `construction.intended_appearance`? A simple core silhouette may have rich hero detail. Gloss and roundness alone do not establish craft.",
    "brief_fit": "Do the visible symbol and geometry specifically communicate this brand's purpose and the meaning in `construction`, rather than merely presenting a generic pleasant object?",
    "material_intent": "Does the object visibly form as described in `construction.material_construction` and achieve its intended appearance? For paper examine changes of plane, folds, edges and layers. Matte and glossy treatments can each succeed when intended.",
    "description_match": "Does the actual visible motif match `construction.current_description` and remain recognizable as the flat mark in `motif`? Judge the current description, not historical pool text. Ambiguity is unresolved, not success.",
}


def creative_questions() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "type": "noul",
            "instructions": instruction,
            "criteria": {
                "true": "The image clearly demonstrates this dimension relative to the stated intent.",
                "false": "The image fails this dimension; technical validity or generic pleasantness is insufficient.",
            },
        }
        for name, instruction in CREATIVE_SPECS.items()
    }


def revision_questions() -> dict[str, dict[str, Any]]:
    return {
        "visually_distinct": {
            "type": "noul",
            "instructions": "Do `before` and `after` explore genuinely different symbol geometry or material-specific construction? Text labels, descriptions, color/material swaps, camera, sampling or finish alone do not count. Compare images with their own construction intents.",
            "criteria": {
                "true": "Meaningfully distinct visual alternatives in symbol or construction are visible.",
                "false": "Essentially the same geometry/idea, or only finish/text/technical settings differ.",
            },
        },
        "critique_resolved": {
            "type": "noul",
            "instructions": "Does `after` visibly address the concrete critique in `prior_critique` relative to its intended appearance and user direction? If no defect was asserted, does it succeed as its own deliberate alternative? A glossier or rounder finish is not automatically better. Preserve uncertainty when the images cannot establish resolution.",
            "criteria": {
                "true": "The revision resolves the stated issue, or succeeds as a deliberate alternative with no invented defect.",
                "false": "The concrete critique persists or cannot be evaluated from the images.",
            },
        },
    }


def creative_ready(answers: dict[str, dict[str, Any]]) -> bool:
    """Positive per-dimension evidence is required; uncertainty remains authoring work."""
    return all(noul_status(float(answers[name]["noul"])) == "yes" for name in CREATIVE_SPECS)


# -- final QA ----------------------------------------------------------------------------

QA_CHECK_SPECS: dict[str, dict[str, str]] = {
    "motif_readable": {
        "instructions": "Does the mark in `render` read as one clear motif?",
        "true": "The mark reads as a single clear shape.",
        "false": "The mark is muddled, doubled, or falls apart visually.",
    },
    "nothing_cut_off": {
        "instructions": "Is the whole mark in `render` inside the frame with margin to spare?",
        "true": "The full mark is visible with clear margin around it.",
        "false": "An edge of the mark is cropped by the frame.",
    },
    "clean_edges": {
        "instructions": "Are the mark's edges in `render` clean?",
        "true": "Edges are crisp with no jaggies, halos, or smears.",
        "false": "Edges show jaggies, halos, noise, or compression smears.",
    },
    "no_veil_or_box": {
        "instructions": "Is the render in `render` free of fog, veils, dark boxes, and backdrop seams over the mark?",
        "true": "The mark sits cleanly with no veil, box, or seam across it.",
        "false": "A fog patch, dark box, or seam crosses or frames the mark.",
    },
    "recognizable_at_32px": {
        "instructions": "Is the mark in `tiny` still recognizable as the same mark?",
        "true": "The tiny mark is still recognizable as the same design.",
        "false": "The tiny mark is an unrecognizable blur or blob.",
    },
}


def qa_questions() -> dict[str, dict[str, Any]]:
    """One Noul per QA check; state holds `render` (full) and `tiny` (32 px) images."""
    return {
        check: {
            "type": "noul",
            "instructions": spec["instructions"],
            "criteria": {"true": spec["true"], "false": spec["false"]},
        }
        for check, spec in QA_CHECK_SPECS.items()
    }


def qa_status(p: float) -> str:
    """Bucket a QA probability into pass / fail / unsettled."""
    status = noul_status(p)
    return {"yes": "pass", "no": "fail", "unsettled": "unsettled"}[status]


def qa_blocks(status: str) -> bool:
    """Truth table: only a clear `fail` blocks a final and triggers its fix.

    Unsettled passes with a flag. Calibration: an owner-approved 3D mark scored
    0.61-0.66 (unsettled) on motif_readable, clean_edges, and recognizable_at_32px,
    while copies degraded for one check scored 0.04-0.05 on that check (blurred and
    jaggy edges, a cropped mark). Veils, cut-offs, and aliasing are also caught by
    code (checks.alpha_report, checks.margin_report, checks.edge_report); a backdrop
    box or seam relies on this judge alone.
    """
    return status == "fail"


# -- self-description ----------------------------------------------------------------------


def describe() -> list[dict[str, Any]]:
    """One row per question id: type, options, threshold, and the truth table it feeds.

    Built by calling the builders with sample inputs, so the doc generated from
    this cannot drift from the questions actually asked.
    """
    from logo_maker import catalog as _catalog

    treatments = {tid: e.description for tid, e in _catalog.treatments().items()}
    materials = {mid: e.description for mid, e in _catalog.materials().items()}
    sample_palette = [{"primary": "#1E4A7A", "background": "#F8F6F1", "accent": "#C96F2B"}]
    sample_fonts = [{"display": "Family A:wght=700", "text": "Family B:wght=400"}]
    built: dict[str, dict[str, Any]] = {}
    built.update(intake_style_questions())
    built.update(intake_color_questions(["#1E4A7A"]))
    built.update(palette_questions(sample_palette))
    built.update(font_questions(sample_fonts))
    built.update(treatment_fit_questions("a sample motif", dict(list(treatments.items())[:1])))
    built.update(material_fit_questions(dict(list(materials.items())[:1])))
    built.update(stage1_questions())
    built.update(stage2_questions())
    built.update(
        head_to_head_questions(
            "sample_alpha",
            "The first sample mark.",
            "sample_beta",
            "The second sample mark.",
            "best fits the sample brand",
        )
    )
    built.update(preview_screen_questions())
    built.update(qa_questions())
    built.update(creative_questions())
    built.update(revision_questions())

    feeds = {
        "rendering": "intake.json style record",
        "lettering": "intake.json style record",
        "ornament": "intake.json style record",
        "color_mood": "intake.json style record",
        "palette_pick": "pick_palette truth table -> ideation/palette.json",
        "any_palette_fits": "pick_palette truth table (companion Noul; <0.3 raises)",
        "font_pick": "pick_fonts truth table -> ideation/fonts.json",
        "any_font_fits": "pick_fonts truth table (companion Noul; <0.3 raises)",
        "concept_fit": "stage1_decision -> stage1.jsonl",
        "feasible_as_object": "stage1_decision -> stage1.jsonl",
        "legible_at_size": "stage1_decision -> stage1.jsonl",
        "standout": "stage2_composite -> stage2.jsonl",
        "double_meaning": "stage2_composite -> stage2.jsonl",
        "memorable": "stage2_composite -> stage2.jsonl",
        "preferred_mark": "head_to_head_table -> tournament.jsonl / winner.json",
        "matches_concept": "preview_decision -> finalists.json",
        "readable_mark": "preview_decision -> finalists.json",
        "appealing": "preview_decision -> finalists.json",
    }
    feeds.update(
        dict.fromkeys(CREATIVE_SPECS, "creative_ready -> scoped refinement authoring stop")
    )
    feeds.update(
        {
            "visually_distinct": "image alternatives gate -> qa/comparisons.json",
            "critique_resolved": "revision comparison -> retained comparison.json",
        }
    )
    thresholds = {
        "noul": f"yes >= {NOUL_YES}, no < {NOUL_NO}, else unsettled",
        "choice": "top choice wins (a companion Noul guards the null case where one exists)",
        "score": "expected value vs the stage's named cutoff",
    }
    rows: list[dict[str, Any]] = []
    for qid, q in built.items():
        if qid in QA_CHECK_SPECS:
            rows.append(
                {
                    "question": qid,
                    "type": "noul",
                    "options": ["true", "false"],
                    "threshold": f"{thresholds['noul']}; only no (< {NOUL_NO}) blocks",
                    "feeds": "qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix)",
                }
            )
            continue
        if qid.startswith("brand_"):
            feed, thresh = "intake.json brand_colors (brand p >= 0.7)", thresholds["noul"]
            options: Any = ["true", "false"]
        elif qid.startswith("fits_"):
            feed, thresh = "select_pool top-k rule -> pool.jsonl", thresholds["noul"]
            options = ["true", "false"]
        else:
            feed = feeds[qid]
            thresh = thresholds[q["type"]]
            if qid == "appealing":
                thresh = f"P(level >= {PLEASANT_LEVEL}) >= {PREVIEW_MIN_PLEASANT}; expected value ranks survivors"
            if q["type"] == "choice":
                options = sorted(q["criteria"])
            elif q["type"] == "score":
                options = [f"0-{len(q['criteria']) - 1}", *q["criteria"]]
            else:
                options = ["true", "false"]
        rows.append(
            {
                "question": qid,
                "type": q["type"],
                "options": options,
                "threshold": thresh,
                "feeds": feed,
            }
        )
    return rows
