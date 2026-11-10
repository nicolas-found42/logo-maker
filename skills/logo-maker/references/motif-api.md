# motif.py reference (for agents authoring a concept's motif)

Each concept folder has a `motif.py` you write. Running it must create a
contract-clean `motif.svg` (and `motif.json`) in the same folder. Use only
`logo_maker.motif` (+ `logo_maker.fonts` specs, `logo_maker.twod_tools`,
`logo_maker.trace`); never hand-write path data.

```python
from logo_maker.motif import Motif

m = Motif()
leaf = m.union(
    m.transform(m.circle(500, 420, 150), scale=1.0, rotate_deg=-20),
    m.polygon([(500, 300), (640, 620), (360, 620)]),
)
arc = m.stroke([(300, 650), (500, 750), (700, 650)], 26)  # centerline -> fill
word = m.glyphs("Na", "Fraunces:opsz=144,wght=600", 300, 500, 560, anchor="center")
m.add("leaf", leaf, fill="#2F5D3A", role="primary", height=1.0, layer=0)
m.add("arc", arc, fill="#C8A24B", role="accent", height=0.6, layer=1)
m.add("word", word[0], fill="#1A1A1A", role="ink", height=1.2, layer=2)
m.save(".")  # run with cwd = the concept folder
```

## Builder (every method returns a plain `d` string unless noted)

- Shapes: `circle(cx, cy, r)`, `rect(x, y, w, h, rx=0)`, `polygon([(x, y), ...])`,
  `regular_polygon(cx, cy, r, n)`, `star(cx, cy, r_outer, r_inner, points=5)`,
  `path(d)` (raw data, parsed now so typos fail fast).
- `glyphs(text, font_spec, size, x, y, anchor="baseline"|"center", tracking=0)` ->
  `(d, advance_px)`. Specs look like `"Fraunces:opsz=144,wght=600"`; `ital=1`
  picks the Italic file. `center` centers the block on `(x, y)`.
- `stroke(points_or_d, width, cap="round", join="round")` turns a centerline
  into a filled outline. Caps: round/butt/square; joins: round/miter/bevel.
- Booleans: `union(a, b)`, `difference(a, b)`, `intersection(a, b)`, `xor(a, b)`.
- Placement: `transform(d, scale, rotate_deg, translate=(dx, dy))`;
  `fit(d)` scales any path into the radius-470 circle (easiest way to satisfy
  the geometry rule).
- `add(id, d, fill, role="primary", height=1.0, layer=0)`; ids unique,
  `fill` is `#RRGGBB`, roles: primary/secondary/accent/highlight/ink.
  `save(concept_dir)` writes `motif.svg` + `motif.json` and returns the svg.

## Generative tools (`logo_maker.twod_tools`, each returns fill-ready shapes)

- `sketchy(d, roughness, bowing, seed, width)` — hand-drawn wobble (rough.js).
- `freehand([(x, y, pressure), ...], size, thinning)` — pen stroke.
- `voronoi(points, bounds)` / `delaunay(points)` — cells as fills.
- `low_poly(w, h, cell_size, variance, seed, palette)` — triangle field.
- `voxels({"cells": [...]})` — heerich voxel scene to polygons.
- `primitive_abstract(image, shapes, mode)` — geometric photo abstraction.
- `plotter_lines([d, ...], width, epsilon)` — merge/simplify, then outline.
- `fontforge_glyphs(font_path, [{"add": {"from": "A", "into": "E", "dx": 640}}])`
  — build ligatures from installed fonts, export outlines.

## The contract (checked by `validate()`; `run_motif_script()` enforces it)

- `viewBox="0 0 1000 1000"`, y down; everything inside the centered
  radius-470 circle (1 px tolerance).
- Only `<path>`: absolute coords, no `transform`, no `stroke`, unique `id`,
  `fill="#RRGGBB"`, optional `data-role` / `data-height` / `data-layer`.
- No AI imagery: every pixel comes from geometry, fonts, materials, renderers.

## Checking your work

```python
from logo_maker.motif import size_sheet, validate

print(validate("motif.svg"))  # [] means clean
size_sheet("motif.svg", "sheet.png")  # 16/32/48/64/180 px side by side
```

Open `sheet.png`: the mark must read at 16 px and hold together at 180 px.
Fit problems, stray strokes, or out-of-circle geometry fail the build — fix the
`motif.py`, never the `.svg` by hand.
