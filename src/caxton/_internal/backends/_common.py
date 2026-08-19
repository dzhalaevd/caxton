"""Small renderer-neutral helpers shared by built-in spreadsheet backends."""

from typing import Final

_AUTO_WIDTH_MIN: Final[int] = 1
_AUTO_WIDTH_MAX: Final[int] = 80
_AUTO_WIDTH_PADDING: Final[int] = 2


def display_width(value: object) -> int:
    """Return the simple rendered character width used by XLSX adapters."""
    return 0 if value is None else len(str(value))


def fitted_width(observed: int) -> int:
    """Clamp an observed width to the shared XLSX auto-width policy.

    Returns:
        The padded width within supported display bounds.
    """
    return min(
        _AUTO_WIDTH_MAX,
        max(_AUTO_WIDTH_MIN, observed + _AUTO_WIDTH_PADDING),
    )


__all__ = ("display_width", "fitted_width")
