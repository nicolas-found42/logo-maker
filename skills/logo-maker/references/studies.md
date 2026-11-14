# Apple Silicon 3D studies

Use this workflow to design a realistic 3D logo, compare directions, or package several selected
designs. It works before Jev access or production sampling qualification is available. You operate
the CLI, scene, references, and review. Ask the user for brand and design decisions only when those
decisions change the outcome. Use [flat assets](flat-assets.md) for flat-only requests.

## Establish the brief and physical reference

1. Create or locate the logo folder. Fill `brief.toml` using the user's words, existing artwork, and
   project evidence. Use `intended_appearance` to describe the object, material, finish,
   construction, and how its surfaces respond to light. Preserve any exact artwork requirement.
2. Gather real photographs with an overall view, a joint or edge at useful resolution, and a
   different angle or lighting condition. Keep a separate photograph from an independent capture
   or source as a holdout for the final comparison. Expand coverage to the quantity requested by
   the user. Open photos and count distinct captures. Use related objects when their construction
   and materials match the target. Claim fidelity to a particular object only where you have
   corresponding evidence for it.
3. Put allowed local copies under `inputs/`. Record them per concept in `references.json`.

   ```json
   {
     "photos": [
       {
         "path": "inputs/joint.jpg",
         "url": "https://example.com/source-page",
         "note": "Satin steel collar with a separate fastener",
         "coverage": "Joint and machining under raking light",
         "use": "craft"
       }
     ]
   }
   ```

   `path` is relative to the logo folder. Use `"holdout"` for the independent photo and
   `"research"` for supplemental views outside the paired Jev review. Brief-level reference files
   are also recognized. Use the [brief and reference guidance](brief-creation.md)
   when collecting source evidence. Record coverage gaps that remain visible in the comparison.
   When a photo demonstrates a particular join, edge, or surface, add a `match` object to its row.
   Set `feature` to `join`, `edge`, or `surface` and `view` to `hero-transparent`, `front`,
   `grazing`, `rear`, or `underside`. Set `photo_region` and `render_region` to normalized
   `[left, top, right, bottom]` boxes over the corresponding details. Leave boxes absent for a
   full view. Check both crops before review. The tool checks feature visibility before using
   the finish comparison.

## Design and compare

1. Give each direction a stable ID. Run the study preview.

   ```sh
   logo-maker study "$logo_dir" --concept first --concept second --preview
   ```

   For MCP, call `logo_study` with `concepts` and `preview: true`. On the authoring stop, describe each
   design in `concept.json` and author its `motif.svg` or `motif.py`. Use the existing outlined
   artwork for an established mark. Set a concept's `intended_appearance` if it needs its own
   construction and finish description. Use [the motif contract](motif-api.md) and inspect the flat
   silhouette at working sizes before building detail.
   For an adaptation, place the existing mark in `identity.png` and describe the required
   identity features and permitted visual changes in `concept.json` as `identity_note`.
2. Build the physical design. Edit the starter `scene.toml` using the reusable
   [scene components](scene-grammar.md), or author a `source.blend` with named editable objects,
   a camera, and packed assets. Keep custom construction reproducible with the local generator
   or documented build inputs when applicable. Avoid relying on linked files or startup scripts.
3. Re-run the preview command, open the resulting comparison, and compare each design with the
   brief and relevant photographs. If the user owns the selection, show the images and the
   tradeoffs, then wait for their choice. If the user delegates it, choose based on the brief and
   disclose the choice. Keep all designs they select for the package.

## Render, inspect and deliver

1. Supply `mono.svg` when the one-ink mark needs authored cutouts or has approved artwork.
   Supply `compact.svg` when the master mark loses recognition at icon sizes. Preserve the
   features that identify the object or wordmark while adjusting the small silhouette and
   negative space. Supply `compact-dark.svg` when a separate ink or contrast treatment is needed
   on dark surfaces. The package includes actual-size 16 px and 32 px light and dark checks.
   Open them and correct lost detail or low contrast before delivery.
2. Run `logo-maker study "$logo_dir" --concept first --concept second` with the selected IDs
   (MCP `logo_study`). Keep one stage active per logo folder. Each successful run keeps its own
   study ID and manifest. The ZIP includes each selected transparent hero, editable `.blend`, full
   and compact flat assets, favicons, survey views, and available reference evidence.
3. Open each hero at native resolution and inspect the front, grazing, rear and underside
   views. Match a hero or close-up against the reference angle and light. Check joints,
   fasteners, part thickness, edge continuity, texture scale, contact, shadow, alpha and
   small-size recognition. Open the independent holdout at this stage. If you see a tangible
   defect, save the native crop, region, cause, and proposed change under the concept's
   `inspection/`. For a more faithful angle, render a dedicated close-up. The tool carries
   authored inspection files into the next study.
4. Change one meaningful cause at a time. Compare the new preview or detail with the strongest
   prior study under matched conditions. Keep the stronger candidate and the old evidence. If a
   revision is inconclusive, stop that iteration and describe the evidence needed to settle it. For
   a suspected sampling defect, run the same design with `--compare-seed`. To also test a
   stricter adaptive threshold on the same camera and seed, use `--calibrate`. Optional
   `sampling-regions.json` names normalized `[left, top, right, bottom]` boxes over the problem
   areas. Open those regions in the rendered images and read the comparison and execution logs.
   For formal qualification, follow [the production sampling process](recovery.md#qualify-the-render).
5. Run `logo-maker review-study "$logo_dir" <study-id>` (MCP `logo_review_study`) when reference
   evidence and Jev are available. The tool checks the manifest before recording craft, fit and
   technical results. Read a visibility failure as a cue to repair the photo or render crop.
   Where both views show the feature and both orders flag its execution, inspect those crops
   for a construction or material defect. A conflicting or uncertain pair stays open. Compare
   an image with itself when a relative judgment looks suspect and keep that control outside
   the selection evidence. Inspect the findings and deliver the exact usable study even when the
   provider is unavailable. Resume the same ID for a provider retry. Updated geometry or photos
   need a new study. Record explicit owner acceptance separately with `--owner-only --accept first`
   (MCP `visual: false`, `accepted: ["first"]`). Use `--note` for the owner's wording where useful.
6. Show the overview and link the ZIP. Give the current study review and qualification states.
   Link individual scene or flat assets when the user needs them directly.
