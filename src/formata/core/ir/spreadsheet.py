from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence

from formata.core._values import normalize_cell_value
from formata.core.formatting import Alignment, DisplayFormat, Style
from formata.core.models.common import (
    DocumentKind,
    DocumentMetadata,
    freeze_metadata,
)
from formata.core.models.formulas import FormulaOperator
from formata.core.models.spreadsheet import AggregateFunction, Freeze
from formata.core.types import SemanticType
from formata.core.values import CellValue

SPREADSHEET_IR_VERSION = 3


@dataclasses.dataclass(frozen=True, slots=True)
class CellAddress:
    """One-based backend-independent spreadsheet coordinate."""

    row: int
    column: int

    def __post_init__(self) -> None:
        if self.row < 1 or self.column < 1:
            message = "Cell coordinates must be positive"
            raise ValueError(message)


class ResolvedFormula:
    """Base for backend-independent formulas with resolved semantic references."""


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedFormulaLiteral(ResolvedFormula):
    value: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            normalize_cell_value(self.value),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedFormulaBinary(ResolvedFormula):
    operator: FormulaOperator
    left: ResolvedFormula
    right: ResolvedFormula


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedCellReference(ResolvedFormula):
    """Resolved column and optional row; ``row=None`` means current formula row."""

    column: int
    row: int | None
    sheet_name: str | None = None
    column_absolute: bool = False
    row_absolute: bool = False

    def __post_init__(self) -> None:
        if self.column < 1 or (self.row is not None and self.row < 1):
            message = "Resolved cell coordinates must be positive"
            raise ValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedRangeReference(ResolvedFormula):
    sheet_name: str
    start: CellAddress
    end: CellAddress
    table_name: str
    column_title: str
    column_absolute: bool = False
    row_absolute: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetColumnIR:
    """Resolved renderer-facing column description."""

    offset: int
    id: str
    title: str
    semantic_type: SemanticType
    alignment: Alignment | None
    width_hint: float | None
    display_format: DisplayFormat | None
    formula: ResolvedFormula | None = None
    style: Style = dataclasses.field(default_factory=Style)
    auto_width: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetTotalIR:
    column_offset: int
    function: AggregateFunction


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetFooterIR:
    label: str
    label_column_offset: int
    items: Sequence[SpreadsheetTotalIR]
    style: Style

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetConditionalRuleIR:
    condition: ResolvedFormula
    style: Style


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetRowIR:
    """One evaluated data row ordered like its table columns."""

    index: int
    values: Sequence[CellValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            tuple(normalize_cell_value(value) for value in self.values),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetTableIR:
    """A resolved table schema with a lazy row stream."""

    name: str | None
    anchor: CellAddress
    columns: Sequence[SpreadsheetColumnIR]
    rows: Iterable[SpreadsheetRowIR]
    header_style: Style = dataclasses.field(default_factory=Style)
    footer: SpreadsheetFooterIR | None = None
    rules: Sequence[SpreadsheetConditionalRuleIR] = ()
    autofilter: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rules", tuple(self.rules))


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetWorksheetIR:
    """An ordered collection of spreadsheet tables."""

    name: str
    tables: Sequence[SpreadsheetTableIR]
    freeze: Freeze | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetIR:
    """Versioned, read-only spreadsheet renderer contract."""

    worksheets: Sequence[SpreadsheetWorksheetIR]
    metadata: DocumentMetadata = dataclasses.field(default_factory=dict)
    version: int = SPREADSHEET_IR_VERSION
    kind: DocumentKind = dataclasses.field(
        default=DocumentKind.SPREADSHEET,
        init=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


__all__ = (
    "SPREADSHEET_IR_VERSION",
    "CellAddress",
    "ResolvedCellReference",
    "ResolvedFormula",
    "ResolvedFormulaBinary",
    "ResolvedFormulaLiteral",
    "ResolvedRangeReference",
    "SpreadsheetColumnIR",
    "SpreadsheetConditionalRuleIR",
    "SpreadsheetFooterIR",
    "SpreadsheetIR",
    "SpreadsheetRowIR",
    "SpreadsheetTableIR",
    "SpreadsheetTotalIR",
    "SpreadsheetWorksheetIR",
)
