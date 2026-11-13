# Adapters

Every external tool logo-maker runs, generated from `logo_maker/adapters/` by `scripts/gen_docs.py`.
`logo-maker doctor` runs each check; the fix column is what it prints when a check fails.

## Judgment

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| jev (TypeSafe) | proprietary API | calibrated yes/no, choice, and score judgments over briefs, concepts, and renders | `logo_maker.jev.client:JevClient` | `export OPENROUTER_API_KEY=<key>  # or TYPESAFE_API_KEY=<key> for direct TypeSafe` |

## Motif 2d

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| fontTools | MIT | Google Fonts download, variable-axis instancing, and text outlines | `logo_maker.fonts:resolve` | `just setup` |
| skia-pathops | BSD-3-Clause | booleans, stroking, and overlap removal behind motif geometry | `logo_maker.motif:union` | `just setup` |
| drawsvg | MIT | writes the contract-clean motif.svg document | `logo_maker.motif:Motif.save` | `just setup` |
| resvg-py | MPL-2.0 | rasters motif.svg to PNG previews at any size | `logo_maker.motif:rasterize` | `just setup` |
| Pillow | MIT-CMU | composes size sheets and prepares reference images | `logo_maker.motif:size_sheet` | `just setup` |
| vtracer | MIT | traces use='geometry' references to SVG paths | `logo_maker.trace:trace` | `just setup` |
| vpype | MIT | merges and simplifies line art before it is outlined to fills | `logo_maker.twod_tools:plotter_lines` | `just setup` |
| FontForge | GPL-3.0-or-later | builds ligature glyphs from component glyphs and exports outlines | `logo_maker.twod_tools:fontforge_glyphs` | `brew install fontforge` |
| primitive | MIT | geometric image abstraction into shapes | `logo_maker.twod_tools:primitive_abstract` | `go install github.com/fogleman/primitive@latest and add $(go env GOPATH)/bin to PATH` |
| rough.js+svg2roughjs | MIT | hand-drawn wobble of motif paths (generator ops; strokes outlined to fills) | `logo_maker.twod_tools:sketchy` | `just setup` |
| perfect-freehand | MIT | pressure-sensitive stroke outlines | `logo_maker.twod_tools:freehand` | `just setup` |
| d3-delaunay | ISC | Voronoi cells and Delaunay triangles | `logo_maker.twod_tools:voronoi` | `just setup` |
| trianglify | GPL-3.0 | low-poly triangle fields from pattern point/poly data (no DOM) | `logo_maker.twod_tools:low_poly` | `just setup` |
| heerich | MIT | voxel scenes rendered to SVG polygons | `logo_maker.twod_tools:voxels` | `just setup` |
| Google Fonts | OFL-1.1 AND Apache-2.0 AND UFL | variable font files (OFL-1.1, Apache-2.0, or UFL per family) with cached licenses | `logo_maker.fonts:resolve` | `just setup` |

## Color type

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| coloraide | MIT | WCAG 2.1 contrast ratios that gate palettes before jev ever sees them | `logo_maker.palette:contrast` | `uv sync` |

## Geometry 3d

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| Blender cloth | GPL-3.0-or-later | Physics drape for ribbon components (analytic wave fallback) | `logo_maker.blender.components:_drape_ribbon` | `uv sync (ships with bpy)` |
| manifold3d | Apache-2.0 | Watertight extrusion triangulation and mesh booleans | `logo_maker.geometry:boolean_mesh` | `uv sync` |
| trimesh | MIT | Mesh assembly, transforms, and PLY export | `logo_maker.geometry:save_ply` | `uv sync` |
| PyMeshLab | GPL-3.0-or-later | Isotropic remeshing for inflated (SDF) meshes | `logo_maker.geometry:inflate_mesh` | `uv sync` |
| build123d | Apache-2.0 | Parametric CAD solids for cad components | `logo_maker.geometry:cad_mesh` | `uv sync` |
| fogleman/sdf | MIT | Signed-distance-field sampling for soft inflated forms | `logo_maker.geometry:inflate_mesh` | `uv sync` |

## Materials lighting

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| Poly Haven | CC0-1.0 | HDRI environment maps via api.polyhaven.com | `logo_maker.hdri:_polyhaven` | `uv sync (httpx); downloads need network, scenes fall back to hdri = "none"` |
| ambientCG | CC0-1.0 | HDRI environment maps via the ambientCG API v3 | `logo_maker.hdri:_ambientcg` | `uv sync (httpx); downloads need network, scenes fall back to hdri = "none"` |

## Rendering

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| bpy/Cycles (Metal) | GPL-3.0-or-later (Blender) / Apache-2.0 (Metal backend use) | Renders every scene on the Apple Silicon GPU | `logo_maker.render:_run_builder` | `uv sync (installs bpy==5.2.3)` |
| OIDN | Apache-2.0 | GPU denoiser for Cycles previews and finals | `logo_maker.blender.settings:apply_quality` | `uv sync (ships with bpy)` |
| Line Art | GPL-3.0-or-later | Outline strokes for toon and lineart looks (Freestyle fallback) | `logo_maker.blender.components:setup_outlines` | `uv sync (ships with bpy)` |
| compositor glare/DOF | GPL-3.0-or-later | Bloom glare mix and camera depth of field when the scene asks | `logo_maker.blender.components:setup_compositor` | `uv sync (ships with bpy)` |
| sysctl (macOS hardware identity) | BSD-3-Clause | reads hardware and OS-build fields for sampling profile invalidation | `logo_maker.blender.profile:environment` | `restore /usr/sbin/sysctl from macOS system tools and include /usr/sbin on PATH` |
| Mitsuba 3 | BSD-3-Clause | alternate PBR renderer (principled BSDF, rect/point/sun lights) | `logo_maker.renderers.mitsuba:render` | `uv sync` |
| LuxCoreRender | Apache-2.0 | alternate unbiased renderer (disney, PATHCPU, alpha film output) | `logo_maker.renderers.luxcore:render` | `uv sync` |
| three.js | MIT | WebGL renderer for the glb (RoomEnvironment/HDRI, physical lights) | `logo_maker.renderers.three:render` | `just setup (runs npm ci in js/)` |
| postprocessing | Zlib | EffectComposer grading for the three.js renderer | `logo_maker.renderers.three:render` | `just setup (runs npm ci in js/)` |
| N8AO | ISC | screen-space ambient occlusion pass for the three.js renderer | `logo_maker.renderers.three:render` | `just setup (runs npm ci in js/)` |
| Playwright (Chrome) | Apache-2.0 | headless Chrome screenshots for the three.js renderer | `logo_maker.renderers.three:render` | `install Google Chrome; just setup (runs npm ci in js/)` |

## Post export

| Tool | License | Use | Entry | Fix |
|---|---|---|---|---|
| ps (system process status) | BSD-3-Clause OR GPL-2.0-or-later | distinguishes stopped zombie groups from denied live export work | `logo_maker.owned_process:_group_has_live_members` | `restore /bin/ps from macOS system tools or Linux procps` |
| OpenImageIO | Apache-2.0 | lanczos3 premultiplied-alpha-correct downsampling | `logo_maker.imageops:downsample` | `uv sync` |
| SVGO | MIT | SVG optimization for the mark exports | `logo_maker.export:optimize_svg` | `just setup (runs npm ci in js/)` |
| favicons | MIT | installability meta: manifest icons, ms tiles, browserconfig | `logo_maker.export:favicons_meta` | `just setup (runs npm ci in js/)` |
| pwa-asset-generator | MIT | app icons, no splash screens (drives Chrome itself) | `logo_maker.export:pwa_assets` | `just setup (runs npm ci in js/)` |
| gltf-transform | MIT | glb pipeline (dedup/prune/draco) | `logo_maker.export:draco_compress` | `just setup (runs npm ci in js/)` |
| Draco | Apache-2.0 | mesh compression codec for model.glb | `logo_maker.export:draco_compress` | `just setup (runs npm ci in js/)` |
| Chrome | proprietary | browser driven by pwa-asset-generator | `logo_maker.export:pwa_assets` | `install Google Chrome` |
