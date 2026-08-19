from __future__ import annotations

from functools import singledispatch

from caxton.core.formatting import (
    CustomFormat,
    DateFormat,
    DecimalFormat,
    MoneyFormat,
    PercentageFormat,
    TimeFormat,
)
from caxton.core.ir import SpreadsheetColumnIR
from caxton.core.types import (
    Date,
    DateTime,
    Decimal,
    Duration,
    Money,
    Percentage,
    SemanticType,
    Time,
)


def number_format(column: SpreadsheetColumnIR) -> str:  # noqa: C901, WPS212
    """Lower one semantic column format to an XLSX number-format pattern.

    Returns:
        A backend-neutral XLSX number-format pattern.
    """
    display_format = column.display_format
    if isinstance(display_format, DecimalFormat):
        return _decimal_pattern(display_format.places, display_format.grouping)
    if isinstance(display_format, MoneyFormat):
        currency = display_format.currency
        if currency is None and isinstance(column.semantic_type, Money):
            currency = column.semantic_type.currency
        return _money_pattern(
            currency,
            display_format.places,
            display_format.grouping,
        )
    if isinstance(display_format, DateFormat):
        return {
            "iso": "yyyy-mm-dd",
            "short": "m/d/yy",
            "long": "mmmm d, yyyy",
        }[display_format.variant]
    if isinstance(display_format, TimeFormat):
        seconds = ":ss" if display_format.seconds else ""
        return (
            f"h:mm{seconds} AM/PM" if display_format.clock == 12 else f"hh:mm{seconds}"
        )
    if isinstance(display_format, PercentageFormat):
        return f"{_decimal_pattern(display_format.places, display_format.grouping)}%"
    if isinstance(display_format, CustomFormat):
        return display_format.pattern
    return _semantic_number_format(column.semantic_type)


@singledispatch
def _semantic_number_format(_semantic_type: SemanticType) -> str:
    return "General"


@_semantic_number_format.register
def _money_number_format(semantic_type: Money) -> str:
    return _money_pattern(semantic_type.currency, 2, grouping=True)


@_semantic_number_format.register
def _percentage_number_format(_semantic_type: Percentage) -> str:
    return "0.00%"


@_semantic_number_format.register
def _datetime_number_format(_semantic_type: DateTime) -> str:
    return "yyyy-mm-dd hh:mm:ss"


@_semantic_number_format.register
def _date_number_format(_semantic_type: Date) -> str:
    return "yyyy-mm-dd"


@_semantic_number_format.register
def _time_number_format(_semantic_type: Time) -> str:
    return "hh:mm:ss"


@_semantic_number_format.register
def _duration_number_format(_semantic_type: Duration) -> str:
    return "[h]:mm:ss"


@_semantic_number_format.register
def _decimal_number_format(_semantic_type: Decimal) -> str:
    return "0.00"


def _decimal_pattern(places: int, grouping: bool = False) -> str:
    whole = "#,##0" if grouping else "0"
    return whole if places == 0 else f"{whole}.{''.join('0' for _ in range(places))}"


def _money_pattern(currency: str | None, places: int, grouping: bool) -> str:
    number = _decimal_pattern(places, grouping)
    return number if currency is None else f'"{currency}" {number}'


__all__ = ("number_format",)
