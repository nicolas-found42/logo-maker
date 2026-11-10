# Creative revision records

The authoritative stage contract is `docs/architecture.md`, “Creative refinement”.
Write per-concept `construction.json` before refinement:

```json
{
  "symbol": "What the core symbol communicates",
  "brand_geometry": "Why these shapes fit this particular brand",
  "material_construction": "How this material forms the object",
  "intended_appearance": "The intended finish and visual character",
  "disproof": "The visible result that would reject this idea",
  "current_description": "An accurate description of the current geometry",
  "dependencies": []
}
```

Set `concept.json.description` to that current description. Keep original pool text as history.
`dependencies` lists local/external files read by custom scripts, relative to the concept folder or
absolute; local concept sources/assets are discovered automatically. Declare imported helpers,
mesh/font/image inputs outside that folder so edits invalidate the evidence.

After opening the returned retained image, write `inspection.json` (`inspection-final.json` for finals):

```json
{
  "revision": "COPY THE RETURNED REVISION ID",
  "observations": "Concrete visible observations from opening this image",
  "user_feedback": "User direction, or empty when none",
  "critiques": [
    {
      "kind": "craftsmanship",
      "dimension": "fold junction",
      "artifact": "retained image path or crop",
      "evidence": "What is visibly unresolved",
      "action": "The intended authoring change",
      "comparison": "The before/after comparison that would establish resolution",
      "resolved": false
    }
  ]
}
```

Allowed kinds: `craftsmanship`, `brief_fit`, `preference`, `technical`. Use an empty critique list
when there is no concrete concern. An unresolved critique blocks progression: revise sources, open
the new image, and record the actual outcome before setting `resolved` true. Pairwise image judging
also checks resolution against the previous revision's inspection and judgments. Uncertain results
remain unresolved. A preference can be resolved by explicit user direction between successful finishes.

Retained revisions contain source copies/hashes, old/new image hashes, execution/settings evidence,
inspection, judgments and comparisons. Read `details.artifact`, `details.verdicts` and
`details.next_comparison` on CLI/MCP stops; revision/comparison paths are relative to the logo folder.
Use `status` for counts and evidence paths. An image or source change revokes downstream eligibility;
rerun refinement and preview before finalize/export. Historical evidence stays available for comparison.

For a technical stop, record `diagnosis.json` with the returned `revision`, a `cause` (`sampling_noise`,
`cap_limitation`, `design`, `geometry`, `material`, `typography`, `denoising`, `filtering`, `resolution`,
`alpha`, `unknown`) and an `evidence` list of `{artifact, sha256, observation}`. Paths are relative to
the logo folder. Missing evidence stays unknown. Sampling diagnoses route to #5's bounded policy;
this record does not authorize automatic sampling changes. Compare independent seeds and noisy/denoised
detail to establish stochastic behavior. Keep geometry, materials and lighting fixed for that probe.
