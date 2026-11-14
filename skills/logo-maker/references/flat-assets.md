# Flat logos, favicons and avatars

## Decide what to keep

Read the user's request and the project for the exact name, what it does, where the mark will be
seen and any existing identity. A one-sentence brief is enough when those facts are clear. Choose
a design direction from that evidence. Make a few distinct silhouettes when a comparison will
help, and show actual images in the requested context. When resizing or repackaging an existing
logo, preserve its authoritative artwork. Ask about a simplified icon only if the supplied mark
cannot meet a requested use without changing its identity.

Work in a fresh absolute folder. Keep the original input and put generated variants beside it
or under a separate deliverable folder. Use the logo-maker Python environment:

```sh
uv run --locked --project "$maker_repo" python -c 'from logo_maker.motif import Motif, rasterize, size_sheet; from PIL import Image'
```

If the imports fail or the 3D environment cannot install on this host, follow the
[minimal flat setup](setup.md#when-a-working-checkout-is-missing).

## Make or reuse the master

- **New art.** Write `motif.py` with [the motif API](motif-api.md). Use a 1000 × 1000 canvas, a
  clear silhouette, and meaningful proportions. Try a simple fill, hole or letterform first.
  Use the brand's colors or select a small palette from the brief. Keep text legible, with a
  separate lockup when the complete wordmark cannot read at icon sizes.
- **Exact supplied SVG.** Preserve the original as the vector deliverable. For resized versions
  of self-contained SVG artwork, use [the resize recipe](#resize-an-original-svg-without-rewriting-it)
  and inspect fidelity, dimensions and padding. A non-square wordmark may need transparent
  padding for square uses. Use the contract-clean workflow for a copy meant to feed the 3D tool.
  Convert text to outlines, expand strokes and bake transforms in that copy. Compare against
  the original.
- **Supplied raster.** Preserve the image for exact resize jobs. When the user authorizes
  deriving geometry from the image, `logo_maker.trace.trace(path, mode="geometry")` followed by
  `trace.shapes(svg_text)` supplies path/color pairs. Group parts and apply one consistent fit
  transform so they stay aligned. Check the trace against the original. For style references,
  derive new geometry from the brief. See [concept authoring](concepts.md) for reference roles.

## Build and check

For a generated motif or a contract-clean SVG, set `maker_repo` to the checkout and `concept_dir`
to the absolute working folder holding `motif.py` or `motif.svg`. Run the following and adapt the
sizes, names and formats to the request. A non-contract original uses the exact-artwork route above.

```sh
uv run --locked --project "$maker_repo" python - "$concept_dir" <<'PY'
import sys
from pathlib import Path

from PIL import Image
from logo_maker.motif import rasterize, run_motif_script, size_sheet, validate

folder = Path(sys.argv[1]).resolve()
svg = folder / "motif.svg"
if (folder / "motif.py").is_file():
    svg = run_motif_script(folder)
problems = validate(svg)
if problems:
    raise SystemExit("\n".join(problems))

size_sheet(svg, folder / "motif-sizes.png")
for size in (16, 32, 48, 180, 512):
    rasterize(svg, size, folder / f"favicon-{size}.png")
with (
    Image.open(folder / "favicon-48.png") as large,
    Image.open(folder / "favicon-16.png") as small,
    Image.open(folder / "favicon-32.png") as medium,
):
    large.save(
        folder / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[small, medium],
    )
PY
```

For a flat avatar, rasterize the motif at the requested size with the intended background and
check a circle crop. For a monochrome option, use `motif.mono` and inspect the silhouette and
negative space on the intended surface. Keep the build source so the next revision remains editable.

Open the size sheet and the requested output at its real size. Check that the 16 and 32 px
versions read on the intended backgrounds, that app and avatar crop masks leave breathing room,
and that a preserved mark matches the input. Show a preview and link the requested files. These
are flat assets. They can be complete for a flat-only request or carry forward into a 3D job as
the shared mark. Keep them outside the pipeline's qualified `exports/` folder.

## Resize an original SVG without rewriting it

Use this for self-contained artwork with its fonts outlined or available to resvg. Set
`source_svg` to the original path, `output_png` to a new path, and `size_px` to the requested square
size. The artwork keeps its aspect ratio. Choose the amount of padding for the intended crop.

```sh
uv run --locked --project "$maker_repo" python - "$source_svg" "$output_png" "$size_px" <<'PY'
import io
import sys
from pathlib import Path

import resvg_py
from PIL import Image

source, output = map(Path, sys.argv[1:3])
size = int(sys.argv[3])
if size <= 0 or output.suffix.lower() != ".png" or source.resolve() == output.resolve():
    raise SystemExit("Choose a positive size and a separate .png output path")

art = resvg_py.svg_to_bytes(svg_path=str(source), width=size, height=size)
with Image.open(io.BytesIO(art)) as original:
    image = original.convert("RGBA")
image.thumbnail((size, size), Image.Resampling.LANCZOS)
canvas = Image.new("RGBA", (size, size))
canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
output.parent.mkdir(parents=True, exist_ok=True)
canvas.save(output)
PY
```

Open the original and resized asset side by side. When the original depends on missing fonts
or external resources, obtain a self-contained export before claiming fidelity. For a raster
original, use Pillow to resize and center a copy in the same way. Inspect transparency, small
details and clipping at the actual output size.
