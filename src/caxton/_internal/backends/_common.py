"""Small renderer-neutral helpers shared by built-in spreadsheet backends."""

from caxton._internal.const import _AUTO_WIDTH_PADDING, _DEFAULT_AUTO_WIDTH
from caxton.core.formatting import AutoWidth


def display_width(value: object) -> int:
    """Return the simple rendered character width used by XLSX adapters."""
    return 0 if value is None else len(str(value))


def fitted_width(observed: int, policy: AutoWidth | None = None) -> float:
    """Clamp an observed width to the shared XLSX auto-width policy.

    Returns:
        The padded width within supported display bounds.
    """
    resolved = policy or _DEFAULT_AUTO_WIDTH
    return min(
        resolved.maximum,
        max(resolved.minimum, observed + _AUTO_WIDTH_PADDING),
    )


__all__ = ("display_width", "fitted_width")
