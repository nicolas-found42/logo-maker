"""Pixel post-ops: OIIO downsample, square pad, flat composite, soft shadow."""

from __future__ import annotations

from pathlib import Path

import OpenImageIO as oiio
from PIL import Image, ImageFilter


def _oiio_read(src: Path) -> oiio.ImageBuf:
    buf = oiio.ImageBuf(str(src))
    if buf.has_error or buf.spec().width == 0:
        raise ValueError(f"cannot read image {src}: {buf.geterror()}")
    return buf


def downsample(src: Path, dst: Path, size: int) -> Path:
    """Scale so the long edge is `size` px, writing an RGBA PNG to `dst`.

    Resizes with OpenImageIO's lanczos3 filter. Images with alpha are
    resized premultiplied (premult -> resize -> unpremult) so fringes and
    halos do not creep in around transparent edges.
    """
    src, dst = Path(src), Path(dst)
    if size <= 0:
        raise ValueError(f"downsample size must be positive, got {size}")
    buf = _oiio_read(src)
    spec = buf.spec()
    width, height, channels = spec.width, spec.height, spec.nchannels
    scale = size / max(width, height)
    new_w, new_h = max(1, round(width * scale)), max(1, round(height * scale))
    roi = oiio.ROI(0, new_w, 0, new_h, 0, 1, 0, channels)
    if channels == 4:
        # Premultiplied-alpha correct: filtering associated color keeps
        # transparent black from bleeding into edge pixels.
        sized = oiio.ImageBufAlgo.resize(
            oiio.ImageBufAlgo.premult(buf), filtername="lanczos3", roi=roi
        )
        sized = oiio.ImageBufAlgo.unpremult(sized)
    else:
        sized = oiio.ImageBufAlgo.resize(buf, filtername="lanczos3", roi=roi)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not sized.write(str(dst)):
        raise ValueError(f"cannot write image {dst}: {sized.geterror()}")
    return dst


def pad_square(
    src: Path, dst: Path, size: int, *, fill: tuple[int, int, int, int] = (0, 0, 0, 0)
) -> Path:
    src, dst = Path(src), Path(dst)
    if size <= 0:
        raise ValueError(f"pad_square size must be positive, got {size}")
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
    rgba.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), fill)
    canvas.alpha_composite(rgba, ((size - rgba.width) // 2, (size - rgba.height) // 2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)
    return dst


def composite_on(png: Path, color_hex: str, dst: Path | None = None) -> Path:
    """Flatten an RGBA PNG onto a solid `color_hex` background (opaque RGB)."""
    png = Path(png)
    dst = png.with_name(f"{png.stem}-flat.png") if dst is None else Path(dst)
    with Image.open(png) as im:
        rgba = im.convert("RGBA")
    bg = Image.new("RGB", rgba.size, color_hex)
    bg.paste(rgba, (0, 0), rgba)
    dst.parent.mkdir(parents=True, exist_ok=True)
    bg.save(dst)
    return dst


def soft_shadow(
    png: Path, *, opacity: float = 0.26, blur: int = 28, offset: tuple[int, int] = (0, 18)
) -> Image.Image:
    """Render the mark's silhouette as a blurred black shadow sprite.

    Returns an RGBA image the same size as `png`: black with the blurred
    silhouette alpha scaled by `opacity`. The caller pastes it shifted by
    `offset` under the mark (Pillow clips at the canvas edge, so the mark
    needs margins of at least blur + offset pixels for a clean result).
    """
    with Image.open(png) as im:
        alpha = im.convert("RGBA").getchannel("A")
    shadow_alpha = alpha.point(lambda v: int(v * opacity)).filter(ImageFilter.GaussianBlur(blur))
    shadow = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    ox, oy = offset
    layer = Image.new("RGBA", (alpha.width + abs(ox), alpha.height + abs(oy)), (0, 0, 0, 0))
    layer.alpha_composite(shadow, (max(ox, 0), max(oy, 0)))
    return layer.crop((0, 0, alpha.width, alpha.height))
