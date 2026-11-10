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
renderer = "cycles"            # cycles | mitsuba | luxcore | three
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
`ring_text` needs `text` and `font` (a font spec like the brief's, e.g. `"Inter:wght=700"`, or a TTF path); `from_treatment`
leaves both blank for the agent to fill. A mark component with no `layers`
builds every role group (height-0 and empty layers skipped); role-less motifs
keep the topmost-layer rule. `relief`, `layers`, `extrude`, and `inflate`
accept `height_scale`, a multiplier on their vertical params
(height / step+slab / depth / puff) for readability fixes. `relief` with
`mode = "cut"` or `"through"` punches the target plate and lays a floor;
`recess` punches a round (`radius`) or motif-shaped (`layers`) pocket.

The QA loop may only adjust `camera.framing`, `[render]` `adaptive_threshold`
and `max_samples`, `height_scale` on mark components, `render.alpha_cleanup`,
and `lighting.rig`. Anything structural means re-authoring the scene.
