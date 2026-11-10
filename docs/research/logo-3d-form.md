# Form-making beyond extrusion (SDF / CSG / physics / voxel / origami) — research

Scope: tools that push the "Chief of Staff" logo past the extrusion floor — blobby/wax-seal forms, smooth blends, remeshed and physics-shaped variants. Brand: private local AI workspace that remembers meetings; owner approves next steps ("Remembers the meeting. You make the call."); calm, capable, discreet. Palette `#1E4A7A #2F6B4F #B45309 #F2C14E #F8F6F1 #16232E`; fonts Playfair Display (static Black `/tmp/logo3d/PlayfairDisplay-Black.ttf`) + Open Sans (OFL, `/tmp/brandfonts/`). Environment: macOS arm64, Python 3.13 venv, Bun 1.4.3, `uv 0.13.6`, `gh 2.102.0`. Existing coverage (`assignments/research/logo-*.jsonl`) is not repeated here — this file adds only beyond-extrusion form tools. Probes ran in `/tmp/logo3d-form/` (own venv + Bun project); no system-wide installs. No AI image/3D generation APIs were used.

Environment versions observed: `bun 1.4.3`, `uv 0.13.6 (Homebrew 2026-10-26 aarch64-apple-darwin)`, probe venv `CPython 3.13.16`.

## Verdict up front

**Best chainable form pipeline (proven on this Mac): `fogleman/sdf` (smooth SDF union of disc + torus rim + extruded Playfair `C`) → STL/OBJ via `meshio` → Blender EEVEE for hero shading → `gltf-transform` optimize (weld/quantize/draco) → GLB/PNG delivery.** This is the only chain that gives true organic/wax-seal blends (varying `k` smooth union) without hand-sculpting, and both ends were run live here (§6). **Best web-native alternative:** `sdf-csg` or `@jscad/modeling` / `three-bvh-csg` in Bun + `gltf-transform` for interactive medallions. **Best emboss/text-on-curve backup:** FreeCAD Part/PartDesign (B-rep). **Ribbon/wax irregularity is a Blender Cloth/Soft-Body or PyBullet sim step, not a static mesh op** — bake the sim, then shade. **Voxel/isometric and paper-fold are accent passes** (`Froxel`/`IsoVoxel`, `pleat`), not the hero.

## 1. SDF / implicit modeling

**fogleman/sdf — probe-verified primary form tool.** "Generate 3D meshes based on SDFs (signed distance functions) with a dirt simple Python API… based on Inigo Quilez's 3D/2D SDF docs" [https://github.com/fogleman/sdf/blob/main/README.md](https://github.com/fogleman/sdf/blob/main/README.md), 2,017★ MIT, pushed 2026-09-30. Core is `sdf/core.py` (Marching Cubes via `skimage.measure.marching_cubes` + numpy batching) [https://github.com/fogleman/sdf/blob/main/sdf/core.py](https://github.com/fogleman/sdf/blob/main/sdf/core.py); 2D text SDFs via `sdf/text.py` (`text(font, "C")` → `.extrude(h)`, PIL + `scipy.ndimage.distance_transform_edt`) [https://github.com/fogleman/sdf/blob/main/sdf/text.py](https://github.com/fogleman/sdf/blob/main/sdf/text.py); `sdf/d3.py` primitives include `rounded_cylinder`, `torus`, `elongate` family helpers, smooth ops via `.k(k)` (`SDF3.__or__` → `dn.union`, where `k` selects the polynomial smooth-min blend) [https://github.com/fogleman/sdf/blob/main/sdf/d3.py](https://github.com/fogleman/sdf/blob/main/sdf/d3.py) and [https://github.com/fogleman/sdf/blob/main/sdf/dn.py](https://github.com/fogleman/sdf/blob/main/sdf/dn.py). Outputs STL natively, other formats via MeshIO [https://github.com/fogleman/sdf/blob/main/README.md](https://github.com/fogleman/sdf/blob/main/README.md). Install is git-only (`git clone … && pip install -e .`, no PyPI wheel for `sdf` itself) [https://github.com/fogleman/sdf/blob/main/README.md](https://github.com/fogleman/sdf/blob/main/README.md). Probe: see §6 — 89,504-tri medallion in 0.16 s at `samples=800_000`.

**sdfcad — pip-installable fork.** "This is my fork of fogleman/sdf… `pip install sdfcad`" [https://pypi.org/project/sdfcad](https://pypi.org/project/sdfcad), same `sdf → sdfcad` API (`sphere(1) & box(1.5) … .save('out.stl')`) [https://pypi.org/project/sdfcad](https://pypi.org/project/sdfcad). Prefer when an editable clone is unwanted; same marching-cubes core. 22★ MIT (`nobodyinperson/sdf`, pushed 2023-09-27). PyPI first published 2024-01-27 [https://pypi.org/project/sdfcad](https://pypi.org/project/sdfcad).

**libfive — research-grade F-Rep (license caution).** "Infrastructure for solid modeling… functional representations… watertight, manifold, hierarchical, feature-preserving triangle meshes… C API + Guile/Python bindings + Studio GUI" [https://github.com/libfive/libfive/blob/master/README.md](https://github.com/libfive/libfive/blob/master/README.md), 1,678★, pushed 2026-10-16. Scheme stdlib includes `(libfive text)` distance-field font/layout tools [https://libfive.com/examples](https://libfive.com/examples). **⚠ License:** GitHub license API 404s (no LICENSE file in repo; `licenseInfo: null` via `gh repo view`) — do not assume MPL/commercial clearance; confirm with the author before shipping assets. Build is full CMake/Qt/Eigen/Boost/Guile/Python, heavy for a logo.

**Curv — GPU F-Rep language.** "Open source (Apache v2.0) 2D/3D F-Rep implicit geometric modelling language… Signed Distance Fields… GPU accelerated… export meshes to STL, OBJ, X3D… watertight, manifold, no self intersections" [https://curv3d.org](https://curv3d.org), 1,168★, Apache-2.0. Active source lives on Codeberg mirror; GitHub mirror pushes to 2023-09-27. Candidates for medallions/lattices/colour fields; setup (C++/GLM/OpenGL 3.3+) is much heavier than `fogleman/sdf` for a single emblem.

**sdfx (deadsy) — Go SDF CAD.** `deadsy/sdfx` is the `SDFX` package behind the `sdfx-ui` renderer ("creating your signed distance function… `sdf.Box3D`… `ui.NewRenderer(anySDF).Run()`") [https://github.com/yeicor/sdfx-ui](https://github.com/yeicor/sdfx-ui), 633★ MIT, pushed 2026-08-29. Use when the Go toolchain is already in use; the Rust `sdf-viewer` + `sdf-viewer-go` integration is the GPU-preview successor [https://github.com/Yeicor/sdf-viewer](https://github.com/Yeicor/sdf-viewer).

**sdf-csg / retrace.gl (web SDFs).** `sdf-csg` "Generate meshes from signed distance functions and CSG operations… heavily based upon Inigo Quilez's 3D SDFs" — `Sphere/Box/Torus/CappedCylinder + smoothUnion/smoothSubtract/smoothIntersect + generateMesh([64,64,64], 0.2)` [https://npmjs.com/package/sdf-csg](https://npmjs.com/package/sdf-csg), Unlicense, 193★. `retrace.gl` is a "SDF sculptor + physically based path tracer (WebGL2)… declarative SDF CSG (hg_sdf bool ops)… export STL… Lambert/metal/dielectric/clearcoat" [https://github.com/stasilo/retrace.gl](https://github.com/stasilo/retrace.gl), GPL-3.0, 196★ — exports are fine, bundling GPL code has copyleft risk.

## 2. Marching-cubes & CSG kernels

**scikit-image `measure.marching_cubes` + PyMCubes.** "Marching cubes extracts a 2D surface mesh from a 3D volume… `verts, faces, normals, values = measure.marching_cubes(ellip_double, 0)`" [https://scikit-image.org/docs/0.23.x/auto_examples/edges/plot_marching_cubes.html](https://scikit-image.org/docs/0.23.x/auto_examples/edges/plot_marching_cubes.html), BSD-3-Clause (`LICENSE.txt` explicit), 6,636★. This is the exact engine `fogleman/sdf` calls (`_marching_cubes` → `measure.marching_cubes` [https://github.com/fogleman/sdf/blob/main/sdf/core.py](https://github.com/fogleman/sdf/blob/main/sdf/core.py)). `PyMCubes` ("marching cubes for Python… volume as NumPy array or `f(x,y,z)`… `mcubes.marching_cubes(u, 0)` → `export_obj`") [https://github.com/pmneila/PyMCubes](https://github.com/pmneila/PyMCubes), BSD-3-Clause, 799★ — use when building a custom SDF grid directly.

**JSCAD / three-bvh-csg (JS CSG).** `@jscad/modeling` "Constructive Solid Geometry (CSG) Library… boolean operations… BSP trees… `npm i @jscad/modeling`" [https://npmjs.com/package/@jscad/modeling](https://npmjs.com/package/@jscad/modeling), MIT, 3,270★. `three-bvh-csg` offers `Evaluator.evaluate(BrushA, BrushB, ADDITION|SUBTRACTION|INTERSECTION|…)` on top of `three-mesh-bvh`, "more than 100 times faster than other BSP-based three.js CSG libraries" [https://github.com/gkjohnson/three-bvh-csg/blob/main/README.md](https://github.com/gkjohnson/three-bvh-csg/blob/main/README.md), MIT, 962★. **FreeCAD** (`import Part; Part.makeBox(3,5,7)` → `Vertexes/Edges/Faces/Shells/Solids` parametric Part shapes) [https://wiki.freecad.org/Manual:Creating_and_manipulating_geometry](https://wiki.freecad.org/Manual:Creating_and_manipulating_geometry) is the B-rep emboss backup, LGPL-2.1, 35,317★, app download (not pip) — heavier than `build123d` for scripted work, keep as checker.

## 3. Mesh ops, remesh, glTF

**Open3D / libigl / PyMeshLab.** Open3D does "voxel downsampling… bucket points into voxels… estimate_normals… TSDF integration" [https://open3d.org/docs/latest/tutorial/geometry/pointcloud.html](https://open3d.org/docs/latest/tutorial/geometry/pointcloud.html) — raw LICENSE is MIT ("The MIT License (MIT)… www.open3d.org"), 14,189★. `libigl` Python ships "NumPy-native bindings… `pip install libigl`… `igl.cotmatrix`, curvature, parametrization" [https://libigl.github.io/python-bindings](https://libigl.github.io/python-bindings); core is MPL-2.0 while `igl.copyleft.*` (CGAL booleans, `remesh_self_intersections`) is GPL-3.0 — keep logo assets on the core path. `PyMeshLab` exposes "isotropic remeshing… alpha wrap… `generate_boolean_intersection`" filters [https://pymeshlab.readthedocs.io/en/0.1.8/filter_list.html](https://pymeshlab.readthedocs.io/en/0.1.8/filter_list.html), GPL-3.0, 984★ — `meshing_isotropic_explicit_remeshing` is the right conditioner for marching-cubes output. **Instant Meshes** (field-aligned quad-dominant remesher) [https://github.com/wjakob/instant-meshes](https://github.com/wjakob/instant-meshes), 6,292★, LICENSE.txt is BSD-3-Clause text sans SPDX — good for a deformable-hero quad pass; dormant since 2022.

**Delivery: gltf-transform + Draco + meshio + PyVista.** `gltf-transform` CLI is `npm install --global @gltf-transform/cli` with `inspect` + `optimize input.glb output.glb --compress draco --texture-compress webp` [https://gltf-transform.donmccurdy.com/cli](https://gltf-transform.donmccurdy.com/cli), MIT, 2,070★ — probe-verified (§6). `Draco` "compresses vertex positions, normals, colors, texture coordinates… `draco_transcoder -i in.glb -o out.glb`" [https://github.com/google/draco/blob/main/README.md](https://github.com/google/draco/blob/main/README.md), Apache-2.0, 7,546★. `meshio` (`pip install meshio`, 20+ formats STL/OBJ/PLY/VTK) [https://github.com/nschloe/meshio](https://github.com/nschloe/meshio), MIT, 2,342★, is `fogleman/sdf`'s format hub (probe used it for OBJ). `PyVista` ("Pythonic VTK… `mesh.save()` / `pyvista.read()`… filtering, plotting, trame") [https://github.com/pyvista/pyvista](https://github.com/pyvista/pyvista), MIT, 3,882★ — headless mesh QA/preview without Blender (`vedo` was already covered elsewhere and is intentionally not repeated).

## 4. Physics, sculpt, addons

**Blender built-ins (via existing `bpy` venv) — no new install.** Geometry Nodes can be scripted headless: `bpy.data.node_groups.new("…", "GeometryNodeTree")` + `nodes.new(...)` + `modifiers.new("…", "NODES")` [https://blog.cg-wire.com/blender-scripting-geometry-nodes-2](https://blog.cg-wire.com/blender-scripting-geometry-nodes-2); docs at [https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/). Cloth is "mass-less… Cloth modifier… drape a flat cloth over a table… Apply the modifier" [https://docs.blender.org/manual/en/latest/physics/cloth/introduction.html](https://docs.blender.org/manual/en/latest/physics/cloth/introduction.html) with Physical Properties (tension/bending/damping/pressure) [https://docs.blender.org/manual/en/latest/physics/cloth/settings/physical_properties.html](https://docs.blender.org/manual/en/latest/physics/cloth/settings/physical_properties.html); Soft Body adds "exterior forces + interior forces… simulate shapes… filled with something" [https://docs.blender.org/manual/en/latest/physics/soft_body/introduction.html](https://docs.blender.org/manual/en/latest/physics/soft_body/introduction.html). Logo use: cloth ribbon draped on the disc; soft-body pressure for wax-seal bulge. Bake/apply, then EEVEE hero. **PyBullet** (`loadSoftBody("cloth_z_up.obj", … useMassSpring …)` + `createSoftBodyAnchor` + `stepSimulation` + `getMeshData`) [https://github.com/bulletphysics/bullet3/blob/master/examples/pybullet/examples/deformable_anchor.py](https://github.com/bulletphysics/bullet3/blob/master/examples/pybullet/examples/deformable_anchor.py) (`pip install pybullet`), zlib — headless alternative when Blender sim is inconvenient.

## 5. Voxel, isometric, origami

**Voxel stack.** `Froxel` ("voxel editor with path tracer and MCP server… `froxel render --input x.vox --output x.png`" headless PNG, `.glb` with merged coplanar faces) [https://github.com/theromis/Froxel](https://github.com/theromis/Froxel), MIT, 7★ (very young, pushed 2026-11-10). `IsoVoxel` ("Generates isometric pixel art from MagicaVoxel .vox files… drag .vox onto IsoVoxel.exe → folder of PNGs") [https://github.com/tommyettinger/IsoVoxel](https://github.com/tommyettinger/IsoVoxel), MIT, 364★. `vox-format`/`vox-tool` ("command-line tool to inspect and manipulate VOX files… `print-info`/`set-palette`/`strip`") [https://github.com/jgraef/vox-format](https://github.com/jgraef/vox-format), MIT, 9★. Logo use: a voxel/isometric `C` icon variant, not the high-detail hero.

**Origami.** `pleat` ("Python library for constructing tilings and turning them into crease patterns… shrink-rotate… crossover to origami simulator" [https://imagirom.github.io/pleat](https://imagirom.github.io/pleat)) — PyPI 2026-07, MIT, 4★: Archimedean/Conway tilings → flat-foldable crease patterns → SVG/Cairo PNG. Logo use: folded-paper corner or ribbon accent on a paper-stock variant; do not let folds carry the identity. (Older alternates `rigid-origami`/FOLD solver exist but are less maintained; `pleat` is the current pick.)

## 6. Probe evidence (this Mac, `/tmp/logo3d-form/`)

### Probe A — fogleman/sdf wax-seal medallion (form + PNG)

Setup (own dir, own venv; reproducible):

```bash
mkdir -p /tmp/logo3d-form && cd /tmp/logo3d-form
git clone --depth 1 https://github.com/fogleman/sdf.git sdf   # then renamed sdf-src to avoid import shadowing
uv venv venv --python 3.13
uv pip install --python venv/bin/python -e ./sdf-src
./venv/bin/python -c "from sdf import measure_text, text; print('ok')"  # -> ok
```

Observed installs: `numpy==2.5.4 meshio==5.3.5 scikit-image==0.26.0 scipy==1.18.1 Pillow==13.0.0 sdf==0.1`. Script `/tmp/logo3d-form/medallion_sdf.py` builds: `rounded_cylinder(2.0, 0.06, 0.45)` disc + `torus(1.80, 0.07)` rim at `z=0.20` + `text("/tmp/logo3d/PlayfairDisplay-Black.ttf", "C", height=2.6).extrude(0.28)` at `z=0.30`, joined with smooth unions (`disc | rim.k(0.08) | letter.k(0.12)`), then `form.generate(samples=800_000)` + `form.save(...)` + matplotlib preview. Run:

```bash
./venv/bin/python medallion_sdf.py
# measure C: w=0.986 h=1.000
# min -2.11358, -2.11358, -0.426744 / max 2.11358, 2.11358, 0.663514 / step 0.0289853
# 877500 samples in 50 batches with 18 workers
# 89504 triangles in 0.16s (first run) / 0.10s (second)
# mesh V=(44754, 3) F=(89504, 3)
```

**Outputs:** `/tmp/logo3d-form/medallion_sdf.stl` (4.3M), `medallion_sdf.obj` (4.3M, via meshio), `medallion_sdf.png` (528K, **1264×1264 RGBA**, matplotlib blue `#1E4A7A` preview). Next step for a hero is `bpy.ops.wm.obj_import` of the OBJ → brand materials (blue enamel / gold rim / ivory C) → EEVEE; the matplotlib PNG proves the form, not the final shading.

### Probe B — gltf-transform delivery (optimize real CAD mesh)

Setup (own Bun project):

```bash
cd /tmp/logo3d-form/gltf && bun init -y && bun add @gltf-transform/cli
# installed @gltf-transform/cli@4.5.1 (bun 1.4.3)
```

Commands + observed output on the existing build123d-exported `/tmp/logo3d/cad_C.gltf` (JSON glTF, generator `Open CASCADE Technology 8.0`):

```bash
bunx @gltf-transform/cli inspect /tmp/logo3d/cad_C.gltf
# version 2.0 / 24,756 renderVertexCount / 4,926 vertices / 8,252 glPrimitives / 14 meshPrimitives / size 207.14 KB

bunx @gltf-transform/cli optimize /tmp/logo3d/cad_C.gltf /tmp/logo3d-form/cad_C_optimized.glb --compress quantize
# info: cad_C.gltf (214.99 KB) -> cad_C_optimized.glb (113.78 KB)
# generator glTF-Transform v4.5.1 (re-inspected)
```

**Output:** `/tmp/logo3d-form/cad_C_optimized.glb` (111K, ~47% smaller). Chain in production: SDF/CAD mesh → Blender GLB → `gltf-transform optimize --compress draco --texture-compress webp` (or `quantize`/`weld`/`simplify` per inspect report) [https://gltf-transform.donmccurdy.com/cli](https://gltf-transform.donmccurdy.com/cli).

## 7. Recommended chains for the mark

| Goal | Chain (all proven local) |
|------|--------------------------|
| Wax-seal medallion hero | `fogleman/sdf` smooth-union (disc + rim + `C`, `k=0.08–0.12`) → STL/OBJ → Blender EEVEE (enamel `#1E4A7A`, gold `#F2C14E`, ivory C) → `gltf-transform optimize --compress draco` |
| Web interactive medallion | `sdf-csg` or `@jscad/modeling` → three.js → `gltf-transform inspect/weld/quantize` |
| Crisp emboss on curved surface | FreeCAD Part sketch-on-face + fillet (verify in Blender) instead of SDF |
| Draped ribbon / wax bulge | Blender Cloth (ribbon) / Soft-Body pressure (wax) → Apply → EEVEE; PyBullet if headless sim preferred |
| Quad-clean hero | SDF mesh → `Instant Meshes` (or PyMeshLab isotropic remesh) → Blender Subdiv |
| Voxel / iso icon | MagicaVoxel/Froxel `.vox` → `IsoVoxel` PNGs (1×–3×) |
| Paper accent | `pleat` shrink-rotate crease pattern → SVG (plotter/laser) |
| Fast preview without Blender | `PyVista` offscreen render of the SDF STL |

**Needs user permission / do-not-proceed alone:** Manual GUI lanes (FreeCAD app install decision, TouchDesigner/Curv compiler builds) — prepare files, do not install or buy. **License care:** `libfive` has no LICENSE in repo (confirm before any commercial shipment); `retrace.gl` + `PyMeshLab` + `libigl.copyleft` are GPL — fine for internal assets, get sign-off before distributing binaries. Renders from GPL tools are not themselves copylefted, but bundled code is.
