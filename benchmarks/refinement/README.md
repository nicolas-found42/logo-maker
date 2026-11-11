# Creative refinement validation

These are regression fixtures and workflow evidence, never brand defaults or a design template.
The paper brief is the owner's Skill Swap case. Its v1 geometry/recipe comes from the retained
`design/logo/finalists/fold` study (an angular S ribbon despite the historical “shared folio” label).
The standalone replay embeds its geometry instead of reading an environment-dependent path. Source
formatting and dependency plumbing are adapted; this is a new GPU replay, not historical image bytes.
Paper v2 explores an actual open folio; v3 joins its binding and corrects its flap hinge. Matte paper
intent is preserved. Keystone is a separate infrastructure brief with satin steel/copper construction:
a generic gate is revised into an assembled arch with a tapered load-bearing key.

Run with the checkout's Python environment:

```sh
uv run --locked python scripts/validate_refinement.py paper v1 --out /tmp/refinement-paper
# Open the returned image; write the requested inspection.json.
uv run --locked python scripts/validate_refinement.py paper v1 --out /tmp/refinement-paper --resume
# Apply structural revision, retaining history in the same job folder.
uv run --locked python scripts/validate_refinement.py paper v2 --out /tmp/refinement-paper
```

Repeat for `paper v3` and `metal v1/v2`. A stop (exit 3) is a supported outcome, not a quality pass.
The runner authors no inspection and grants no readiness: an agent must open each image, record actual
observations/critique and resume. Provider failures remain errors. Full local job folders retain source
copies, compiled inputs, images, logs, inspections, judgments and comparisons per revision. Selected
public evidence and measured limits are retained alongside this README after validation.

This is creative-workflow validation. It does not qualify #5's adaptive sampling profiles, calibrate
Jev probabilities against owner labels, establish cross-brand OMP parity or assert owner approval.

Metal v3 preserves the arch idea while fixing planar-cap normal interpolation and seating the key.
These are geometry/shading changes with their own rationale, not sampling optimizations. The paper
and metal iterations intentionally include rejected intermediates: a comparison may establish a
resolved earlier critique while a new or still-uncertain craft dimension continues to block readiness.
