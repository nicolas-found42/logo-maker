"""Export set: hero/avatar/favicon/SVG/PWA/glTF/contact sheet plus a manifest.

`export_all` turns one concept (its `final.png`, `motif.svg`, and optional
`model.glb`/`scene.blend`) into the shippable `exports/` set. Every raster
derives from either the transparent hero or the flat motif, so flat and 3D
always match. Raises `ExportError` when the hero fails its alpha check.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from logo_maker.checks import OBJECT_ALPHA, alpha_report, margin_report
from logo_maker.imageops import downsample, pad_square, soft_shadow
from logo_maker.proc import node
from logo_maker.sampling import Budget, SamplingLimit

HERO_SIZE = 2000
AVATAR_SIZE = 1024
# The mark's bbox must fit inside this fraction of the avatar's inscribed circle.
AVATAR_CIRCLE_FILL = 0.88
PAPER_TONE = "#F4F1EA"
FAVICON_SIZES = (16, 32, 48, 180, 512)


class ExportError(RuntimeError):
    """An export input failed its QA check or a step could not be produced."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rasterize_flat(
    svg_path: Path, size: int, out_path: Path, *, background: str | None = None
) -> Path:
    """Render the flat motif SVG at `size` px square (transparent unless set).

    Uses `logo_maker.motif.rasterize` when the 2D slice has landed, else
    resvg directly; both take an optional background color.
    """
    try:
        from logo_maker import motif as motif_module

        rasterize = getattr(motif_module, "rasterize", None)
        if rasterize is not None:
            return Path(rasterize(svg_path, size, out_path, background=background))
    except ImportError:
        pass
    import resvg_py

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(
        resvg_py.svg_to_bytes(
            svg_path=str(svg_path), width=size, height=size, background=background
        )
    )
    return out_path


def _mono_svg_text(svg_path: Path, ink: str) -> str:
    """Recolor every fill in the motif to `ink` (mono export keeps roles as info)."""
    try:
        from logo_maker import motif as motif_module

        mono = getattr(motif_module, "mono", None)
        if mono is not None:
            out = svg_path.with_name(svg_path.stem + ".mono-tmp.svg")
            mono(svg_path, ink, out)
            text = out.read_text()
            out.unlink(missing_ok=True)
            return text
    except ImportError:
        pass
    text = svg_path.read_text()
    text = re.sub(r'fill="#[0-9A-Fa-f]{3,8}"', f'fill="{ink}"', text)
    text = re.sub(r"fill='#[0-9A-Fa-f]{3,8}'", f"fill='{ink}'", text)
    return text


def optimize_svg(src: Path, dst: Path) -> Path:
    """SVGO-optimize `src` to `dst` via js/svgo.mjs (adapter entry: export:optimize_svg)."""
    node("svgo", {"input": str(Path(src)), "output": str(Path(dst))})
    return Path(dst)


def draco_compress(src: Path, dst: Path, *, compression_level: int = 7) -> Path:
    """Draco-compress a glb via js/gltf.mjs (adapter entry: export:draco_compress)."""
    node(
        "gltf",
        {"input": str(Path(src)), "output": str(Path(dst)), "compression_level": compression_level},
    )
    return Path(dst)


def favicons_meta(
    source: Path,
    out_dir: Path,
    *,
    app_name: str,
    background: str,
    theme_color: str,
    manifest_name: str = "manifest.webmanifest",
) -> list[str]:
    """Android manifest icons + Windows tiles via js/favicons.mjs."""
    result = node(
        "favicons",
        {
            "source": str(Path(source)),
            "out_dir": str(Path(out_dir)),
            "app_name": app_name,
            "background": background,
            "theme_color": theme_color,
            "manifest_name": manifest_name,
        },
    )
    return list(result.get("files", []))


def pwa_assets(
    source: Path,
    out_dir: Path,
    *,
    manifest_name: str = "manifest.json",
    background: str = "transparent",
    opaque: bool = False,
) -> dict:
    """App icons + splash screens via js/pwa.mjs; manifest srcs made relative."""
    out = Path(out_dir)
    result = node(
        "pwa",
        {
            "source": str(Path(source)),
            "out_dir": str(out),
            "manifest": str(out / manifest_name),
            "background": background,
            "opaque": opaque,
        },
    )
    manifest_path = out / manifest_name
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        for icon in manifest.get("icons", []):
            icon["src"] = Path(str(icon.get("src", ""))).name
        manifest_path.write_text(json.dumps(manifest, indent=2))
    return result


def _paper(palette: dict[str, str]) -> str:
    return palette.get("background", PAPER_TONE)


def _ink(palette: dict[str, str]) -> str:
    return palette.get("ink") or palette.get("primary", "#111111")


def _hero(concept_dir: Path, out_dir: Path) -> Path:
    final = Path(concept_dir) / "final.png"
    if not final.is_file():
        raise ExportError(f"no final render at {final}")
    hero = Path(out_dir) / "hero-transparent.png"
    downsample(final, out_dir / ".hero-long.png", HERO_SIZE)
    pad_square(out_dir / ".hero-long.png", hero, HERO_SIZE)
    (out_dir / ".hero-long.png").unlink(missing_ok=True)
    report = alpha_report(hero)
    if report["bbox"] is None:
        raise ExportError(f"{hero.name}: render is fully transparent")
    if report["veil"]:
        raise ExportError(
            f"{hero.name}: background veil detected (haze_fraction={report['haze_fraction']:.3f})"
        )
    margins = margin_report(hero)
    if margins["cut_off"]:
        raise ExportError(f"{hero.name}: object touches the frame {margins['margins']}")
    return hero


def _hero_on_paper(hero: Path, out_dir: Path, paper: str, *, shadow: bool) -> Path:
    """Hero flattened onto `paper`, with a soft drop shadow when asked."""
    name = "hero-paper.png" if shadow else ".pwa-source.png"
    dst = Path(out_dir) / name
    with Image.open(hero) as mark:
        rgba = mark.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, paper)
    if shadow:
        layer = soft_shadow(hero)
        ox, oy = 0, 18
        canvas.alpha_composite(layer, (ox, oy))
    canvas.alpha_composite(rgba, (0, 0))
    canvas.convert("RGB").save(dst)
    return dst


def _avatar(hero: Path, out_dir: Path, paper: str) -> Path:
    """Circle-safe avatar: the mark's bbox fits the inscribed circle, on `paper`."""
    import numpy as np

    dst = Path(out_dir) / "avatar-1024.png"
    with Image.open(hero) as mark:
        rgba = mark.convert("RGBA")
    alpha = np.asarray(rgba)[:, :, 3]
    ys, xs = np.nonzero(alpha >= OBJECT_ALPHA)
    if len(xs) == 0:
        raise ExportError("hero is fully transparent; cannot build avatar")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    half_diag = float(np.hypot(x1 - x0, y1 - y0) / 2)
    radius = AVATAR_SIZE / 2 * AVATAR_CIRCLE_FILL
    scale = radius / max(half_diag, 1e-6)
    fitted = rgba.resize(
        (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), paper)
    cx, cy = (x0 + x1) / 2 * scale, (y0 + y1) / 2 * scale
    canvas.alpha_composite(fitted, (round(AVATAR_SIZE / 2 - cx), round(AVATAR_SIZE / 2 - cy)))
    canvas.convert("RGB").save(dst)
    return dst


def _favicons(motif_svg: Path, out_dir: Path) -> dict[str, Path]:
    """Favicon PNGs + ICO from the flat motif (exact pixel sizes)."""
    out = Path(out_dir)
    paths: dict[str, Path] = {}
    for size in FAVICON_SIZES:
        dst = out / f"favicon-{size}.png"
        _rasterize_flat(motif_svg, size, dst)
        paths[f"favicon-{size}"] = dst
    png48 = Image.open(paths["favicon-48"]).convert("RGBA")
    ico = out / "favicon.ico"
    png48.save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    paths["favicon-ico"] = ico
    return paths


def _svgs(motif_svg: Path, out_dir: Path, ink: str) -> dict[str, Path]:
    out = Path(out_dir)
    color = out / "mark-color.svg"
    shutil.copyfile(motif_svg, out / ".mark-color.src.svg")
    optimize_svg(out / ".mark-color.src.svg", color)
    (out / ".mark-color.src.svg").unlink(missing_ok=True)
    mono_src = out / ".mark-mono.src.svg"
    mono_src.write_text(_mono_svg_text(motif_svg, ink))
    mono = out / "mark-mono.svg"
    optimize_svg(mono_src, mono)
    mono_src.unlink(missing_ok=True)
    return {"mark-color": color, "mark-mono": mono}


def _contact_sheet(
    entries: list[tuple[str, Path]], dst: Path, *, mono_background: str = "#FFFFFF"
) -> Path:
    """One labeled sheet of the export set (thumbs at 384 px, three columns).

    The mono mark is a one-color silhouette in the brand ink, so its chip uses
    the brand background — the surface the ink is designed for.
    """
    thumbs: list[tuple[str, Image.Image]] = []
    for label, path in entries:
        background = mono_background if label == "mark-mono" else "#FFFFFF"
        if path.suffix.lower() == ".svg":
            tmp = dst.parent / f".sheet-{len(thumbs)}.png"
            _rasterize_flat(path, 384, tmp, background=background)
            thumb = Image.open(tmp).convert("RGB")
            tmp.unlink(missing_ok=True)
        else:
            with Image.open(path) as im:
                rgba = im.convert("RGBA")
            thumb = Image.alpha_composite(Image.new("RGBA", rgba.size, background), rgba).convert(
                "RGB"
            )
        thumb.thumbnail((384, 384), Image.Resampling.LANCZOS)
        thumbs.append((label, thumb))
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    cell_w, cell_h, caption = 400, 400, 28
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + caption)), "#FFFFFF")
    draw = ImageDraw.Draw(sheet)
    for idx, (label, thumb) in enumerate(thumbs):
        ox, oy = (idx % cols) * cell_w, (idx // cols) * (cell_h + caption)
        sheet.paste(thumb, (ox + (cell_w - thumb.width) // 2, oy + (cell_h - thumb.height) // 2))
        draw.text((ox + 12, oy + cell_h + 6), label, fill="#333333")
    sheet.save(dst)
    return dst


def _export_all(
    concept_dir: Path, out_dir: Path, *, name: str, palette: dict[str, str], motif_svg: Path
) -> dict[str, Path]:
    """Build the full export set; return a manifest dict and write manifest.json."""
    concept_dir, out, motif = Path(concept_dir), Path(out_dir), Path(motif_svg)
    out.mkdir(parents=True, exist_ok=True)
    if not motif.is_file():
        raise ExportError(f"no motif svg at {motif}")
    paper, ink = _paper(palette), _ink(palette)

    manifest: dict[str, Path] = {}
    manifest["hero-transparent"] = _hero(concept_dir, out)
    hero = manifest["hero-transparent"]
    manifest["hero-paper"] = _hero_on_paper(hero, out, paper, shadow=True)
    manifest["avatar-1024"] = _avatar(hero, out, paper)

    pwa_source = _hero_on_paper(hero, out, paper, shadow=False)
    manifest.update(_favicons(motif, out))
    manifest.update(_svgs(motif, out, ink))

    pwa_dir = out / "pwa"
    pwa_assets(pwa_source, pwa_dir, background=paper, opaque=True)
    manifest["pwa-manifest"] = pwa_dir / "manifest.json"

    fav_files = favicons_meta(
        pwa_source, out, app_name=name, background=paper, theme_color=palette.get("primary", ink)
    )
    for produced in fav_files:
        manifest[f"favicons-{Path(produced).stem}"] = out / produced
    pwa_source.unlink(missing_ok=True)
    model = Path(concept_dir) / "model.glb"
    if model.is_file():
        manifest["model.glb"] = draco_compress(model, out / "model.glb")
    blend = Path(concept_dir) / "scene.blend"
    if blend.is_file():
        shutil.copyfile(blend, out / "scene.blend")
        manifest["scene.blend"] = out / "scene.blend"

    sheet_entries = [
        (key, path)
        for key, path in manifest.items()
        if path.suffix.lower() in (".png", ".svg")
        and "favicon-" not in key
        and "favicons-" not in key
        and "pwa" not in key
    ]
    sheet_entries += [
        (key, path) for key, path in manifest.items() if key in ("favicon-512", "favicon-180")
    ]
    manifest["contact-sheet"] = _contact_sheet(
        sheet_entries, out / "contact-sheet.png", mono_background=paper
    )

    files: dict[str, dict] = {}
    for key, path in manifest.items():
        entry: dict = {
            "path": path.name if path.parent == out else str(path.relative_to(out)),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        if path.suffix.lower() in (".png", ".ico", ".jpg"):
            with Image.open(path) as im:
                entry["width"], entry["height"] = im.size
        files[key] = entry
    record = {"name": name, "palette": dict(palette), "files": files}
    (out / "manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True))

    # The flat motif is not a product SVG; keep the folder to the contract set.
    for extra in (".mark-color.src.svg", ".mark-mono.src.svg"):
        (out / extra).unlink(missing_ok=True)
    return manifest


def export_all(
    concept_dir: Path,
    out_dir: Path,
    *,
    name: str,
    palette: dict[str, str],
    motif_svg: Path,
    budget: Budget | None = None,
) -> dict[str, Path]:
    """Build under the whole-job deadline, then replace the export set as a unit.

    The child deadline covers native CPU image processing and external tools too.
    Low-level legacy image exports remain available, explicitly unattested; the
    pipeline winner boundary additionally requires sampling qualification.
    """
    budget = budget or Budget()
    budget.check()
    started = time.monotonic()
    concept_dir, out_dir = Path(concept_dir).resolve(), Path(out_dir).resolve()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    provenance_path = concept_dir / ".build/final.sampling.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else None
    if provenance and (
        not provenance.get("published")
        or provenance.get("delivered_sha256") != _sha256(concept_dir / "final.png")
    ):
        raise ExportError("sampling provenance does not match final image; prior exports retained")
    with TemporaryDirectory(prefix=".export-pending-", dir=out_dir.parent) as temp:
        pending = Path(temp) / "exports"
        payload = {
            "concept_dir": str(concept_dir),
            "out_dir": str(pending),
            "name": name,
            "palette": palette,
            "motif_svg": str(Path(motif_svg).resolve()),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "logo_maker.export"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=budget.remaining,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SamplingLimit(
                "time_limit: export deadline exhausted; prior exports retained"
            ) from exc
        if proc.returncode:
            raise ExportError((proc.stderr or proc.stdout)[-2000:])
        budget.check()
        record = json.loads((pending / "manifest.json").read_text())
        record["sampling"] = (
            {"state": "unattested_legacy_image"}
            if provenance is None
            else {"record_sha256": _sha256(provenance_path), "record": provenance}
        )
        record["export_seconds"] = time.monotonic() - started
        record["whole_job_budget"] = budget.record()
        (pending / "manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True))
        budget.check()
        backup = out_dir.with_name(out_dir.name + ".prior-" + uuid.uuid4().hex)
        if out_dir.exists():
            out_dir.rename(backup)
        try:
            pending.rename(out_dir)
            budget.check()
        except (OSError, SamplingLimit):
            if out_dir.exists():
                shutil.rmtree(out_dir)
            if backup.exists():
                backup.rename(out_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    return {key: out_dir / entry["path"] for key, entry in record["files"].items()}


if __name__ == "__main__":
    _export_all(**json.loads(sys.stdin.read()))
