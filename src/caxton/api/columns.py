from __future__ import annotations

from caxton.core.formatting import StyleInput
from caxton.core.models.columns import Column
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
    SemanticType,
    Text,
    Time,
)


def _make(
    *,
    id: str | None,
    semantic_type: SemanticType,
    source: ColumnSourceInput,
    title: str | None,
    formula: FormulaInput | None,
    style: StyleInput | None,
) -> Column:
    return Column(
        id=id,
        semantic_type=semantic_type,
        source=source,
        title=title,
        excel_formula=formula,
        style=style,
    )


def text(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Text(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def money(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    currency: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Money(currency=currency),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def date(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Date(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def time(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Time(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def datetime(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=DateTime(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def duration(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Duration(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def percentage(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Percentage(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def decimal(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Decimal(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def integer(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Integer(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def boolean(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Boolean(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


def link(
    *,
    id: str | None = None,
    source: ColumnSourceInput = None,
    title: str | None = None,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    return _make(
        id=id,
        semantic_type=Link(),
        source=source,
        title=title,
        formula=formula,
        style=style,
    )


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
