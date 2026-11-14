"""Every jev question, threshold, and truth-table input in one place.

Jev judges; code decides. Each builder here returns a question set (a mapping of
question id to a `noul`/`choice`/`score` question). Each decision lives in a
named function or named constants beside it, so audits edit wording here and
logic in the open. `describe()` enumerates every question for docs/jev-questions.md.
"""

from __future__ import annotations

from typing import Any


def eligibility_decision(
    *,
    craft: list[str],
    fit: dict[str, str],
    technical: str,
    evidence: str,
    fit_keys: set[str] | None = None,
) -> str:
    """Essential visual gates; preference and execution policy are deliberately absent.

    API errors stay errors; missing evidence cannot pass. Equality to the reference
    is a pass supplied by the craft judgment, never a forced preference win.
    """
    rows = [*craft, *fit.values(), technical, evidence]
    if "api_error" in rows:
        return "api_error"
    if (
        not craft
        or set(fit) != (fit_keys if fit_keys is not None else set(fit_questions()))
        or "missing_evidence" in rows
    ):
        return "missing_evidence"
    if "fail" in rows:
        return "fail"
    if evidence != "complete" or any(s != "pass" for s in [*craft, *fit.values(), technical]):
        return "unsettled"
    return "pass"


def sampling_decision(checks: dict[str, str], *, limit: str, device: str) -> str:
    """Visual acceptance and sampling stop reason remain separate from craft/fit.

    #5 supplies diagnostics when qualified. Until then the limit is unknown.
    This table diagnoses; it never prescribes repeated sample escalation.
    """
    if device != "verified":
        return "device_error"
    if set(checks) != set(technical_questions()):
        return "unknown"
    for qid, diagnosis in (
        ("structure_correct", "structural_error"),
        ("detail_preserved", "detail_loss"),
        ("aliasing_free", "persistent_aliasing"),
    ):
        if checks[qid] == "fail":
            return diagnosis
    if checks["noise_free"] == "fail":
        return (
            "cap_limited_noise"
            if limit == "capped"
            else ("sampling_noise" if limit == "below_cap" else "noise_limit_unknown")
        )
    if any(status != "pass" for status in checks.values()):
        return "unknown"
    return {"capped": "visual_pass_capped", "below_cap": "visual_pass_below_cap"}.get(
        limit, "visual_pass_limit_unknown"
    )


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


REQUIREMENT_SCOPES = {
    "must": "Mandatory: every candidate must meet this direction.",
    "prefer": "Preference: favor this direction without treating it as mandatory.",
    "avoid": "Prohibition: the design must avoid this stated property or association.",
    "open": "Open choice: no particular solution for this aspect is prescribed.",
}

SOURCE_CONTEXTS = {
    "owner": "Owner statement: establishes the owner's intent, not independently observed audience behavior.",
    "project": "Project record: its stated design constraints have project authority.",
    "fixture": "Fictional exercise record: its stated inputs and constraints apply to the exercise; they are not independently verified market facts or human owner approval.",
}

OBLIGATION_SCOPES = {
    "brief": "Mandatory workflow obligation: complete brief development before freezing, using the retained earlier brief as evidence. This is not an attribute every logo must depict.",
    "authoring": "Mandatory workflow obligation: develop the detail plan before preview and verify its visible realization before image advancement. Recording intent does not establish completed artwork.",
    "validation": "Mandatory workflow obligation: perform the declared reference comparisons before finalist or winner selection. This does not prescribe the references' styling.",
}


def brief_source_questions(source_id: str) -> dict[str, dict[str, Any]]:
    """One source-to-record relation; all source results are essential, never averaged."""
    return {
        f"source_{source_id}_directions": {
            "type": "noul",
            "instructions": "Do `recorded_directions` retain every explicit design instruction, preference, prohibition and open choice in `source.excerpt`?",
            "criteria": {
                "true": "Each explicit direction is recorded with the source's authority and scope. Descriptive business facts and feedback about a previous artifact are not new design instructions. A source without design directions needs none invented.",
                "false": "An explicit direction is missing, its authority is weakened, or its mandatory, preference, prohibition or open-choice scope is changed.",
            },
        }
    }


def brief_review_questions(
    facts: list[dict],
    requirements: list[dict] | None = None,
    sources: dict | None = None,
    obligations: list[dict] | None = None,
) -> dict[str, dict[str, Any]]:
    """Business evidence only: authoring rationale cannot establish a business fact."""
    specs = {
        "activity": (
            "Does `business` specify a concrete activity or service?",
            "A reader can identify what happens for the people served.",
            "Only broad category words or a proposed symbol are supplied.",
        ),
        "audience": (
            "Does `business` identify an intended audience situation for the identity?",
            "The audience and the context in which it encounters the identity are sufficiently clear.",
            "The audience or encounter remains an essential unknown.",
        ),
        "communication": (
            "Does `communication_priority` name a clear primary impression for this identity?",
            "It provides a useful communication priority grounded in the service and audience.",
            "It only prescribes a shape, or leaves the communication priority unclear.",
        ),
        "grounding": (
            "Are factual claims in `business` supported by the established facts and their cited excerpts?",
            "Business claims are supported; assumptions and design proposals remain explicitly separate.",
            "The factual brief relies on an unsupported claim, assumption or proposed visual explanation.",
        ),
        "consistent": (
            "Can the mandatory requirements in `requirements` be satisfied together?",
            "Requirements are compatible, including deliberately open design choices.",
            "Two mandatory requirements conflict or require an unresolved choice.",
        ),
    }
    result = {
        qid: {"type": "noul", "instructions": question, "criteria": {"true": yes, "false": no}}
        for qid, (question, yes, no) in specs.items()
    }
    for source_id in sources or {}:
        result.update(brief_source_questions(source_id))
    for fact in facts:
        if fact["status"] == "established":
            result[f"fact_{fact['id']}"] = {
                "type": "noul",
                "instructions": (
                    f"Do source excerpts with IDs {fact['sources']} support this claim: {fact['claim']}"
                ),
                "criteria": {
                    "true": "The cited excerpts support the claim without inventing additional facts.",
                    "false": "The excerpts contradict the claim, are silent, or require unsupported inference.",
                },
            }
    established_requirements = [row for row in requirements or [] if row["origin"] != "proposal"]
    directions = [(row, "requirement") for row in established_requirements]
    directions.extend(
        (row, "obligation") for row in obligations or [] if row["origin"] != "proposal"
    )
    for requirement, prefix in directions:
        result[f"{prefix}_{requirement['id']}"] = {
            "type": "noul",
            "instructions": (
                f"Do source excerpts with IDs {requirement['sources']} establish this "
                f"{requirement['origin']} requirement: {requirement['claim']}. "
                f"Required scope: {OBLIGATION_SCOPES[requirement['kind']] if prefix == 'obligation' else REQUIREMENT_SCOPES[requirement['priority']]}"
            ),
            "criteria": {
                "true": "The source establishes the stated requirement and its mandatory or optional scope.",
                "false": "The requirement or its claimed authority is an unsupported designer inference.",
            },
        }
    for obligation in obligations or []:
        if obligation["kind"] == "brief":
            result[f"brief_clarified_{obligation['id']}"] = {
                "type": "noul",
                "instructions": f"Compared with previous_briefs.{obligation['id']}, do the proposed business brief and evidence record clarify consequential design decisions?",
                "criteria": {
                    "true": "The communication priority, audience encounter, constraints or open decisions are more explicit without inventing business facts or merely prescribing the already-selected shape.",
                    "false": "Only more adjectives, a longer rationale for the same shape, or unsupported business features are added; the important decisions remain unclear.",
                },
            }
    if established_requirements:
        result["mandates"] = {
            "type": "noul",
            "instructions": "Does the brief preserve established owner/project requirements in its business and design direction?",
            "criteria": {
                "true": "Established requirements remain intact; open choices and designer proposals do not erase them.",
                "false": "A stated mandatory direction is missing, contradicted, or silently recast as optional.",
            },
        }
    return result


def plan_review_questions(
    details: list[dict], obligations: list[dict] | None = None
) -> dict[str, dict[str, Any]]:
    """Intent review only; actual pixels receive independent craft/fit/technical gates."""
    specs = {
        "plan_grounded": (
            "Is the plan's visual hypothesis connected to the frozen communication priority?",
            "The proposed relationship addresses the priority; assumptions stay separate from business facts.",
            "The rationale invents a business fact or has no stated connection to the priority.",
        ),
        "plan_mandates": (
            "Does the plan preserve mandatory frozen requirements?",
            "The proposed concept respects mandates while using declared design latitude.",
            "A mandatory requirement is contradicted or silently treated as optional.",
        ),
        "plan_shared_identity": (
            "Does the plan place its primary recognition contours in the shared flat master?",
            "The same primary identity can serve flat and hero; secondary finish may resolve only at hero scale.",
            "The hero introduces the only primary identity relationship or an incompatible mark.",
        ),
        "plan_construction": (
            "Are the plan's stated physical construction relationships mutually compatible?",
            "The described parts, contacts and material roles form a coherent proposed construction.",
            "The plan describes conflicting physical relationships or leaves its central assembly undefined.",
        ),
    }
    result = {
        key: {"type": "noul", "instructions": question, "criteria": {"true": yes, "false": no}}
        for key, (question, yes, no) in specs.items()
    }
    for i, detail in enumerate(details):
        result[f"plan_detail_{i}"] = {
            "type": "noul",
            "instructions": f"Does plan.details[{i}] identify a purposeful visible contribution for {detail['feature']!r}?",
            "criteria": {
                "true": "The feature serves recognition, proportion, hierarchy or construction/material credibility at its named scale; its removal consequence is explicit.",
                "false": "Only additional ornament, polygons or texture are offered as evidence of quality, with no visible role.",
            },
        }
    for i, obligation in enumerate(obligations or []):
        result[f"plan_obligation_{obligation['id']}"] = {
            "type": "noul",
            "instructions": f"Does the plan provide concrete authoring decisions that address authoring_obligations[{i}].claim?",
            "criteria": {
                "true": "The planned construction or material decisions address the particular requested correction, beyond merely repeating its words or proposing unrelated details.",
                "false": "The specific correction is absent, contradicted, or replaced with a self-selected feature that does not address it.",
            },
        }
    return result


def brief_followup(check: str, status: str) -> str:
    """One consequential clarification; authoring agents consult available sources first."""
    if check.startswith("fact_"):
        name = check.removeprefix("fact_")
        if status == "conflict":
            return f"Which owner/project evidence resolves the conflicting fact {name!r}?"
        return f"Which available owner/project evidence establishes the required fact {name!r}?"
    if check.startswith("requirement_"):
        return f"Which source establishes requirement {check.removeprefix('requirement_')!r} and its authority?"
    if check.startswith("obligation_"):
        return f"Which source establishes obligation {check.removeprefix('obligation_')!r} and its mandatory scope?"
    if check.startswith("brief_clarified_"):
        return "Which consequential design decisions remain unclear compared with the retained earlier brief?"
    if check.startswith("source_"):
        source_id = check.removeprefix("source_").removesuffix("_directions")
        return f"Which explicit directions in source {source_id!r} are missing or have the wrong authority or scope?"
    return {
        "activity": "What does one person actually do through this service?",
        "audience": "Who encounters this identity, and in which primary situation?",
        "communication": "Which single impression should this identity communicate first?",
        "grounding": "Which factual claims can available project/owner sources support, and which remain assumptions?",
        "consistent": "Which conflicting mandatory requirement should take priority?",
        "mandates": "How should the brief preserve the established owner/project requirements?",
        "requirements_complete": "Which explicit owner/project directions are missing or misrepresented in the requirement record?",
    }[check]


def detail_realization_questions(
    details: list[dict], *, baseline: bool, obligation: bool = True
) -> dict[str, dict[str, Any]]:
    result = {}
    for i, detail in enumerate(details):
        result[f"realized_detail_{i}"] = {
            "type": "noul",
            "instructions": f"Does the actual candidate visibly realize the contribution of detail_plan.details[{i}] ({detail['feature']}) at its declared scale?",
            "criteria": {
                "true": "The visible geometry, proportion, assembly or material response supports the planned contribution. Hero-only detail can resolve in native views without appearing in a favicon.",
                "false": "The contribution exists only in the explanation, is absent, or is undermined by unresolved construction in the actual pixels.",
            },
        }
    if baseline:
        result["detail_developed"] = {
            "type": "noul",
            "instructions": "Does the candidate visibly develop purposeful construction or material detail beyond the prior baseline?",
            "criteria": {
                "true": "More resolved proportions, junctions, seating, edge hierarchy or credible material detail develop the new direction. A higher ornament count is not required.",
                "false": "Only gloss, texture density or a more flattering explanation changes; the visible construction remains underdeveloped.",
            },
        }
    if obligation:
        result["obligation_realized"] = {
            "type": "noul",
            "instructions": "Do the actual candidate pixels fulfill the particular correction in authoring_obligation.claim?",
            "criteria": {
                "true": "Visible construction or material evidence addresses the stated correction at its relevant scale, rather than only realizing an unrelated self-selected detail plan.",
                "false": "The specific correction remains visibly unfulfilled, even if other planned details are present.",
            },
        }
    return result


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


def craft_questions() -> dict[str, dict[str, Any]]:
    """Execution only, in both image orders; equal execution meets the floor."""
    specs = {
        "form_finish": (
            "Are the candidate's contours and joins at least as deliberately finished as the reference's?",
            "Contours and joins have comparable or better control for each object's intended treatment.",
            "The candidate has less controlled joins, contours or intersections than the reference for their intended treatments.",
        ),
        "surface_finish": (
            "Is the candidate's surface execution at least as controlled as the reference's for their respective intended appearances?",
            "Each treatment has intentional surface transitions; muted and glossy finishes can be equally well executed.",
            "Surface artifacts or unresolved shading reduce the candidate below the execution level demonstrated by the reference.",
        ),
        "detail_finish": (
            "Is the candidate's visible detail resolved at least as carefully as the reference's?",
            "The candidate's own details are deliberate and resolved at the demonstrated execution level, including simpler designs.",
            "The candidate's details are less resolved than the reference's: crude, damaged, merged or unfinished below that demonstrated execution level.",
        ),
        "edge_refinement": (
            "Are the candidate's designed edge transitions as resolved as the reference's for their intended treatments?",
            "Sharp, folded, cut, rounded or beveled edges each have deliberate consistent transitions; equality meets the floor.",
            "Pinching, bevel ends, thickness changes or rims are less resolved in the candidate than in the reference for their intended treatments.",
        ),
        "material_construction": (
            "Is the candidate's intended material realized with execution control comparable to the reference's intended material?",
            "Thickness, surface response and transitions convincingly form the stated material, including deliberately matte or restrained materials.",
            "The candidate's thickness, surface response or transitions realize its intended material less convincingly than the reference realizes its own.",
        ),
        "proportion_control": (
            "Are the candidate's proportions as deliberately resolved as the reference's?",
            "Relative masses, spacing and negative space look intentional and balanced at the demonstrated execution level.",
            "The candidate's spacing, relative masses or negative spaces are less deliberately controlled than the reference's.",
        ),
        "visual_hierarchy": (
            "Does the candidate organize its primary and supporting forms with control comparable to the reference?",
            "The core motif dominates clearly and supporting detail serves it; a simple design can fully meet this standard.",
            "The candidate's core motif is less clearly organized than the reference's because of competing forms, weak focal structure or incidental detail.",
        ),
        "lighting_control": (
            "Does the candidate's lighting articulate its intended form with control comparable to the reference?",
            "Light reveals intended depth and material without obscuring important shapes, in either a restrained or high-contrast treatment.",
            "The candidate's light reveals its intended form and material less clearly than the reference's, through confusing, clipped or misplaced shading.",
        ),
    }
    return {
        qid: {
            "type": "noul",
            "instructions": instructions,
            "criteria": {
                "true": yes
                + " Equality passes. Different palette, lettering, geometry, material and edge roundness are allowed. Execution quality is the comparison, not imitation or personal preference.",
                "false": no,
            },
        }
        for qid, (instructions, yes, no) in specs.items()
    }


def fit_questions() -> dict[str, dict[str, Any]]:
    return {
        "symbol": {
            "type": "noul",
            "instructions": "Does `candidate` visibly express the motif described in `concept` for `brief`?",
            "criteria": {
                "true": "The described symbolic relationship is visible in the actual shapes and fits the brand direction.",
                "false": "The symbolic relationship is absent, contradicted or depends only on the written explanation.",
            },
        },
        "appearance": {
            "type": "noul",
            "instructions": "Does `candidate` match `intended_appearance`?",
            "criteria": {
                "true": "Gloss, reflection strength, highlight contrast and edge roundness suit the stated finish, whether restrained or glossy.",
                "false": "The visible finish contradicts the stated direction, even if it is competently executed in another style.",
            },
        },
        "brand_specificity": {
            "type": "noul",
            "instructions": "Does `candidate` contain a developed visual idea specific to the purpose or identity in `brief`?",
            "criteria": {
                "true": "Authored relationships, negative space, letterform integration or distinctive construction connect this mark to the brand beyond its broad category.",
                "false": "A stock category icon or arrangement of generic primitives could be reassigned to many brands without meaningful change; the explanation supplies the specificity.",
            },
        },
        "meaningful_synthesis": {
            "type": "noul",
            "instructions": "Do the visible shape relationships in `candidate` express the brand promise in `brief`?",
            "criteria": {
                "true": "The actual construction communicates a purposeful relationship, action or visual idea grounded in the brand promise, with a coherent shared core motif.",
                "false": "The shapes merely illustrate a category object or sit together decoratively while the claimed brand relationship remains in the prose.",
            },
        },
        "constraint_fidelity": {
            "type": "noul",
            "instructions": "Does `candidate` honor the explicit direction and avoid-list in `brief`?",
            "criteria": {
                "true": "The visible design follows the actual user constraints, including required materials, topology and identity.",
                "false": "The design contradicts a stated user constraint, despite being attractive or competently rendered.",
            },
        },
        "communicative_clarity": {
            "type": "noul",
            "instructions": "Can the intended audience in `brief` read the core visual idea in `candidate` without the concept explanation?",
            "criteria": {
                "true": "The intended relationship is perceptible from the mark itself and supports the brand's purpose.",
                "false": "A viewer needs the written concept explanation to discover the claimed meaning, or reads a conflicting idea.",
            },
        },
        "small_flat": {
            "type": "noul",
            "instructions": "Does `flat_32px` preserve the intended core motif shown in `candidate`?",
            "criteria": {
                "true": "The supplied flat artwork preserves a clear, recognizable shared core at 32 px. Secondary hero lettering and ornament need not be readable here.",
                "false": "The shared core collapses, merges or becomes a different mark at 32 px.",
            },
        },
        "small_hero": {
            "type": "noul",
            "instructions": "Does `hero_32px` retain the core motif's identity from `candidate`?",
            "criteria": {
                "true": "The primary silhouette and core relationship remain recognizable at 32 px; secondary lettering and hero ornament may disappear.",
                "false": "The core motif becomes unreadable or loses its identity at 32 px.",
            },
        },
    }


MATCHED_FEATURES = {
    "join": "the attachment or transition between the visible parts",
    "edge": "the exposed edge profile, thickness or layering",
    "surface": "the material surface and its response to light",
}


def matched_craft_questions() -> dict[str, dict[str, Any]]:
    return {
        "feature_visible": {
            "type": "noul",
            "instructions": "Do `candidate_detail` and `reference_detail` both clearly show `feature`?",
            "criteria": {
                "true": "The corresponding feature is visible in both images at a useful scale and can be assessed despite differences in object shape and lighting.",
                "false": "A different feature is shown, or framing, angle, lighting, resolution or occlusion prevents comparison.",
            },
        },
        "feature_execution": {
            "type": "noul",
            "instructions": "Does the visible `feature` in `candidate_detail` meet the finish demonstrated by `reference_detail`?",
            "criteria": {
                "true": "The named feature is at least as resolved for the candidate's stated finish. Equally controlled execution meets the floor.",
                "false": "A visible defect or implausible transition in the named candidate feature puts it below the demonstrated finish. Differences in brand, framing, shape, or gloss alone are irrelevant.",
            },
        },
    }


def matched_craft_decision(visibility: list[str], execution: list[str]) -> str:
    if visibility == ["fail", "fail"]:
        return "missing_evidence"
    if visibility == ["pass", "pass"] and execution in (["pass", "pass"], ["fail", "fail"]):
        return execution[0]
    return "unsettled"


def matched_craft_calibration_questions() -> dict[str, dict[str, Any]]:
    """Development variant. Keep it out of production until independently evaluated."""
    return {
        "candidate_visible": {
            "type": "noul",
            "instructions": "Is the named feature visible clearly enough in `candidate_detail` to inspect its construction?",
            "criteria": {
                "true": "The feature has visible edges or surface detail at a scale suitable for inspection.",
                "false": "The feature is outside the crop, hidden, or lacks enough visible detail to inspect.",
            },
        },
        "reference_visible": {
            "type": "noul",
            "instructions": "Is the corresponding feature visible clearly enough in `reference_detail` to inspect its construction?",
            "criteria": {
                "true": "The corresponding feature has visible edges or surface detail at a scale suitable for inspection.",
                "false": "The feature is outside the crop, hidden, or lacks enough visible detail to inspect.",
            },
        },
        "candidate_defect": {
            "type": "noul",
            "instructions": "Does the named feature in `candidate_detail` show a visible construction or finish defect?",
            "criteria": {
                "true": "A visible defect affects the named feature, such as intersecting parts, a broken edge, an unsupported joint, or a rough transition inconsistent with the intended finish.",
                "false": "Visible parts of the feature look consistently formed and finished for their purpose.",
            },
        },
    }


def construction_triage_question() -> dict[str, dict[str, Any]]:
    """Development comparison of specific observable alternatives."""
    return {
        "construction_observation": {
            "type": "choice",
            "instructions": "Which observation describes the named feature in `candidate_detail` compared with `reference_detail`?",
            "criteria": {
                "visible_intact_feature": "Both images show the feature. The candidate has a continuous shape or a clean connection appropriate to the feature and finish.",
                "visible_damage_or_construction_error": "A visible break, chip, open seam, overlap or malformed area affects the named candidate feature.",
                "feature_outside_inspectable_area": "The feature is outside the crop, obscured, or too small in either image.",
                "comparison_unclear": "Both views contain the feature but the angle, reflections or dissimilar construction prevent a definite judgment.",
            },
        },
    }


def adaptation_questions() -> dict[str, dict[str, Any]]:
    return {
        "source_identity": {
            "type": "noul",
            "instructions": "Does `candidate` retain the recognizable identity from `identity_source` under the changes allowed in `identity_note`?",
            "criteria": {
                "true": "The specified lettering or mark remains recognizable with the stated permitted changes to layout, finish or depth.",
                "false": "A required letter, figure, recognizable shape or other specified identity feature is missing or changed beyond the stated adaptation.",
            },
        },
        "adaptation_treatment": {
            "type": "noul",
            "instructions": "Is the specific visual treatment requested in `identity_note` visible in `candidate`?",
            "criteria": {
                "true": "The specified arrangement or treatment is apparent in the visible object.",
                "false": "The visible arrangement contradicts the specified treatment or it is absent.",
            },
        },
    }


def technical_questions() -> dict[str, dict[str, Any]]:
    """Independent image acceptance, never a diagnosis prescribing more samples."""
    specs = {
        "noise_free": (
            "Is `candidate` free of distracting stochastic grain?",
            "Gradients and shadows are visually clean.",
            "Distracting random grain remains in gradients or shadows.",
        ),
        "detail_preserved": (
            "Are the intended fine details in `candidate` preserved?",
            "Strokes, counters and fine relief remain distinct.",
            "Fine details are smeared, erased or merged, including by denoising.",
        ),
        "aliasing_free": (
            "Are the edges in `candidate` free of persistent stair-stepping or halos?",
            "Edges have clean transitions at the delivered size.",
            "Edges have visible jaggies, ringing or halos.",
        ),
        "structure_correct": (
            "Does `candidate` have the intended structure described in `concept`?",
            "The actual geometry and any lettering have the intended shapes and spelling.",
            "Geometry or lettering is structurally wrong even if smooth and noise-free.",
        ),
    }
    return {
        qid: {"type": "noul", "instructions": ins, "criteria": {"true": yes, "false": no}}
        for qid, (ins, yes, no) in specs.items()
    }


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
                "Pleasant: nice to look at.",
                "Beautiful: visually striking.",
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
    if match != "yes":
        return False, f"concept match {match}; requires review or revision"
    if read != "yes":
        return False, f"readability {read}; requires review or revision"
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
    sample_facts = [
        {
            "id": "activity",
            "claim": "The stated service exists.",
            "status": "established",
            "sources": ["sample"],
        }
    ]
    sample_requirements = [
        {
            "id": "visual",
            "claim": "Preserve the owner's stated visual requirement.",
            "priority": "must",
            "origin": "owner",
            "sources": ["sample"],
        }
    ]
    built: dict[str, dict[str, Any]] = {}
    sample_sources = {"sample": {"kind": "owner"}}
    sample_obligations = [
        {
            "id": "specificity",
            "kind": "brief",
            "origin": "owner",
            "claim": "Clarify the brief",
            "sources": ["sample"],
        }
    ]
    built.update(
        brief_review_questions(
            sample_facts, sample_requirements, sample_sources, sample_obligations
        )
    )
    sample_authoring = [{"id": "detail", "claim": "Develop purposeful detail"}]
    built.update(plan_review_questions([{"feature": "sample construction"}], sample_authoring))
    built.update(detail_realization_questions([{"feature": "sample construction"}], baseline=True))
    built.update(intake_style_questions())
    built.update(intake_color_questions(["#1E4A7A"]))
    built.update(palette_questions(sample_palette))
    built.update(font_questions(sample_fonts))
    built.update(treatment_fit_questions("a sample motif", dict(list(treatments.items())[:1])))
    built.update(material_fit_questions(dict(list(materials.items())[:1])))
    built.update(stage1_questions())
    built.update(stage2_questions())
    built.update(matched_craft_calibration_questions())
    built.update(construction_triage_question())
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
    built.update(craft_questions())
    built.update(matched_craft_questions())
    built.update(fit_questions())
    built.update(adaptation_questions())
    built.update(technical_questions())
    built.update(qa_questions())
    built.update(creative_questions())
    built.update(revision_questions())

    feeds = {
        **dict.fromkeys(
            detail_realization_questions([{"feature": "sample construction"}], baseline=True),
            "authoring obligation -> actual-image eligibility (only settled passes advance)",
        ),
        **dict.fromkeys(
            plan_review_questions([{"feature": "sample construction"}], sample_authoring),
            "plan review -> concepts/<id>/plan-review.json (intent only; pass before preview)",
        ),
        **dict.fromkeys(
            brief_review_questions(
                sample_facts, sample_requirements, sample_sources, sample_obligations
            ),
            "brief review -> ideation/requirements.json (only pass freezes)",
        ),
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
        **dict.fromkeys(
            (*craft_questions(), *fit_questions(), *technical_questions()),
            "eligibility_decision -> qa/eligibility.jsonl (only pass advances)",
        ),
        **dict.fromkeys(
            (*matched_craft_questions(), *adaptation_questions()), "study visual review"
        ),
        **dict.fromkeys(
            matched_craft_calibration_questions(),
            "development calibration comparison",
        ),
        **dict.fromkeys(construction_triage_question(), "development calibration comparison"),
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
        if (
            qid.startswith("brand_")
            and qid[6:]
            and all(c in "0123456789abcdefABCDEF" for c in qid[6:])
        ):
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
