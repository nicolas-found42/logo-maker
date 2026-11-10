# Logo concept chain (jevify, 3 chained jev stages)

Floor: Current logo (creativity floor): 3D-rendered blue enamel disc with thin gold rim, raised ivory Playfair Display Black 'C', raised polished gold check mark passing through the C's opening; beside it the wordmark 'Chief of Staff' (Playfair, amber italic 'of') and tagline.

Pool: 20 metaphors x 5 forms x 10 materials = 1000 concepts (built combinatorially before judging; rubrics frozen first).

| Stage | Questions | In | Pass | Errors |
|---|---|---|---|---|
| 1 screen | fit (strong/weak/off-brand), feasible locally, survives 32 px | 1000 | 767 (fit==strong_fit (top p>=0.5) and feasible>=0.6 and small_size>=0.5) | 0 |
| 2 rank | standout 0-4, double meaning, beats floor | 767 | 64 (standout>=2.6 and beats_floor>=0.55 -> top 8 by standout + 0.5*double_meaning to round-robin) | 0 |
| 3 round robin | A vs B, both orders, best concept per metaphor | 8 concepts / 56 pairs | ranking below | 0 |

Stage-1 fit labels: {'strong_fit': 843, 'weak_fit': 157}.
Stage-2 passers by metaphor: {'c_check': 8, 'speech_to_check': 23, 'pocket_watch': 6, 'of_ligature': 1, 'quill_check': 2, 'chess_piece': 10, 'key': 7, 'dossier_folder': 1, 'shield_c': 6}; by material: {'wax': 9, 'letterpress': 8, 'glass': 11, 'leather_emboss': 10, 'brushed_brass': 3, 'porcelain': 3, 'enamel_gold': 10, 'clay_soft3d': 5, 'paper_cut': 3, 'flat_vector': 2}.

## Round-robin ranking (points out of 14)

| Points | Concept id | Concept |
|---|---|---|
| 10.13 | `c_check|layered|wax` | Playfair 'C' with a check passing through its opening (the chief's approval); built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as glossy deep-colored sealing wax with a soft pressed edge; built with signed-distance-field modeling (smooth unions, displacement). |
| 9.51 | `dossier_folder|layered|enamel_gold` | a closed dossier folder with a tab shaped like a 'C' and a small check on its clasp (briefed before every meeting); built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as hard enamel with polished gold metal lines (like a lapel pin); built with Blender Cycles with studio HDRI lighting. |
| 8.56 | `key|layered|leather_emboss` | a key whose bow is a 'C' and whose bit is shaped as a check (trusted keyholder, private and local); built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as blind-embossed navy leather like a portfolio cover; built with Blender Cycles with studio HDRI lighting. |
| 7.66 | `of_ligature|layered|wax` | the italic 'of' of 'Chief of Staff' as a flowing ligature that loops into a check, connecting Chief and Staff; built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as glossy deep-colored sealing wax with a soft pressed edge; built with signed-distance-field modeling (smooth unions, displacement). |
| 5.94 | `pocket_watch|layered|wax` | a pocket watch whose hands form a check mark at 'the time to decide' (meeting timing, making the call); built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as glossy deep-colored sealing wax with a soft pressed edge; built with signed-distance-field modeling (smooth unions, displacement). |
| 5.48 | `quill_check|layered|wax` | a fountain-pen nib whose slit and breather hole form a check (owner signs off); built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as glossy deep-colored sealing wax with a soft pressed edge; built with signed-distance-field modeling (smooth unions, displacement). |
| 4.43 | `speech_to_check|negative_space|wax` | a speech bubble whose tail folds into a check (what was said becomes approved action); built mainly from negative space in a single solid shape; rendered as glossy deep-colored sealing wax with a soft pressed edge; built with signed-distance-field modeling (smooth unions, displacement). |
| 4.30 | `chess_piece|layered|leather_emboss` | a chess piece silhouette (the king's right hand) whose collar forms a check; built from 3-4 stacked layers with real depth (paper-cut / shadow-box); rendered as blind-embossed navy leather like a portfolio cover; built with Blender Cycles with studio HDRI lighting. |

## Built

Winner `c_check|layered|wax` -> `/tmp/logo/wax3d.py` (bpy; Cycles CPU, Poly Haven studio HDRI, CC0) +
`/tmp/logo/final_wax.py` (Pillow/resvg lockup). Relief outlines come from the flat master via fontTools + skia-pathops
(`/tmp/logo/relief.json`), so seal and flat mark share geometry. Tagline set as a coin legend around the impression.
Tools sourced from `logo-3d-render.md`, `logo-3d-form.md`, `logo-3d-stylized.md`.

Judge output is evidence, not truth: stage-2 `beats_floor` margins are thin (0.55-0.60); the final call is visual.
