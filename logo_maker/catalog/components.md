# Scene components

`[materials.*]` table (except `bpy`), and an optional `name` (defaults to
`kind_index`). `from_treatment` emits one material table per motif role
present (`surface` for plates/rims/recesses/ring text, plus one per of
primary, secondary, accent, highlight, ink found in the motif), each naming a
`preset` from `catalog/materials.toml` with an optional `color` override. The
motif's 1000-unit box maps to 2.0 scene units. Heights are
absolute: plates put their top at `top`, and most components default their base
to the target plate's top. Set `target` to sit on a non-first plate. A mark
component (`relief`, `extrude`, `inflate`, `tube`, `voxels`, `layers`) with no
explicit `layers` builds every role group at once; `layers = [<ids>]` with
`material = <role>` restricts one copy to one group (that is how multi-color
marks are built: one copy per role, each in its own material).

- `plate` — a solid disc; the base everything else sits on.
  `shape` circle (more shapes later), `radius` 1.0, `thickness` 0.17,
  `top` 0.17, `edge` smooth|irregular, `seed` 0, `bevel` 0.0.
- `recess` — a round or motif-shaped pocket pressed into `target`.
  `radius` (round) or `layers` (motif-shaped), `depth` 0.06. The plate gets a
  matching hole, a floor slab, and a lip tube automatically.
- `rim` — a torus lip or border. `major` 0.85, `minor` 0.03, `z` (defaults to
  the target top).
- `relief` — motif layers raised above, cut into, or through the plate.
  `layers` (default: all role groups), `height` 0.03, `base` (raise: just
  under the plate top), `mode` raise|cut|through, `height_scale` 1.0
  (multiplies `height`). Cut and through punch the plate and lay a floor.
- `extrude` — the motif as a freestanding solid. `layers` (default: all role
  groups), `depth` 0.22, `base` 0.0, `bevel` 0.0, `height_scale` 1.0
  (multiplies `depth`).
- `inflate` — the motif as a soft puffy solid via a signed distance field.
  `layers` all, `puff` 0.16, `depth` 0.05, `base` 0.0, `height_scale` 1.0
  (multiplies `puff`).
- `layers` — one slab per motif `data-layer` value, stacked. `base` 0.0,
  `step` 0.05, `slab` 0.05, `height_scale` 1.0 (multiplies `step` and `slab`).
- `ring_text` — wording set on a circle, shrunk to fit and spaced evenly.
  `text` and `font` (required; a font spec such as `"Inter:wght=700"` or a TTF path), `radius` 0.7,
  `cap_height` 0.07, `base`, `extrude` 0.012.
- `ribbon` — a wavy strip with swallow-tail ends. `angle_deg` 0.0,
  `length` 3.2, `width` 0.4, `z` -0.02, `phase` 0.0, `thickness` 0.012,
  `drape` false (true drops it onto the plate with the cloth simulator).
- `tube` — motif centerlines swept into round tubes. `layers` all,
  `radius` 0.035, `z` 0.1.
- `voxels` — the motif rasterized to cubes. `layers` all, `cube` 0.07,
  `height` 0.14, `base` 0.0.
- `cad` — a build123d primitive. `op` box|rounded_box|cylinder, plus
  `size`|`radius`+`height`, `center`.
- `mesh` — an imported OBJ/STL/PLY/GLB. `path` (relative to the concept),
  `scale` 1.0, `location` [0,0,0], `smooth` true. Set `smooth = false` for planar
  folded or machined faces whose normals must not be averaged across the solid.
- `bpy` — agent-written `scene.py` with `build(ctx)`; `ctx` exposes
  `materials`, `scene`, and `link(obj)`. Escape hatch only.

Material tables can set `tangent = [1.0, 0.0, 0.0]` (any finite nonzero 3D vector)
to author a consistent brushing direction independently of mesh-generated tangents.

Every mark kind reads the motif after the scene-wide `[mark] scale` (0.1-2.0,
about the plate center); treatment presets set it so the mark clears plate
edges, rims, and ring text. Plates, rims, recesses, and ring text keep their
own sizes.

When jev judges a preview against the brief, only these change without a new
concept: `camera.framing` (fill the frame), `[render]` `adaptive_threshold`
and `max_samples` (noise vs. time), `height_scale` on `relief`, `layers`,
`extrude`, and `inflate` (readability), `lighting.rig` (`raking` brings out
relief; `top_flat` suits toon), and `render.alpha_cleanup` (clears faint
background haze host-side, keeping anti-aliased edges). Anything else needs the agent to re-author
the scene. Note: `glare` has no effect under headless pip bpy (no compositor
node tree); leave it 0 there.
