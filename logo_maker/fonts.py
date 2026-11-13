"""Google Fonts resolution and text geometry (no AI, just font files and math).

Fonts come from github.com/google/fonts (OFL/Apache/UFL directories). Variable
axes are pinned with fontTools.varLib.instancer to a cached static TTF, so every
consumer sees a plain file. Use is recorded through the optional ``on_asset``
callback (wired to ``RunLog.asset`` by the pipeline).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from logo_maker.paths import cache_dir, slugify
from logo_maker.proc import ToolError

GF_REPO = "https://raw.githubusercontent.com/google/fonts/main"
GF_API = "https://api.github.com/repos/google/fonts/contents"
GF_METADATA = "https://fonts.google.com/metadata/fonts"
LICENSE_DIRS = ("ofl", "apache", "ufl")
DIR_LICENSE = {"ofl": "OFL-1.1", "apache": "Apache-2.0", "ufl": "UFL"}
METADATA_TTL = 7 * 24 * 3600

OnAsset = Callable[[str, str, str, str], None]


class FontSpecError(ValueError):
    """A font spec is malformed, names no known family, or asks for an impossible axis."""


@dataclass(frozen=True)
class FontSpec:
    family: str
    axes: dict[str, float]

    def __str__(self) -> str:
        if not self.axes:
            return self.family
        return self.family + ":" + ",".join(f"{k}={_num(v)}" for k, v in self.axes.items())


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


_SPEC_RE = re.compile(r"^(?P<family>[^:]+?)(?::(?P<axes>[A-Za-z0-9_.,=\s-]+))?\s*$")
_AXIS_RE = re.compile(r"^[A-Za-z]{4}$")


def parse_spec(spec: str) -> FontSpec:
    """Parse ``'Family Name[:axis=value,...]'``; italic is ``ital=1``. Raises FontSpecError."""
    match = _SPEC_RE.match(spec.strip())
    if not match or not match.group("family").strip():
        raise FontSpecError(f"bad font spec {spec!r}; want 'Family Name' or 'Family Name:wght=700'")
    axes: dict[str, float] = {}
    raw_axes = (match.group("axes") or "").strip()
    if raw_axes:
        for part in raw_axes.split(","):
            part = part.strip()
            if "=" not in part:
                raise FontSpecError(f"bad axis {part!r} in {spec!r}; want tag=value like wght=700")
            tag, value = part.split("=", 1)
            tag, value = tag.strip(), value.strip()
            if not _AXIS_RE.match(tag):
                raise FontSpecError(f"bad axis tag {tag!r} in {spec!r}; tags are four letters")
            try:
                axes[tag] = float(value)
            except ValueError:
                raise FontSpecError(
                    f"bad axis value {value!r} in {spec!r}; want a number"
                ) from None
    return FontSpec(match.group("family").strip(), axes)


def _fonts_dir() -> Path:
    return cache_dir("fonts")


def _replace(dest: Path, write: Callable[[Path], object]) -> None:
    """Write through a sibling temp file, so an interrupted write never leaves a cached file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f".{dest.name}.{os.getpid()}.part")
    try:
        write(part)
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)


def _get(url: str, dest: Path, *, timeout: float = 60) -> Path:
    if dest.exists():
        return dest

    def download(part: Path) -> None:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
            if resp.status_code != 200:
                raise FontSpecError(f"download failed ({resp.status_code}): {url}")
            with open(part, "wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)

    try:
        _replace(dest, download)
    except httpx.HTTPError as exc:
        raise ToolError(f"could not download {url}: {exc}") from exc
    return dest


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _load_index() -> dict[str, list[str]]:
    """The cached family directory index; a damaged one is a cache miss."""
    path = _fonts_dir() / "index.json"
    try:
        index = json.loads(path.read_text())
    except (ValueError, OSError):
        return {}
    valid = isinstance(index, dict) and all(
        isinstance(dirs, list) and dirs and all(isinstance(d, str) and "/" in d for d in dirs)
        for dirs in index.values()
    )
    return index if valid else {}


def _save_index(index: dict[str, list[str]]) -> None:
    text = json.dumps(index, indent=1, sort_keys=True)
    _replace(_fonts_dir() / "index.json", lambda part: part.write_text(text))


def _refresh_index() -> dict[str, list[str]]:
    """List the ofl/apache/ufl directories through the GitHub contents API."""
    index: dict[str, list[str]] = {}
    try:
        for top in LICENSE_DIRS:
            url = f"{GF_API}/{top}?per_page=100&ref=main"
            while url:
                resp = httpx.get(url, timeout=60, headers={"Accept": "application/vnd.github+json"})
                if resp.status_code != 200:
                    raise ToolError(
                        f"github contents listing failed ({resp.status_code}) for {top}"
                    )
                for entry in resp.json():
                    if entry.get("type") == "dir":
                        index.setdefault(_norm(entry["name"]), []).append(f"{top}/{entry['name']}")
                url = None
                link = resp.headers.get("link", "")
                for part in link.split(","):
                    if 'rel="next"' in part:
                        url = part.split(";")[0].strip().strip("<>")
    except httpx.HTTPError as exc:
        raise ToolError(f"could not list google/fonts directories: {exc}") from exc
    _save_index(index)
    return index


def _family_dirpath(family: str) -> tuple[str, str]:
    """Return (license_dir, dirname) for a family, guessing then falling back to the API."""
    guess = _norm(family)
    index = _load_index()
    if _norm(family) in index:
        top, dirname = index[_norm(family)][0].split("/", 1)
        return top, dirname
    for top in LICENSE_DIRS:  # fast path: the repo convention is the squashed lowercase name
        path = _fonts_dir() / "meta" / top / f"{guess}.pb"
        try:
            _get(f"{GF_REPO}/{top}/{guess}/METADATA.pb", path)
        except (FontSpecError, ToolError):
            continue
        index.setdefault(_norm(family), []).append(f"{top}/{guess}")
        _save_index(index)
        return top, guess
    index = _refresh_index()  # slow path: list every directory once, then cache
    hits = index.get(_norm(family), [])
    if not hits:
        from difflib import get_close_matches

        names = sorted({p.split("/", 1)[1] for paths in index.values() for p in paths})
        hint = get_close_matches(family, names, n=3)
        raise FontSpecError(
            f"unknown Google Fonts family {family!r}" + (f"; did you mean {hint}?" if hint else "")
        )
    top, dirname = hits[0].split("/", 1)
    return top, dirname


METADATA_FONTS_RE = re.compile(r"fonts \{(.*?)\}", re.S)
METADATA_AXES_RE = re.compile(r"axes \{(.*?)\}", re.S)
_FIELD_RE = re.compile(r'(\w+):\s*(?:"([^"]*)"|([0-9.]+))')


def _metadata(top: str, dirname: str) -> tuple[list[dict], list[dict], str]:
    """Parse a family's METADATA.pb into (files, axes, spdx_license)."""
    path = _fonts_dir() / "meta" / top / f"{dirname}.pb"
    _get(f"{GF_REPO}/{top}/{dirname}/METADATA.pb", path)
    text = path.read_text()
    files = []
    for block in METADATA_FONTS_RE.findall(text):
        fields = {k: (s or n) for k, s, n in _FIELD_RE.findall(block)}
        if "filename" in fields:
            files.append(
                {
                    "name": fields.get("name", ""),
                    "style": fields.get("style", "normal"),
                    "weight": fields.get("weight", "400"),
                    "filename": fields["filename"],
                }
            )
    axes = []
    for block in METADATA_AXES_RE.findall(text):
        fields = {k: (s or n) for k, s, n in _FIELD_RE.findall(block)}
        if "tag" in fields:
            axes.append(
                {
                    "tag": fields["tag"],
                    "min": float(fields.get("min_value", 0)),
                    "max": float(fields.get("max_value", 0)),
                }
            )
    lic = re.search(r'license:\s*"([^"]+)"', text)
    spdx = {"OFL": "OFL-1.1", "APACHE": "Apache-2.0", "UFL": "UFL"}.get(
        lic.group(1).strip().upper() if lic else "OFL", DIR_LICENSE[top]
    )
    return files, axes, spdx


def _pick_file(files: list[dict], spec: FontSpec) -> dict:
    italic = spec.axes.get("ital", 0.0) >= 0.5
    style = "italic" if italic else "normal"
    same = [f for f in files if f["style"] == style]
    if not same and italic:
        raise FontSpecError(f"{spec.family} has no italic; drop ital=1 or pick another family")
    same = same or files
    variable = [f for f in same if "[" in f["filename"]]
    if variable:
        return variable[0]
    if set(spec.axes) - {"ital"}:
        names = sorted({f["filename"] for f in same})
        raise FontSpecError(
            f"{spec.family} has no variable font (only {names}); drop the axes from the spec"
        )
    return same[0]


def resolve(spec: str, on_asset: OnAsset | None = None) -> Path:
    """Download a family, pin its variable axes, and return a cached static TTF.

    Results cache by spec hash under ``cache_dir('fonts')``; the license is
    reported through ``on_asset(key, source, license, path)`` when given.
    """
    parsed = parse_spec(spec) if isinstance(spec, str) else spec
    top, dirname = _family_dirpath(parsed.family)
    files, _axes, spdx = _metadata(top, dirname)
    if not files:
        raise FontSpecError(f"no font files listed for {parsed.family!r}")
    picked = _pick_file(files, parsed)
    raw_url = f"{GF_REPO}/{top}/{dirname}/{quote(picked['filename'])}"
    raw = _fonts_dir() / "raw" / top / dirname / picked["filename"]
    _get(raw_url, raw)

    canonical = str(FontSpec(parsed.family, dict(sorted(parsed.axes.items()))))
    digest = hashlib.sha1(canonical.encode(), usedforsecurity=False).hexdigest()[:12]
    static = _fonts_dir() / "static" / f"{slugify(parsed.family)}-{digest}.ttf"
    if not static.exists():
        try:
            font = TTFont(raw)
        except Exception as exc:  # fontTools raises TTLibError, struct.error, ... on bad bytes
            raw.unlink(missing_ok=True)  # the next run downloads it again
            raise ToolError(
                f"cached font {raw} was not a font ({exc}); removed it, run again"
            ) from exc
        if "fvar" in font:
            ranges = {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes}
            for tag, value in parsed.axes.items():
                if tag == "ital":
                    continue
                if tag not in ranges:
                    known = sorted(ranges)
                    raise FontSpecError(f"{parsed.family} has no {tag!r} axis (has {known})")
                lo, hi = ranges[tag]
                if not lo - 1e-6 <= value <= hi + 1e-6:
                    raise FontSpecError(f"{parsed.family} {tag}={value:g} outside [{lo:g}, {hi:g}]")
            pin = {k: v for k, v in parsed.axes.items() if k != "ital" and k in ranges}
            if pin:
                instantiateVariableFont(font, pin, inplace=True, updateFontNames=True)
        elif set(parsed.axes) - {"ital"}:
            raise FontSpecError(f"{parsed.family} is a static font; drop the axes from the spec")
        _replace(static, font.save)
    if on_asset is not None:  # one record per spec: two weights of a family are two files
        on_asset(f"font:{canonical}", raw_url, spdx, str(static))
    return static


def _catalog(data: object) -> list[dict] | None:
    entries = data.get("familyMetadataList") if isinstance(data, dict) else None
    if isinstance(entries, list) and all(
        isinstance(e, dict) and isinstance(e.get("family"), str) for e in entries
    ):
        return entries
    return None


def _families_data() -> list[dict]:
    path = _fonts_dir() / "families.json"
    if path.exists() and time.time() - path.stat().st_mtime < METADATA_TTL:
        try:
            cached = _catalog(json.loads(path.read_text()))
        except (ValueError, OSError):  # a damaged cache is a miss
            cached = None
        if cached is not None:
            return cached
    try:
        resp = httpx.get(GF_METADATA, timeout=60)
        resp.raise_for_status()
        data = _catalog(resp.json())
    except httpx.HTTPError as exc:
        raise ToolError(f"could not fetch the Google Fonts catalog: {exc}") from exc
    except ValueError as exc:
        raise ToolError(f"the Google Fonts catalog at {GF_METADATA} is not JSON: {exc}") from exc
    if data is None:
        raise ToolError(f"the Google Fonts catalog at {GF_METADATA} has no family list")
    text = json.dumps({"familyMetadataList": data})
    _replace(path, lambda part: part.write_text(text))
    return data


def families(category: str | None = None) -> list[str]:
    """Every family name, optionally filtered by category (case-insensitive)."""
    names = []
    for entry in _families_data():
        if category is None or entry.get("category", "").lower() == category.lower():
            names.append(entry["family"])
    return sorted(names)


def family_exists(name: str) -> bool:
    """True when Google Fonts hosts a family with this exact (case-insensitive) name."""
    return _norm(name) in {_norm(f) for f in families()}


def _font(spec: str) -> TTFont:
    return TTFont(resolve(spec))


def _kern_units(font: TTFont, left: str, right: str) -> float:
    """Best-effort GPOS pair kerning in font units; 0 when the font has none."""
    try:
        table = font["GPOS"].table
    except KeyError:
        return 0
    try:
        for lookup in table.LookupList.Lookup:
            if lookup.LookupType != 2:  # PairPos only
                continue
            for sub in lookup.SubTable:
                if sub.Format == 1:
                    idx = sub.Coverage.glyphs.index(left) if left in sub.Coverage.glyphs else None
                    if idx is None:
                        continue
                    for pair in sub.PairSet[idx].PairValueRecord:
                        if pair.SecondGlyph == right and pair.Value1 is not None:
                            return float(pair.Value1.XAdvance or 0)
                elif sub.Format == 2:
                    c1 = sub.ClassDef1.classDefs.get(left)
                    c2 = sub.ClassDef2.classDefs.get(right)
                    if c1 is None or c2 is None:
                        continue
                    value = sub.Class1Record[c1].Class2Record[c2].Value1
                    if value is not None:
                        return float(value.XAdvance or 0)
    except (AttributeError, IndexError, KeyError):
        pass
    return 0


def _cmap(font: TTFont) -> dict[int, str]:
    """Best cmap, or a clear error for fonts without usable character mapping."""
    cmap = font.getBestCmap()
    if cmap is None:
        raise FontSpecError("font has no usable cmap")
    return cmap


def _upm(font: TTFont) -> float:
    """Units-per-em: fontTools sets head.unitsPerEm dynamically, so read it loosely."""
    upm = getattr(font["head"], "unitsPerEm", None)
    if upm is None:
        raise FontSpecError("font head table has no units-per-em")
    return float(upm)


def _glyph_advances_em(font: TTFont, text: str) -> tuple[list[str], list[float]]:
    """Glyph names and per-glyph advances in em (pair kerning folded into the left glyph)."""
    cmap = _cmap(font)
    hmtx = font["hmtx"]
    upm = _upm(font)
    names, advs = [], []
    for ch in text:
        name = cmap.get(ord(ch), ".notdef")
        names.append(name)
        advs.append(hmtx[name][0] / upm)
    for i in range(len(names) - 1):
        advs[i] += _kern_units(font, names[i], names[i + 1]) / upm
    return names, advs


def advances(text: str, spec: str) -> list[float]:
    """Per-glyph advances in em, including GPOS pair kerning."""
    return _glyph_advances_em(_font(spec), text)[1]


def metrics(spec: str) -> dict[str, float]:
    """upm plus cap/x heights and ascender/descender, all in em except upm."""
    font = _font(spec)
    upm = _upm(font)
    os2 = font.get("OS/2")
    hhea = font["hhea"]
    out = {"upm": float(upm), "ascender": hhea.ascent / upm, "descender": hhea.descent / upm}
    cap = getattr(os2, "sCapHeight", 0) if os2 is not None else 0
    xh = getattr(os2, "sxHeight", 0) if os2 is not None else 0
    glyphset = font.getGlyphSet()
    if not cap:
        cap = _glyph_top(glyphset, "H")
    if not xh:
        xh = _glyph_top(glyphset, "x")
    out["cap_height_em"] = cap / upm
    out["x_height_em"] = xh / upm
    return out


def _glyph_top(glyphset, name: str) -> float:
    """Top of a glyph in font units, or 0 when the glyph is missing or empty."""
    if name not in glyphset:
        return 0.0
    pen = BoundsPen(glyphset)
    try:
        glyphset[name].draw(pen)
    except Exception:  # a broken glyph reads as no height, not a crash
        return 0.0
    return pen.bounds[3] if pen.bounds else 0.0


def text_path(
    text: str, spec: str, size: float, x: float, y: float, tracking: float = 0.0
) -> tuple[str, float]:
    """Set text as one SVG path d plus its total advance in px.

    Y-down, baseline at ``y``; ``tracking`` adds px after every glyph but the
    last. Empty text returns ``('', 0.0)``.
    """
    if not text:
        return "", 0.0
    font = _font(spec)
    upm = _upm(font)
    scale = size / upm
    glyphset = font.getGlyphSet()
    names, advs = _glyph_advances_em(font, text)
    missing = sorted({ch for ch, name in zip(text, names, strict=True) if name == ".notdef"})
    if missing:
        shown = ", ".join(f"U+{ord(ch):04X}" for ch in missing)
        raise FontSpecError(f"{spec} has no glyph for {shown}; choose a font that covers the text")
    parts: list[str] = []
    cursor = 0.0
    for i, (name, adv) in enumerate(zip(names, advs, strict=True)):
        if name in glyphset and name != ".notdef":
            pen = SVGPathPen(glyphset)
            glyphset[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x + cursor * scale, y)))
            parts.append(pen.getCommands())
        cursor += adv * upm
        if i < len(names) - 1:
            cursor += tracking / scale if scale else 0.0
    return " ".join(p for p in parts if p), cursor * scale


def available_on_disk(spec: str) -> Path | None:
    """The cached static TTF for a spec, or None when it was never resolved."""
    try:
        parsed = parse_spec(spec)
    except FontSpecError:
        return None
    digest = hashlib.sha1(
        str(FontSpec(parsed.family, dict(sorted(parsed.axes.items())))).encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]
    static = _fonts_dir() / "static" / f"{slugify(parsed.family)}-{digest}.ttf"
    return static if static.exists() else None


__all__ = [
    "FontSpec",
    "FontSpecError",
    "advances",
    "available_on_disk",
    "families",
    "family_exists",
    "metrics",
    "parse_spec",
    "resolve",
    "text_path",
]
