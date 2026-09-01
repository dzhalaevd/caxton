from __future__ import annotations

from caxton.core._compat import StrEnum


class Alignment(StrEnum):
    """Horizontal alignment expressed without backend terminology."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


__all__ = ("Alignment",)
