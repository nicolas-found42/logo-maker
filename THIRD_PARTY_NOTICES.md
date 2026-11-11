# Third-party notices

logo-maker is MIT-licensed. It installs and runs these components under their own licenses; none of
their source is vendored here.

| Component | License | How logo-maker uses it |
|---|---|---|
| [System sysctl (macOS)](https://github.com/apple-oss-distributions/system_cmds/blob/main/sysctl/sysctl.c) | BSD-3-Clause | Read-only machine/build profile fields; invoked externally, not vendored |
| System ps (macOS BSD / Linux procps) | BSD-3-Clause / GPL-2.0-or-later | Process-state inspection after denied export-group signals; invoked externally, not vendored |
| bpy (Blender as a Python module) | GPL-3.0-or-later | Scene building and Cycles rendering, in a subprocess |
| PyMeshLab | GPL-3.0 | Remeshing generated solids |
| FontForge | GPL-3.0-or-later | Glyph operations via `fontforge -script` subprocess |
| trianglify | GPL-3.0 | Low-poly pattern generation via a Node subprocess |
| LuxCoreRender (pyluxcore) | Apache-2.0 | Alternate renderer |
| Mitsuba 3 | BSD-3-Clause | Alternate renderer |
| three.js, postprocessing, N8AO | MIT | Alternate real-time renderer in headless Chrome |
| fogleman/primitive | MIT | Shape-based abstraction of style references |
| Google Fonts families | OFL-1.1 / Apache-2.0 / UFL-1.0 | Downloaded to the cache on use; license recorded per logo in run.json |
| Poly Haven and ambientCG assets | CC0-1.0 | HDRIs and textures downloaded to the cache on use; recorded in run.json |
| Jev (TypeSafe) | Proprietary API | Judgments; requests and answers logged per logo |

Exports a logo-maker run produces belong to the brief's owner. Fonts embedded as outlines in exported
SVGs remain under their font licenses, which permit this use.
