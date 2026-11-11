import json
from pathlib import Path

from logo_maker.motif import Motif

data = json.loads(Path("geometry.json").read_text())
m = Motif()
colors = {"primary": "#285640", "secondary": "#DCE7D6"}
for i, part in enumerate(data["parts"]):
    m.add(
        part["id"],
        m.polygon([tuple(p) for p in part["points"]]),
        fill=colors[part["role"]],
        role=part["role"],
        height=1,
        layer=i,
    )
m.save(".")
