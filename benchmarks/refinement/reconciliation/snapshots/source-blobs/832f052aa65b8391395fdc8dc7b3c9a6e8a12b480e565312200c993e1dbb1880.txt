"""Jev slice adapters: judgment calls and the color math behind them."""

from __future__ import annotations

import os

from logo_maker.adapters import Adapter, python_module

__all__ = ["ADAPTERS"]


def _jev_key() -> str | None:
    if os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        return None
    return "no jev API key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY"


ADAPTERS: list[Adapter] = [
    Adapter(
        name="jev (TypeSafe)",
        stage="judgment",
        license="proprietary API",
        summary="calibrated yes/no, choice, and score judgments over briefs, concepts, and renders",
        entry="logo_maker.jev.client:JevClient",
        check=_jev_key,
        fix="export OPENROUTER_API_KEY=<key>  # or TYPESAFE_API_KEY=<key> for direct TypeSafe",
    ),
    Adapter(
        name="coloraide",
        stage="color_type",
        license="MIT",
        summary="WCAG 2.1 contrast ratios that gate palettes before jev ever sees them",
        entry="logo_maker.palette:contrast",
        check=python_module("coloraide"),
        fix="uv add coloraide",
    ),
]
