# Scene grammar (scene.toml)

A scene composes catalog components into one 3D logo. Validate with
`logo_maker.scene.load_scene`; start from `from_treatment`; resolve with
`compile`. Units: the motif's 1000-unit box is 2.0 scene units.

```toml
[meta]
concept = "metaphor|treatment|material"
treatment = "embossed_plate"   # catalog preset this scene started from
seed = 1234                    # from run.json

[camera]
tilt_deg = 28                  # 0 = straight on, max 89
azimuth_deg = 0
lens_mm = 100
framing = 0.84                 # fraction of the frame the bounds fill (0.05-1)

[mark]
scale = 0.82                   # motif size (0.1-2.0); presets size it to clear
                               # plate edges, rims, and ring text

[lighting]
rig = "studio_soft"            # catalog/lighting.toml: studio_soft, three_point, raking, top_flat
hdri = "none"                  # polyhaven:<slug> | ambientcg:<id> | none | absolute path
hdri_strength = 0.45

[render]
renderer = "cycles"            # keep cycles: mitsuba | luxcore | three load, but the pipeline
                               # refuses to render them (GPU-only policy)
look = "photoreal"             # photoreal | toon | lineart
glare = 0.0                    # compositor bloom mix, 0 = off (unavailable in
                               # headless pip bpy: renders without it, loudly)
dof_fstop = 0.0                # 0 = no depth of field
adaptive_threshold = 0.01      # optional: adaptive sampling noise target
max_samples = 256              # optional: overrides the quality sample count
alpha_cleanup = false          # optional: clear faint background haze host-side

[materials.surface]
preset = "porcelain"           # catalog/materials.toml
color = "#F8F6F1"              # overrides the preset base color (optional)

[materials.accent]             # from_treatment emits one table per motif role
preset = "porcelain"          # present (primary, secondary, accent, highlight,
color = "#DDAA33"             # ink), colored from the layer fill

[[components]]
kind = "plate"                 # every kind in catalog/components.md, with its fields
material = "surface"           # plates, rims, recesses, ring text use surface;
                               # each mark component names its role instead
```

```toml
[[components]]                 # one copy per role group for mark kinds
kind = "extrude"               # (relief, extrude, inflate, tube, voxels, layers)
material = "accent"            # the role this copy builds
layers = [ "bar" ]             # motif layer ids of that role
depth = 0.44                  # preset depth scaled by the group's layer height
```

Component kinds: `plate`, `recess`, `rim`, `relief`, `extrude`, `inflate`,
`layers`, `ring_text`, `ribbon`, `tube`, `voxels`, `cad`, `mesh`, `bpy`.
`ring_text` needs `text` and `font` (a font spec like the brief's, e.g.
`"Inter:wght=700"`, or a TTF path); `from_treatment` leaves both blank for the
agent to fill. A mark component with no `layers`
builds every role group (height-0 and empty layers skipped); role-less motifs
keep the topmost-layer rule. `relief`, `layers`, `extrude`, and `inflate`
accept `height_scale`, a multiplier on their vertical params
(height / step+slab / depth / puff) for readability fixes. `relief` with
`mode = "cut"` or `"through"` punches the target plate and lays a floor;
`recess` punches a round (`radius`) or motif-shaped (`layers`) pocket.

Technical QA returns scoped diagnosis work; it does not guess sampling, lighting or height changes.
Use [refinement.md](refinement.md) to retain critique and comparisons. Structural authoring may change
motif geometry, component topology and bespoke `scene.py`, while preserving the shared motif contract.
Sampling actions belong to #5's bounded policy and preserve explicit user settings.

## How a treatment consumes the motif

The starter scene already wires the treatment; this is what each one does with
the motif's filled shapes (from `catalog/treatments.toml`):

- `extruded_solid`: the mark itself as a solid object with depth and beveled
  edges, free-standing.
- `embossed_plate`: the mark raised in relief from a flat plate or tile.
- `debossed_plate`: the mark pressed or carved into a plate, below the surface.
- `stencil_plate`: the mark cut all the way through a plate.
- `layered_cutout`: the mark as stacked flat cut-out layers at different
  heights, with visible steps.
- `inflated_soft`: the mark as a rounded, puffy form.
- `medallion`: the mark in relief inside a round disc with a raised rim; room
  for `ring_text` around the edge.
- `shaped_badge`: the mark on a shaped badge (shield, hexagon, rounded square)
  with a raised border.
- `tube_lines`: the outline of each filled shape swept as a continuous round
  tube (wire/neon look). Draw filled shapes; it traces them for you.
- `voxel_build`: the mark assembled from small cubes.
- `engraved_lines`: the mark as fine engraved lines read through line art.
- `toon_object`: the mark as a solid object with flat cel shading.

## Tuning ranges

Per-kind component fields and their defaults live in
`logo_maker/catalog/components.md`; material presets and their parameters in
`logo_maker/catalog/materials.toml`. Both are reference reading.

- `camera.tilt_deg`: 15–35 reads as a product shot; past 45 the mark foreshortens.
- `camera.framing`: 0.8–0.9 usually leaves margin for shadows; revise it after inspecting
  crop/margin evidence.
- `[mark] scale`: 0.7–1.0 for plates and rims; smaller only when a ring of text
  needs room.
- `tube.radius`: default 0.035; 0.02 is hairline, 0.06 is heavy cable. Tubes
  ride at `z` above the plate (default 0.1); raise `z` to clear rims.
- Mark heights come from the motif layer heights; a component's `height` /
  `depth` is scaled by the group's layer height, and `height_scale`
  multiplies that for readability fixes.
- `Motif.regular_polygon(cx, cy, r, n, rotation_deg=-90)` puts a vertex at the
  top; pass `rotation_deg=0` for a flat top edge.

## Bounded sampling controls

The `[sampling]` profile, diagnosis, diagnostic-storage, attempt and wall-clock controls are documented
in [the sampling policy](../../../docs/automatic-sampling.md). Use that policy's source/image-bound
diagnosis for numeric changes. `construction.json` and creative inspection supply brand intent and
revision evidence; they do not replace a qualified machine profile or independent-seed noise review.
