from __future__ import annotations

from caxton.core.formatting import StyleInput
from caxton.core.models.columns import Column, make_column
from caxton.core.models.expressions import ColumnSourceInput
from caxton.core.models.formulas import FormulaInput
from caxton.core.types import (
    Boolean,
    Date,
    DateTime,
    Decimal,
    Duration,
    Integer,
    Link,
    Money,
    Percentage,
    Text,
    Time,
)


def text(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Text(), source, formula, style)


def money(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    currency: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Money(currency=currency), source, formula, style)


def date(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Date(), source, formula, style)


def time(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Time(), source, formula, style)


def datetime(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, DateTime(), source, formula, style)


def duration(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Duration(), source, formula, style)


def percentage(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Percentage(), source, formula, style)


def decimal(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Decimal(), source, formula, style)


def integer(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Integer(), source, formula, style)


def boolean(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Boolean(), source, formula, style)


def link(
    column_id: str,
    *,
    source: ColumnSourceInput = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return make_column(column_id, Link(), source, formula, style)


__all__ = (
    "boolean",
    "date",
    "datetime",
    "decimal",
    "duration",
    "integer",
    "link",
    "money",
    "percentage",
    "text",
    "time",
)
