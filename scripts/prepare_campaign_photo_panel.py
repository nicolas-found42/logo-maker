"""Build a blinded evaluation panel from previously unused, attributed photographs."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from logo_maker.campaign_calibration import _PAGE
from logo_maker.sampling_diagnostics import sha256
from logo_maker.study_render import digest


def prepare(project: Path, specification: Path, output: Path) -> None:
    spec = json.loads(specification.read_text())
    cases: list[dict[str, Any]] = sorted(spec["cases"], key=digest)
    with TemporaryDirectory(prefix=".photo-panel-", dir=output.parent) as temporary:
        staging = Path(temporary) / "panel"
        public = staging / "review"
        public.mkdir(parents=True)
        evidence, sections = {}, []
        board = Image.new("RGB", (1040, ((len(cases) + 1) // 2) * 230), "#f7f7f4")
        draw = ImageDraw.Draw(board)
        credits = {}
        for index, case in enumerate(cases):
            cid = f"{index + 1:02d}"
            feature = case["feature_name"]
            draw.text(
                ((index % 2) * 520 + 8, (index // 2) * 230 + 6),
                f"{cid}  {feature}",
                fill="#212622",
                font_size=16,
            )
            files, figures, source = {}, [], {}
            for pos, role in enumerate(("candidate_detail", "reference_detail")):
                item = case[role]
                receipt = json.loads((project / item["receipt"]).read_text())
                image_path = project / receipt["path"]
                if sha256(image_path) != receipt["sha256"]:
                    raise ValueError(f"source photo changed: {image_path}")
                credits[receipt["url"]] = {k: receipt[k] for k in ("source", "license", "url")}
                name = f"{cid}-{role}.png"
                with Image.open(image_path) as image:
                    photo = ImageOps.exif_transpose(image).convert("RGB")
                    box = tuple(
                        round(a * b) for a, b in zip(item["crop"], photo.size * 2, strict=True)
                    )
                    crop = photo.crop(box)
                    crop.thumbnail((1400, 1400))
                    crop.save(public / name)
                x = (index % 2) * 520 + pos * 260
                y = (index // 2) * 230
                crop.thumbnail((246, 174))
                board.paste(crop, (x + (260 - crop.width) // 2, y + 31))
                title = ("Design", "Reference")[pos]
                draw.text((x + 8, y + 208), title, fill="#212622", font_size=12)
                files[role] = {"file": name, "sha256": sha256(public / name)}
                source[role] = {**receipt, "crop": item["crop"]}
                figures.append(
                    f'<figure><a href="{name}"><img src="{name}" alt="{title}"></a>'
                    f"<figcaption>{title}</figcaption></figure>"
                )
            evidence[cid] = {
                "feature": case["feature"],
                "feature_name": feature,
                "files": files,
                "source": source,
                "view_sha256": source["candidate_detail"]["sha256"],
                "intended_appearances": {
                    "candidate": "An intact, fully formed object with a consistent material finish.",
                    "reference": "A comparable formed feature on a real object.",
                },
            }
            sections.append(
                f"<section><h2>{cid} · {html.escape(feature)}</h2>"
                f'<div class="pair">{"".join(figures)}</div></section>'
            )
        (staging / "evidence.json").write_text(
            json.dumps({"schema": 1, "partition": "held_out", "cases": evidence}, indent=2) + "\n"
        )
        (staging / "attribution.json").write_text(
            json.dumps(list(credits.values()), indent=2) + "\n"
        )
        (public / "index.html").write_text(_PAGE + "".join(sections) + "</html>\n")
        board.save(public / "overview.jpg", quality=92)
        staging.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("specification", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.project, args.specification, args.output)
