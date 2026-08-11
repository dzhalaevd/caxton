from __future__ import annotations

import re

from formata.core.ir import CellAddress

_CELL_ADDRESS = re.compile(r"^(?P<column>[A-Za-z]+)(?P<row>[1-9][0-9]*)$")


def parse_cell_address(value: str) -> CellAddress:
    """Parse an A1-style address into a family IR coordinate.

    Returns:
        A one-based cell address.

    Raises:
        ValueError: If the address is not in A1 notation.
    """
    matched = _CELL_ADDRESS.fullmatch(value)
    if matched is None:
        message = f"Invalid cell anchor {value!r}"
        raise ValueError(message)
    return CellAddress(
        row=int(matched.group("row")),
        column=_column_number(matched.group("column")),
    )


def format_cell_address(row: int, column: int) -> str:
    """Format a one-based row and column as an A1-style address.

    Returns:
        The canonical uppercase cell address.

    """
    _validate_coordinate(row)
    _validate_coordinate(column)
    letters: list[str] = []
    remaining = column
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return f"{''.join(reversed(letters))}{row}"


def _validate_coordinate(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message = "Cell coordinates must be positive integers"
        raise ValueError(message)


def _column_number(letters: str) -> int:
    column = 0
    for character in letters.upper():
        column = column * 26 + ord(character) - ord("A") + 1
    return column


__all__ = ("format_cell_address", "parse_cell_address")
