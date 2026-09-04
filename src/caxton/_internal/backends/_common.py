"""Small renderer-neutral helpers shared by built-in spreadsheet backends."""

from caxton._internal.const import _AUTO_WIDTH_PADDING, _DEFAULT_AUTO_WIDTH
from caxton.core.formatting import AutoWidth
from caxton.core.ir import SpreadsheetTableIR


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


def reserved_last_row(
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
) -> int:
    """Return the last row the rendered table body occupies.

    A named table with no data rows still reserves one blank row, because XLSX
    native tables cannot consist of a header alone.

    Returns:
        The last physical row owned by the header and data area.
    """
    if table.name is not None and last_row == header_row:
        return header_row + 1
    return last_row


__all__ = ("display_width", "fitted_width", "reserved_last_row")
