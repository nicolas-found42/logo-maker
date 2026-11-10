import json
from pathlib import Path

from logo_maker.motif import Motif

data = json.loads(Path("geometry.json").read_text())
m = Motif()
for part in data["parts"]:
    m.add(
        part["id"],
        m.polygon([tuple(p) for p in part["points"]]),
        fill={"primary": "#245064", "secondary": "#B87E48"}[part["role"]],
        role=part["role"],
    )
m.save(".")
