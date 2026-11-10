"""Adapters for the render + export slice: alternate renderers and export tooling."""

from __future__ import annotations

import shutil
from pathlib import Path

from logo_maker.adapters import Adapter, binary, node_package, python_module


def _chrome() -> str | None:
    if shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium"):
        return None
    if Path("/Applications/Google Chrome.app").exists():
        return None
    return "chrome not found (checked PATH and /Applications)"


def _playwright_chrome() -> str | None:
    from logo_maker.paths import JS_DIR

    if not (JS_DIR / "node_modules" / "playwright-core" / "package.json").exists():
        return "js/node_modules/playwright-core missing"
    return _chrome()


ADAPTERS: list[Adapter] = [
    Adapter(
        "ps (system process status)",
        "post_export",
        "BSD-3-Clause OR GPL-2.0-or-later",
        "distinguishes stopped zombie groups from denied live export work",
        "logo_maker.export:_export_group_has_live_members",
        binary("/bin/ps"),
        "restore /bin/ps from macOS system tools or Linux procps",
    ),
    Adapter(
        "Mitsuba 3",
        "rendering",
        "BSD-3-Clause",
        "alternate PBR renderer (principled BSDF, rect/point/sun lights)",
        "logo_maker.renderers.mitsuba:render",
        python_module("mitsuba"),
        "uv sync",
    ),
    Adapter(
        "LuxCoreRender",
        "rendering",
        "Apache-2.0",
        "alternate unbiased renderer (disney, PATHCPU, alpha film output)",
        "logo_maker.renderers.luxcore:render",
        python_module("pyluxcore"),
        "uv sync",
    ),
    Adapter(
        "three.js",
        "rendering",
        "MIT",
        "WebGL renderer for the glb (RoomEnvironment/HDRI, physical lights)",
        "logo_maker.renderers.three:render",
        node_package("three"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "postprocessing",
        "rendering",
        "MIT",
        "EffectComposer grading for the three.js renderer",
        "logo_maker.renderers.three:render",
        node_package("postprocessing"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "N8AO",
        "rendering",
        "MIT",
        "screen-space ambient occlusion pass for the three.js renderer",
        "logo_maker.renderers.three:render",
        node_package("n8ao"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "Playwright (Chrome)",
        "rendering",
        "Apache-2.0",
        "headless Chrome screenshots for the three.js renderer",
        "logo_maker.renderers.three:render",
        _playwright_chrome,
        "install Google Chrome; just setup (runs npm ci in js/)",
    ),
    Adapter(
        "OpenImageIO",
        "post_export",
        "Apache-2.0",
        "lanczos3 premultiplied-alpha-correct downsampling",
        "logo_maker.imageops:downsample",
        python_module("OpenImageIO"),
        "uv sync",
    ),
    Adapter(
        "SVGO",
        "post_export",
        "MIT",
        "SVG optimization for the mark exports",
        "logo_maker.export:optimize_svg",
        node_package("svgo"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "favicons",
        "post_export",
        "MIT",
        "installability meta: manifest icons, ms tiles, browserconfig",
        "logo_maker.export:favicons_meta",
        node_package("favicons"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "pwa-asset-generator",
        "post_export",
        "Apache-2.0",
        "app icons + splash screens (drives Chrome itself)",
        "logo_maker.export:pwa_assets",
        node_package("pwa-asset-generator"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "gltf-transform",
        "post_export",
        "Apache-2.0",
        "glb pipeline (dedup/prune/draco)",
        "logo_maker.export:draco_compress",
        node_package("@gltf-transform/functions"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "Draco",
        "post_export",
        "Apache-2.0",
        "mesh compression codec for model.glb",
        "logo_maker.export:draco_compress",
        node_package("draco3dgltf"),
        "just setup (runs npm ci in js/)",
    ),
    Adapter(
        "Chrome",
        "post_export",
        "proprietary",
        "browser driven by pwa-asset-generator",
        "logo_maker.export:pwa_assets",
        _chrome,
        "install Google Chrome",
    ),
]
