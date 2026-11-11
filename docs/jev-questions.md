# Jev questions

Every question Jev answers, generated from `logo_maker/jev/questions.py` (`describe()`) by
`scripts/gen_docs.py`. Jev answers; the truth table named in the last column decides.

| question | type | options / levels | threshold | feeds |
|---|---|---|---|---|
| `activity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `audience` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `communication` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `grounding` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `consistent` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `source_sample_directions` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `fact_activity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `requirement_visual` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `obligation_specificity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `brief_clarified_specificity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `mandates` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | brief review -> ideation/requirements.json (only pass freezes) |
| `plan_grounded` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `plan_mandates` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `plan_shared_identity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `plan_construction` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `plan_detail_0` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `plan_obligation_detail` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | plan review -> concepts/<id>/plan-review.json (intent only; pass before preview) |
| `realized_detail_0` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | authoring obligation -> actual-image eligibility (only settled passes advance) |
| `detail_developed` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | authoring obligation -> actual-image eligibility (only settled passes advance) |
| `obligation_realized` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | authoring obligation -> actual-image eligibility (only settled passes advance) |
| `rendering` | choice | `dimensional_object`, `flat_vector` | top choice wins (a companion Noul guards the null case where one exists) | intake.json style record |
| `lettering` | choice | `no_lettering`, `sans_lettering`, `script_lettering`, `serif_lettering` | top choice wins (a companion Noul guards the null case where one exists) | intake.json style record |
| `ornament` | choice | `minimal_plain`, `ornate_detailed` | top choice wins (a companion Noul guards the null case where one exists) | intake.json style record |
| `color_mood` | choice | `bold_saturated`, `deep_jewel`, `monochrome_neutral`, `muted_earthy`, `soft_pastel` | top choice wins (a companion Noul guards the null case where one exists) | intake.json style record |
| `brand_1E4A7A` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | intake.json brand_colors (brand p >= 0.7) |
| `palette_pick` | choice | `palette_1e4a7a` | top choice wins (a companion Noul guards the null case where one exists) | pick_palette truth table -> ideation/palette.json |
| `any_palette_fits` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | pick_palette truth table (companion Noul; <0.3 raises) |
| `font_pick` | choice | `typeface_family-a` | top choice wins (a companion Noul guards the null case where one exists) | pick_fonts truth table -> ideation/fonts.json |
| `any_font_fits` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | pick_fonts truth table (companion Noul; <0.3 raises) |
| `fits_extruded_solid` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | select_pool top-k rule -> pool.jsonl |
| `fits_polished_metal` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | select_pool top-k rule -> pool.jsonl |
| `concept_fit` | choice | `off_brand`, `strong_fit`, `weak_fit` | top choice wins (a companion Noul guards the null case where one exists) | stage1_decision -> stage1.jsonl |
| `feasible_as_object` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | stage1_decision -> stage1.jsonl |
| `legible_at_size` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | stage1_decision -> stage1.jsonl |
| `standout` | score | `0-4`, `Generic: could belong to any brand.`, `Familiar: a common idea with a small twist.`, `Distinctive: memorable among comparable marks.`, `Striking: immediately catches the eye.`, `Iconic: one of a kind.` | expected value vs the stage's named cutoff | stage2_composite -> stage2.jsonl |
| `double_meaning` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | stage2_composite -> stage2.jsonl |
| `memorable` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | stage2_composite -> stage2.jsonl |
| `preferred_mark` | choice | `sample_alpha`, `sample_beta` | top choice wins (a companion Noul guards the null case where one exists) | head_to_head_table -> tournament.jsonl / winner.json |
| `matches_concept` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | preview_decision -> finalists.json |
| `readable_mark` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | preview_decision -> finalists.json |
| `appealing` | score | `0-4`, `Unappealing: unpleasant to look at.`, `Plain: inoffensive but forgettable.`, `Pleasant: nice to look at.`, `Beautiful: visually striking.`, `Gorgeous: a mark worth keeping for years.` | P(level >= 2) >= 0.5; expected value ranks survivors | preview_decision -> finalists.json |
| `form_finish` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `surface_finish` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `detail_finish` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `edge_refinement` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `material_construction` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `proportion_control` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `visual_hierarchy` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `lighting_control` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `symbol` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `appearance` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `brand_specificity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | intake.json brand_colors (brand p >= 0.7) |
| `meaningful_synthesis` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `constraint_fidelity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `communicative_clarity` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `small_flat` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `small_hero` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `noise_free` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `detail_preserved` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `aliasing_free` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `structure_correct` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled | eligibility_decision -> qa/eligibility.jsonl (only pass advances) |
| `motif_readable` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled; only no (< 0.3) blocks | qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix) |
| `nothing_cut_off` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled; only no (< 0.3) blocks | qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix) |
| `clean_edges` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled; only no (< 0.3) blocks | qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix) |
| `no_veil_or_box` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled; only no (< 0.3) blocks | qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix) |
| `recognizable_at_32px` | noul | `true`, `false` | yes >= 0.7, no < 0.3, else unsettled; only no (< 0.3) blocks | qa_blocks -> qa/rounds.jsonl (fail triggers that check's fix) |
