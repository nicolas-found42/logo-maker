"""three.js alternate renderer: scene export -> lit RGBA PNG via headless Chrome.

Serves the repo `js/` directory over a local HTTP server (so the page can
use ES modules, fetch, and the glb), stages a session dir with the glb plus
a Y-up converted `config.json`, and screenshots `js/three-page.html` with
Playwright (`channel: "chrome"`). Materials come from the glb itself as
`MeshPhysicalMaterial`; the HDRI lights the scene via RGBELoader+PMREM and
`RoomEnvironment` is the fallback. pmndrs `postprocessing` EffectComposer
with N8AO ambient occlusion (and optional bloom for emissive scenes)
grades the frame; plain WebGL rendering is the fallback.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path

from logo_maker.paths import JS_DIR
from logo_maker.proc import ToolError, node
from logo_maker.renderers import load_export, resolve, scaled_size, spp_for


def _zup_to_yup(values) -> list[float]:
    """Blender/PLY Z-up world coords -> three.js Y-up: (x, y, z) -> (x, z, -y)."""
    x, y, z = (float(v) for v in values)
    return [x, z, -y]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def render(export_json: Path, out_png: Path, *, quality: str, resolution: int) -> Path:
    """Render the scene export with three.js to an RGBA PNG."""
    import sys

    spp_for(quality)  # validated for signature parity; three.js is not sample-based
    data, concept_dir = load_export(export_json)
    width, height = scaled_size(data, resolution)
    camera = data.get("camera", {})
    world = data.get("world", {})

    glb_src = resolve(concept_dir, data.get("glb", "model.glb"))
    if not glb_src.is_file():
        raise FileNotFoundError(f"glb not found: {glb_src}")

    session_id = f".three-tmp/{uuid.uuid4().hex[:12]}"
    session_dir = JS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    hdri_name: str | None = None
    try:
        shutil.copyfile(glb_src, session_dir / "model.glb")
        hdri = world.get("hdri")
        if hdri and not world.get("transparent", True):
            # Opaque renders may use the HDRI for image-based lighting.
            src = resolve(concept_dir, hdri)
            if src.is_file():
                hdri_name = "env" + src.suffix.lower()
                shutil.copyfile(src, session_dir / hdri_name)
        config = {
            "width": width,
            "height": height,
            "camera": {
                "location": _zup_to_yup(camera.get("location", (0, -3, 2))),
                "target": _zup_to_yup(camera.get("target", (0, 0, 0))),
                "up": _zup_to_yup(camera.get("up", (0, 0, 1))),
                "fov_deg": float(camera.get("fov_deg", 35.0)),
            },
            "lights": [
                {
                    "type": light.get("type", "point"),
                    "location": _zup_to_yup(light.get("location", (0, 0, 5))),
                    "target": _zup_to_yup(light.get("target", (0, 0, 0))),
                    "size": float(light.get("size", 1.0)),
                    "power_w": float(light.get("power_w", 10.0)),
                    "color_linear": [float(v) for v in light.get("color_linear", (1.0, 1.0, 1.0))],
                }
                for light in data.get("lights", [])
            ],
            "hdri": hdri_name,
            "env_strength": float(world.get("strength", 1.0) or 0.0),
            "bloom": any(
                float(
                    data.get("materials", {})
                    .get(obj.get("material", ""), {})
                    .get("emission_strength", 0.0)
                )
                > 0
                for obj in data.get("objects", [])
            ),
        }
        (session_dir / "config.json").write_text(json.dumps(config))

        port = _free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=JS_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            url = f"http://127.0.0.1:{port}/three-page.html?session={session_id}"
            deadline = time.time() + 20
            while time.time() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.1)
            out_png.parent.mkdir(parents=True, exist_ok=True)
            node(
                "three-render",
                {
                    "url": url,
                    "out_png": str(out_png.absolute()),
                    "width": width,
                    "height": height,
                },
                timeout=600,
            )
        finally:
            server.terminate()
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)
    if not out_png.is_file():
        raise ToolError(f"three.js finished without writing {out_png}")
    return out_png
