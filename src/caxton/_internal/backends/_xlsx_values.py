"""Validate semantic values at the shared XLSX materialization boundary."""

from __future__ import annotations

import datetime as dt
import decimal
import math

from caxton.core.errors import UnsupportedFeatureError
from caxton.core.values import CellValue

_MAX_TEXT_LENGTH = 32_767
_MAX_SIGNIFICANT_DIGITS = 15


def validate_xlsx_value(
    value: CellValue,
    *,
    worksheet: str,
    table: str | None,
    row: int,
    column: str,
) -> CellValue:
    """Return a value only when XLSX can preserve it portably.

    Returns:
        The unchanged portable value.

    Raises:
        UnsupportedFeatureError: If XLSX cannot preserve the value.
    """
    reason = _incompatibility(value)
    if reason is None:
        return value
    message = f"XLSX cannot preserve value in column {column!r}: {reason}"
    raise UnsupportedFeatureError(
        message,
        context={
            "column": column,
            "row": row,
            "table": table,
            "value_type": type(value).__name__,
            "worksheet": worksheet,
        },
    )


def validate_xlsx_text(value: str, *, role: str) -> str:
    """Validate literal workbook labels that do not carry row context.

    Returns:
        The unchanged portable text.

    Raises:
        UnsupportedFeatureError: If the text exceeds the XLSX cell limit.
    """
    if len(value) <= _MAX_TEXT_LENGTH:
        return value
    message = f"XLSX {role} exceeds the 32,767 character cell limit"
    raise UnsupportedFeatureError(
        message,
        context={"length": len(value), "role": role},
    )


def _incompatibility(value: CellValue) -> str | None:  # noqa: C901, WPS212
    if isinstance(value, str):
        return None if len(value) <= _MAX_TEXT_LENGTH else "text is too long"
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        if _significant_digits(value) > _MAX_SIGNIFICANT_DIGITS:
            return "integer exceeds 15 significant digits"
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return "number is not finite"
        if _significant_digits(decimal.Decimal(str(value))) > _MAX_SIGNIFICANT_DIGITS:
            return "number exceeds 15 significant digits"
        return None
    if isinstance(value, decimal.Decimal):
        if not value.is_finite():
            return "number is not finite"
        if _significant_digits(value) > _MAX_SIGNIFICANT_DIGITS:
            return "decimal exceeds 15 significant digits"
        return None
    if isinstance(value, (dt.datetime, dt.time)) and value.tzinfo is not None:
        return "timezone-aware date/time values are unsupported"
    if isinstance(value, bytes):
        return "binary cell values are unsupported"
    return None


def _significant_digits(value: int | decimal.Decimal) -> int:
    if isinstance(value, int):
        digits = str(abs(value))
    else:
        digits = "".join(str(digit) for digit in value.as_tuple().digits)
    return len(digits.rstrip("0")) or 1


__all__ = ("validate_xlsx_text", "validate_xlsx_value")
