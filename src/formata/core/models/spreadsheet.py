from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping, Sequence
from typing import Any

from formata.core.errors import FormataTypeError, FormataValueError
from formata.core.formatting import (
    DocumentTheme,
    StyleInput,
    StyleSheet,
)
from formata.core.protocols.data import DataSource

from .columns import Column
from .common import DocumentKind, DocumentMetadata, freeze_metadata
from .formulas import Formula, FormulaInput, as_formula


@dataclasses.dataclass(frozen=True, slots=True)
class Freeze:
    """Number of leading worksheet rows and columns kept visible."""

    rows: int = 0
    columns: int = 0

    def __post_init__(self) -> None:
        for name, value in (("rows", self.rows), ("columns", self.columns)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                message = f"Freeze {name} must be non-negative"
                raise FormataValueError(message)
        if self.rows == 0 and self.columns == 0:
            message = "Freeze must include at least one row or column"
            raise FormataValueError(message)


class AggregateFunction(enum.StrEnum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


@dataclasses.dataclass(frozen=True, slots=True, init=False)
class Total:
    """Aggregate placed in one semantic column of a totals footer."""

    column: str
    function: AggregateFunction = AggregateFunction.SUM

    def __init__(
        self,
        column: str,
        function: AggregateFunction | str = AggregateFunction.SUM,
    ) -> None:
        object.__setattr__(self, "column", column)
        try:
            normalized = AggregateFunction(function)
        except ValueError as error:
            message = f"Unsupported aggregate function {function!r}"
            raise FormataValueError(message) from error
        object.__setattr__(self, "function", normalized)
        self.__post_init__()

    def __post_init__(self) -> None:
        _validate_required_name(self.column, "Total column")


@dataclasses.dataclass(frozen=True, slots=True)
class Totals:
    """One totals/footer row."""

    label: str = "Total"
    items: Sequence[Total] = ()
    label_column: str | None = None
    style: StyleInput | None = None

    def __post_init__(self) -> None:
        _validate_required_name(self.label, "Totals label")
        if self.label_column is not None:
            _validate_required_name(self.label_column, "Totals label column")
        object.__setattr__(self, "items", tuple(self.items))


@dataclasses.dataclass(frozen=True, slots=True)
class ConditionalRule:
    """Formula-based conditional cell style for a table data range."""

    condition: Formula
    style: StyleInput


def when(condition: FormulaInput, *, style: StyleInput) -> ConditionalRule:
    return ConditionalRule(condition=as_formula(condition), style=style)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class TableData:
    """Shared semantic schema and its lazy row source."""

    source: DataSource[Any]
    columns: Sequence[Column]

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class SpreadsheetTable:
    """Spreadsheet placement of semantic table data."""

    data: TableData
    name: str | None = None
    anchor: str | None = None
    style: StyleInput | None = None
    header_style: StyleInput | None = None
    footer: Totals | None = None
    rules: Sequence[ConditionalRule] = ()
    autofilter: bool = False
    freeze: str | None = None
    auto_width: bool = False

    def __post_init__(self) -> None:
        _validate_optional_name(self.name, "Table name")
        _validate_optional_name(self.anchor, "Table anchor")
        if self.freeze is not None and self.freeze != "header":
            message = "Table freeze must be 'header'"
            raise FormataValueError(message)
        object.__setattr__(self, "rules", tuple(self.rules))

    @property
    def columns(self) -> Sequence[Column]:
        return self.data.columns


SpreadsheetBlock = SpreadsheetTable


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Worksheet:
    """Immutable sequence of spreadsheet blocks."""

    name: str
    blocks: Sequence[SpreadsheetBlock]
    freeze: Freeze | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            message = "Worksheet name must be a string"
            raise FormataTypeError(message)
        if not self.name.strip():
            message = "Worksheet name cannot be empty"
            raise FormataValueError(message)
        object.__setattr__(self, "blocks", tuple(self.blocks))


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class SpreadsheetDocument:
    """Backend-independent spreadsheet document intent."""

    worksheets: Sequence[Worksheet]
    metadata: DocumentMetadata = dataclasses.field(default_factory=dict)
    styles: StyleSheet = dataclasses.field(default_factory=lambda: StyleSheet({}))
    theme: DocumentTheme = dataclasses.field(default_factory=DocumentTheme)
    kind: DocumentKind = dataclasses.field(
        default=DocumentKind.SPREADSHEET,
        init=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


def metadata_or_empty(
    metadata: Mapping[str, object] | None,
) -> Mapping[str, object]:
    return {} if metadata is None else metadata


def _validate_optional_name(value: str | None, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise FormataTypeError(message)
    if not value.strip():
        message = f"{label} cannot be empty"
        raise FormataValueError(message)


def _validate_required_name(value: object, label: str) -> None:
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise FormataTypeError(message)
    if not value.strip():
        message = f"{label} cannot be empty"
        raise FormataValueError(message)


__all__ = (
    "AggregateFunction",
    "ConditionalRule",
    "Freeze",
    "SpreadsheetBlock",
    "SpreadsheetDocument",
    "SpreadsheetTable",
    "TableData",
    "Total",
    "Totals",
    "Worksheet",
    "when",
)
