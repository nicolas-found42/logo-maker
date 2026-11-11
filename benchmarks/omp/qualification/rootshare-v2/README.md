# Rootshare R — different-material calibration fixture

This is an experimental artifact, not a catalog entry, default or approved winner.
The owner rejected this exact R final overall and requested a more specific brief and more detail.
Separate owner craft/fit labels remain unknown. After iterative feedback it is a development case,
not an untouched holdout for future workflow validation. See the exact measured final and
limitations under
`../../validation/issue-2/follow-up/`.

The brief combines Rootshare's R and a seed-shaped counter in unglazed terracotta with pale
ceramic inlay. `concept/motif.py` produces the shared flat master. `concept/prepare_sculpt.py`
constructs closed rounded meshes from its contours; `concept/scene.py` shades the mesh walls.
No bevel modifier or generated bitmap is used.

From the repository root, with the locked environment:

```sh
uv run --locked python benchmarks/omp/qualification/rootshare-v2/concept/motif.py
uv run --locked python benchmarks/omp/qualification/rootshare-v2/concept/prepare_sculpt.py
uv run --locked python -c 'from pathlib import Path; from logo_maker.render import render;
print(render(Path("benchmarks/omp/qualification/rootshare-v2/concept"), "final"))'
```

The PLY files retain the measured geometry. Rebuilding or rendering creates new evidence and
must not overwrite the archived image's identity or owner labels. GPU tracing and denoising
are required; CPU geometry preparation and host work are permitted. No bundled Chief artwork
supplies this fixture's design. Add an explicit craft reference when using production eligibility.
