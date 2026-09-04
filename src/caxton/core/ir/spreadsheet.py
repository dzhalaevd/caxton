from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Iterator, Sequence, Sized
from typing import TypeAlias

from caxton.core._compat import Self, StrEnum, final
from caxton.core._values import normalize_cell_value
from caxton.core.errors import (
    CaxtonTypeError,
    CaxtonValueError,
    InvalidOperationError,
)
from caxton.core.formatting import Alignment, AutoWidth, DisplayFormat, Style
from caxton.core.models.common import (
    DocumentKind,
    DocumentMetadata,
    freeze_metadata,
)
from caxton.core.models.formulas import FormulaOperator
from caxton.core.models.spreadsheet import AggregateFunction, ChartKind, Freeze
from caxton.core.types import SemanticType
from caxton.core.values import CellValue

SPREADSHEET_IR_VERSION = 6


def _require_positive_integer(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"{label} must be an integer"
        raise CaxtonTypeError(message)
    if value < 1:
        message = f"{label} must be positive"
        raise CaxtonValueError(message)


def _require_cell_address(value: object, label: str) -> None:
    if not isinstance(value, CellAddress):
        message = f"{label} must be a CellAddress"
        raise CaxtonTypeError(message)


def _require_ordered_range(start: CellAddress, end: CellAddress) -> None:
    if end.row < start.row or end.column < start.column:
        message = "Cell range end must not precede its start"
        raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class CellAddress:
    """One-based backend-independent spreadsheet coordinate."""

    row: int
    column: int

    def __post_init__(self) -> None:
        _require_positive_integer(self.row, "Cell row")
        _require_positive_integer(self.column, "Cell column")


@dataclasses.dataclass(frozen=True, slots=True)
class CellRange:
    """Inclusive rectangular region of one worksheet."""

    start: CellAddress
    end: CellAddress

    def __post_init__(self) -> None:
        _require_cell_address(self.start, "Cell range start")
        _require_cell_address(self.end, "Cell range end")
        _require_ordered_range(self.start, self.end)

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
    """Base for backend-independent formulas with resolved semantic references.

    The set of nodes is closed: :data:`ResolvedFormulaNode` enumerates it, so a
    renderer can match it exhaustively and a type checker reports a forgotten
    branch when the IR grows a node.
    """

    def __new__(cls, *_args: object, **_kwargs: object) -> Self:
        """Create a concrete resolved formula node.

        Returns:
            A new instance of a concrete node type.

        Raises:
            CaxtonTypeError: If the abstract base itself is instantiated.
        """
        if cls is ResolvedFormula:
            message = "ResolvedFormula is abstract and cannot be instantiated"
            raise CaxtonTypeError(message)
        return object.__new__(cls)


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
        _require_positive_integer(self.column, "Resolved cell column")
        if self.row is not None:
            _require_positive_integer(self.row, "Resolved cell row")


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedRangeReference(ResolvedFormula):
    sheet_name: str
    start: CellAddress
    end: CellAddress
    table_name: str
    column_title: str
    column_absolute: bool = False
    row_absolute: bool = False

    def __post_init__(self) -> None:
        _require_cell_address(self.start, "Resolved range start")
        _require_cell_address(self.end, "Resolved range end")
        _require_ordered_range(self.start, self.end)


ResolvedFormulaNode: TypeAlias = (
    ResolvedFormulaLiteral
    | ResolvedFormulaBinary
    | ResolvedCellReference
    | ResolvedRangeReference
)


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
    auto_width: AutoWidth | None = None
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


@final
class RowStream:
    """One-shot stream of resolved rows carried by a table.

    The IR is read-only, but rows stay lazy: the stream may wrap a generator or
    a one-shot data source, so it is delivered exactly once. A second pass
    raises instead of silently yielding nothing, which is what a bare exhausted
    iterator would do.
    """

    __slots__ = ("_consumed", "_rows")

    def __init__(self, rows: Iterable[SpreadsheetRowIR]) -> None:
        self._rows = rows
        self._consumed = False

    @property
    def consumed(self) -> bool:
        """Whether the stream has already been handed out."""
        return self._consumed

    def consume(self) -> Iterator[SpreadsheetRowIR]:
        """Return the row iterator exactly once.

        Returns:
            An iterator over the resolved rows.

        Raises:
            InvalidOperationError: If the stream was already consumed.
        """
        if self._consumed:
            message = (
                "Table rows are a one-shot stream and were already consumed; "
                "collect them once if the renderer needs two passes"
            )
            raise InvalidOperationError(message)
        self._consumed = True
        return iter(self._rows)

    def __iter__(self) -> Iterator[SpreadsheetRowIR]:
        """Iterate the stream once.

        Returns:
            An iterator over the resolved rows.
        """
        return self.consume()

    @property
    def row_count(self) -> int | None:
        """Number of rows when the underlying source knows it without reading."""
        return len(self._rows) if isinstance(self._rows, Sized) else None

    def materialized(self) -> RowStream:
        """Return an unconsumed stream over the same rows, read into memory.

        Consumes this stream when its rows are still lazy, so the returned
        stream is the one to keep. Calling it again on a materialized stream
        hands out a fresh unconsumed stream over the same rows, which is how a
        renderer that needs a second pass pays for it explicitly.

        Returns:
            An unconsumed stream over a materialized row sequence.
        """
        if isinstance(self._rows, tuple):
            return RowStream(self._rows)
        return RowStream(tuple(self.consume()))


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetTableIR:
    """A resolved table schema with a lazy, single-pass row stream.

    ``rows`` is a :class:`RowStream`: renderers consume it exactly once. A bare
    iterable is wrapped, so the contract holds however the table was built.
    """

    name: str | None
    anchor: CellAddress
    columns: Sequence[SpreadsheetColumnIR]
    rows: RowStream
    header_style: Style = dataclasses.field(default_factory=Style)
    footer: SpreadsheetFooterIR | None = None
    rules: Sequence[SpreadsheetConditionalRuleIR] = ()
    autofilter: bool = False
    merges: Sequence[CellRange] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rows, RowStream):
            object.__setattr__(self, "rows", RowStream(self.rows))
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
        _require_positive_integer(self.span, "Text span")


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
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            message = "Spreadsheet IR version must be an integer"
            raise CaxtonTypeError(message)
        if self.version != SPREADSHEET_IR_VERSION:
            message = f"Unsupported Spreadsheet IR version {self.version!r}"
            raise CaxtonValueError(message)


__all__ = (
    "SPREADSHEET_IR_VERSION",
    "CellAddress",
    "CellRange",
    "ResolvedCellReference",
    "ResolvedFormula",
    "ResolvedFormulaBinary",
    "ResolvedFormulaLiteral",
    "ResolvedFormulaNode",
    "ResolvedRangeReference",
    "RowStream",
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
