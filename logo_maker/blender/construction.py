"""Measure authored construction assertions on a packed editable scene."""

from __future__ import annotations

import math
from pathlib import Path

from logo_maker.blender.study import _campaign_static, _open_scene
from logo_maker.host import serve
from logo_maker.sampling_diagnostics import sha256


def check(payload: dict) -> dict:
    path = Path(payload["source"])
    source_digest = sha256(path)
    scene = _open_scene(path, False)
    import bpy
    from mathutils import Vector

    _campaign_static(scene)
    graph = bpy.context.evaluated_depsgraph_get()
    rows = {}
    for test in payload["rays"]:
        key = test["id"]
        expected = test["expect"]
        origin, direction = test["origin"], test["direction"]
        distance = test["distance"]
        if (
            not isinstance(key, str)
            or not key.strip()
            or key in rows
            or expected not in ("open", "hit")
            or len(origin) != 3
            or len(direction) != 3
            or not all(math.isfinite(v) for v in (*origin, *direction, distance))
            or distance <= 0
            or not any(direction)
        ):
            raise ValueError("invalid or duplicate construction ray assertion")
        hit, position, _, _, obj, _ = scene.ray_cast(
            graph, Vector(origin), Vector(direction).normalized(), distance=distance
        )
        rows[key] = {
            "expected": expected,
            "hit": obj.name if hit else None,
            "position": list(position) if hit else None,
            "status": "pass"
            if (expected == "open" and not hit)
            or (
                expected == "hit" and hit and (not test.get("object") or obj.name == test["object"])
            )
            else "fail",
        }
    if sha256(path) != source_digest:
        raise ValueError("scene changed during construction verification")
    return {"scene_sha256": source_digest, "checks": rows}


if __name__ == "__main__":
    serve(check)
