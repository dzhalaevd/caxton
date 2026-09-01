from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence

from caxton.core._compat import StrEnum
from caxton.core._values import normalize_cell_value
from caxton.core.formatting import Alignment, DisplayFormat, Style
from caxton.core.models.common import (
    DocumentKind,
    DocumentMetadata,
    freeze_metadata,
)
from caxton.core.models.formulas import FormulaOperator
from caxton.core.models.spreadsheet import AggregateFunction, ChartKind, Freeze
from caxton.core.types import SemanticType
from caxton.core.values import CellValue

SPREADSHEET_IR_VERSION = 5


@dataclasses.dataclass(frozen=True, slots=True)
class CellAddress:
    """One-based backend-independent spreadsheet coordinate."""

    row: int
    column: int

    def __post_init__(self) -> None:
        if self.row < 1 or self.column < 1:
            message = "Cell coordinates must be positive"
            raise ValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class CellRange:
    """Inclusive rectangular region of one worksheet."""

    start: CellAddress
    end: CellAddress

    def __post_init__(self) -> None:
        if self.end.row < self.start.row or self.end.column < self.start.column:
            message = "Cell range end must not precede its start"
            raise ValueError(message)

    @property
    def rows(self) -> int:
        """Number of worksheet rows covered by this range."""
        return self.end.row - self.start.row + 1

    @property
    def columns(self) -> int:
        """Number of worksheet columns covered by this range."""
        return self.end.column - self.start.column + 1

    def intersects(self, other: CellRange) -> bool:
        """Return whether two ranges share at least one cell."""
        return (
            self.start.row <= other.end.row
            and other.start.row <= self.end.row
            and self.start.column <= other.end.column
            and other.start.column <= self.end.column
        )


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
    matrix_key: tuple[CellValue, ...] | None = None


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
    merges: Sequence[CellRange] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "merges", tuple(self.merges))


class SpreadsheetBlockKind(StrEnum):
    """Stable identity of one resolved spreadsheet layout block."""

    TABLE = "table"
    MATRIX = "matrix"
    TITLE = "title"
    SPACER = "spacer"
    IMAGE = "image"
    CHART = "chart"
    STACK = "stack"


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetPlacementIR:
    """Resolved position and occupied range of one layout block."""

    kind: SpreadsheetBlockKind
    path: str
    anchor: CellAddress
    occupied: CellRange | None
    name: str | None = None
    explicit: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetTextIR:
    """Resolved heading text written into a single worksheet row."""

    anchor: CellAddress
    text: str
    span: int = 1
    style: Style = dataclasses.field(default_factory=Style)

    def __post_init__(self) -> None:
        if self.span < 1:
            message = "Text span must be positive"
            raise ValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetImageIR:
    """Resolved picture placement with its declared pixel size."""

    anchor: CellAddress
    source: str | bytes
    width: int
    height: int
    name: str | None = None
    description: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetSeriesIR:
    """One resolved chart series bound to a physical worksheet range."""

    name: str
    values: CellRange
    categories: CellRange | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetChartIR:
    """Resolved chart placement with physical data ranges."""

    anchor: CellAddress
    kind: ChartKind
    sheet_name: str
    series: Sequence[SpreadsheetSeriesIR]
    title: str | None = None
    width: int = 480
    height: int = 288
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "series", tuple(self.series))


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetWorksheetIR:
    """An ordered collection of resolved spreadsheet layout blocks."""

    name: str
    tables: Sequence[SpreadsheetTableIR]
    freeze: Freeze | None = None
    texts: Sequence[SpreadsheetTextIR] = ()
    images: Sequence[SpreadsheetImageIR] = ()
    charts: Sequence[SpreadsheetChartIR] = ()
    placements: Sequence[SpreadsheetPlacementIR] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "texts", tuple(self.texts))
        object.__setattr__(self, "images", tuple(self.images))
        object.__setattr__(self, "charts", tuple(self.charts))
        object.__setattr__(self, "placements", tuple(self.placements))


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
    "CellRange",
    "ResolvedCellReference",
    "ResolvedFormula",
    "ResolvedFormulaBinary",
    "ResolvedFormulaLiteral",
    "ResolvedRangeReference",
    "SpreadsheetBlockKind",
    "SpreadsheetChartIR",
    "SpreadsheetColumnIR",
    "SpreadsheetConditionalRuleIR",
    "SpreadsheetFooterIR",
    "SpreadsheetIR",
    "SpreadsheetImageIR",
    "SpreadsheetPlacementIR",
    "SpreadsheetRowIR",
    "SpreadsheetSeriesIR",
    "SpreadsheetTableIR",
    "SpreadsheetTextIR",
    "SpreadsheetTotalIR",
    "SpreadsheetWorksheetIR",
)
