from __future__ import annotations

import enum


class Alignment(enum.StrEnum):
    """Horizontal alignment expressed without backend terminology."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


__all__ = ("Alignment",)
