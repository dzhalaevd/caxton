from __future__ import annotations

import dataclasses
import enum
from collections.abc import Iterator, Sequence
from typing import Any, TypeAlias

from caxton.core.errors import CaxtonTypeError, CaxtonValueError
from caxton.core.formatting import (
    DocumentTheme,
    Style,
    StyleInput,
    StyleSheet,
)
from caxton.core.protocols.data import DataSource

from ._validation import (
    require_name,
    require_non_negative,
    require_optional_name,
    require_positive,
)
from .columns import Column
from .common import DocumentKind, DocumentMetadata, freeze_metadata
from .expressions import ColumnRef, Expression, contains_aggregate
from .formulas import Formula, FormulaInput, TableReference, as_formula
from .templates import TemplateRepeat, TemplateSpecification

DEFAULT_OBJECT_WIDTH = 480
DEFAULT_OBJECT_HEIGHT = 288


@dataclasses.dataclass(frozen=True, slots=True)
class Freeze:
    """Number of leading worksheet rows and columns kept visible.

    The default freezes the first row, which is the common header case.
    """

    rows: int = 1
    columns: int = 0

    def __post_init__(self) -> None:
        require_non_negative(self.rows, "Freeze rows")
        require_non_negative(self.columns, "Freeze columns")
        if self.rows == 0 and self.columns == 0:
            message = "Freeze must include at least one row or column"
            raise CaxtonValueError(message)


class AggregateFunction(enum.StrEnum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


@dataclasses.dataclass(frozen=True, slots=True, init=False)
class Total:
    """Aggregate placed in one semantic column of a totals footer.

    Every aggregate, including ``COUNT``, names the column it is placed in and
    aggregates that column's values.
    """

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
            raise CaxtonValueError(message) from error
        object.__setattr__(self, "function", normalized)
        self.__post_init__()

    def __post_init__(self) -> None:
        require_name(self.column, "Total column")


@dataclasses.dataclass(frozen=True, slots=True)
class Totals:
    """One totals/footer row.

    ``label_column`` selects where the label is written; when it is ``None``
    the first column without an aggregate is used.
    """

    label: str = "Total"
    items: Sequence[Total] = ()
    label_column: str | None = None
    style: StyleInput | None = None

    def __post_init__(self) -> None:
        require_name(self.label, "Totals label")
        require_optional_name(self.label_column, "Totals label column")
        items = tuple(self.items)
        for item in items:
            if not isinstance(item, Total):
                message = "Totals items must be Total values"
                raise CaxtonTypeError(message)
        object.__setattr__(self, "items", items)


@dataclasses.dataclass(frozen=True, slots=True)
class ConditionalRule:
    """Formula-based conditional cell style for a table data range."""

    condition: Formula
    style: StyleInput

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", as_formula(self.condition))
        _validate_style(self.style, "Conditional rule style")


def when(condition: FormulaInput, *, style: StyleInput) -> ConditionalRule:
    """Declare a conditional style applied to a table data range.

    Returns:
        An immutable conditional rule.
    """
    return ConditionalRule(condition=as_formula(condition), style=style)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class TableData:
    """Shared semantic schema and its lazy row source."""

    source: DataSource[Any]
    columns: Sequence[Column]

    def __post_init__(self) -> None:
        if not isinstance(self.source, DataSource):
            message = "Table data source must implement the DataSource protocol"
            raise CaxtonTypeError(message)
        columns = tuple(self.columns)
        for column in columns:
            if not isinstance(column, Column):
                message = "Table columns must be Column values"
                raise CaxtonTypeError(message)
        object.__setattr__(self, "columns", columns)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class SpreadsheetTable:
    """Spreadsheet placement of semantic table data.

    ``freeze_header`` keeps the header row of this table visible; worksheet
    level freezing stays in ``Worksheet.freeze``. ``auto_width`` applies to
    every column that declares no explicit width, while a column's own
    ``auto_width`` always wins.
    """

    data: TableData
    name: str | None = None
    anchor: str | None = None
    style: StyleInput | None = None
    header_style: StyleInput | None = None
    footer: Totals | None = None
    rules: Sequence[ConditionalRule] = ()
    autofilter: bool = False
    freeze_header: bool = False
    auto_width: bool = False
    into: ColumnRef | TemplateRepeat | None = None

    def __post_init__(self) -> None:  # noqa: WPS238
        require_optional_name(self.name, "Table name")
        require_optional_name(self.anchor, "Table anchor")
        if self.anchor is not None and self.into is not None:
            message = "Table anchor and template target are mutually exclusive"
            raise CaxtonValueError(message)
        if self.into is not None and not isinstance(
            self.into,
            (ColumnRef, TemplateRepeat),
        ):
            message = "Table template target must be created with ref() or repeat()"
            raise CaxtonTypeError(message)
        if self.footer is not None and not isinstance(self.footer, Totals):
            message = "Table footer must be a Totals value"
            raise CaxtonTypeError(message)
        rules = tuple(self.rules)
        for rule in rules:
            if not isinstance(rule, ConditionalRule):
                message = "Table rules must be ConditionalRule values"
                raise CaxtonTypeError(message)
        object.__setattr__(self, "rules", rules)

    @property
    def columns(self) -> Sequence[Column]:
        return self.data.columns


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Matrix:
    """Declarative pivot-like spreadsheet block over one row source."""

    source: DataSource[Any]
    row_dimensions: Sequence[Column]
    column_dimensions: Sequence[Column]
    value: Column
    anchor: str | None = None
    style: StyleInput | None = None
    header_style: StyleInput | None = None

    def __post_init__(self) -> None:  # noqa: C901, WPS238
        if not isinstance(self.source, DataSource):
            message = "Matrix source must implement the DataSource protocol"
            raise CaxtonTypeError(message)
        rows = tuple(self.row_dimensions)
        columns = tuple(self.column_dimensions)
        if not rows or not columns:
            message = "Matrix requires row and column dimensions"
            raise CaxtonValueError(message)
        dimensions = (*rows, *columns)
        for dimension in dimensions:
            if not isinstance(dimension, Column):
                message = "Matrix dimensions must be Column values"
                raise CaxtonTypeError(message)
            if dimension.excel_formula is not None or dimension.source is None:
                message = "Matrix dimensions cannot use Excel formulas"
                raise CaxtonValueError(message)
            if isinstance(dimension.source, Expression) and contains_aggregate(
                dimension.source,
            ):
                message = "Matrix dimensions must be non-aggregate expressions"
                raise CaxtonTypeError(message)
        if not isinstance(self.value, Column):
            message = "Matrix value must be a Column"
            raise CaxtonTypeError(message)
        if self.value.excel_formula is not None or self.value.source is None:
            message = "Matrix value cannot use an Excel formula"
            raise CaxtonValueError(message)
        identifiers = [item.id for item in (*dimensions, self.value)]
        if len(set(identifiers)) != len(identifiers):
            message = "Matrix dimensions and value must have unique column ids"
            raise CaxtonValueError(message)
        require_optional_name(self.anchor, "Matrix anchor")
        object.__setattr__(self, "row_dimensions", rows)
        object.__setattr__(self, "column_dimensions", columns)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Title:
    """One line of heading text occupying a single worksheet row."""

    text: str
    level: int = 1
    span: int = 1
    style: StyleInput | None = None
    anchor: str | None = None

    def __post_init__(self) -> None:
        require_name(self.text, "Title text")
        require_positive(self.level, "Title level")
        require_positive(self.span, "Title span")
        require_optional_name(self.anchor, "Title anchor")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Spacer:
    """Empty layout gap measured in whole rows and columns."""

    rows: int = 1
    columns: int = 1
    anchor: str | None = None

    def __post_init__(self) -> None:
        require_non_negative(self.rows, "Spacer rows")
        require_non_negative(self.columns, "Spacer columns")
        require_optional_name(self.anchor, "Spacer anchor")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Image:
    """Picture placed by declared pixel size instead of engine coordinates."""

    source: str | bytes
    width: int = DEFAULT_OBJECT_WIDTH
    height: int = DEFAULT_OBJECT_HEIGHT
    name: str | None = None
    description: str | None = None
    anchor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, (str, bytes)):
            message = "Image source must be a path string or raw bytes"
            raise CaxtonTypeError(message)
        if isinstance(self.source, str) and not self.source.strip():
            message = "Image source cannot be empty"
            raise CaxtonValueError(message)
        require_positive(self.width, "Image width")
        require_positive(self.height, "Image height")
        require_optional_name(self.name, "Image name")
        require_optional_name(self.anchor, "Image anchor")


class ChartKind(enum.StrEnum):
    """Closed set of chart shapes supported by the spreadsheet family."""

    AREA = "area"
    BAR = "bar"
    COLUMN = "column"
    DOUGHNUT = "doughnut"
    LINE = "line"
    PIE = "pie"
    RADAR = "radar"
    SCATTER = "scatter"


@dataclasses.dataclass(frozen=True, slots=True, eq=False, init=False)
class Chart:
    """Chart whose data is bound to columns of one named table."""

    source: TableReference
    x: str  # noqa: WPS111
    y: Sequence[str]  # noqa: WPS111
    kind: ChartKind = ChartKind.COLUMN
    title: str | None = None
    width: int = DEFAULT_OBJECT_WIDTH
    height: int = DEFAULT_OBJECT_HEIGHT
    name: str | None = None
    anchor: str | None = None

    def __init__(  # noqa: WPS211, WPS213
        self,
        source: TableReference,
        *,
        x: str,  # noqa: WPS111
        y: str | Sequence[str],  # noqa: WPS111
        kind: ChartKind | str = ChartKind.COLUMN,
        title: str | None = None,
        width: int = DEFAULT_OBJECT_WIDTH,
        height: int = DEFAULT_OBJECT_HEIGHT,
        name: str | None = None,
        anchor: str | None = None,
    ) -> None:
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", (y,) if isinstance(y, str) else tuple(y))
        object.__setattr__(self, "kind", _chart_kind(kind))
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "anchor", anchor)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.source, TableReference):
            message = "Chart source must be a table reference"
            raise CaxtonTypeError(message)
        require_name(self.x, "Chart category column")
        if not self.y:
            message = "Chart requires at least one value column"
            raise CaxtonValueError(message)
        for column in self.y:
            require_name(column, "Chart value column")
        require_positive(self.width, "Chart width")
        require_positive(self.height, "Chart height")
        require_optional_name(self.name, "Chart name")
        require_optional_name(self.anchor, "Chart anchor")


class BlockDirection(enum.StrEnum):
    """Direction in which a flow container advances its layout cursor."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@dataclasses.dataclass(frozen=True, slots=True, eq=False, init=False)
class Stack:
    """Minimal flow container placing nested blocks one after another."""

    items: Sequence[SpreadsheetBlock]
    direction: BlockDirection = BlockDirection.VERTICAL
    gap: int = 0
    anchor: str | None = None

    def __init__(
        self,
        items: Sequence[SpreadsheetBlock],
        direction: BlockDirection | str = BlockDirection.VERTICAL,
        gap: int = 0,
        anchor: str | None = None,
    ) -> None:
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "direction", _block_direction(direction))
        object.__setattr__(self, "gap", gap)
        object.__setattr__(self, "anchor", anchor)
        self.__post_init__()

    def __post_init__(self) -> None:
        require_non_negative(self.gap, "Stack gap")
        require_optional_name(self.anchor, "Stack anchor")


SpreadsheetBlock: TypeAlias = (
    SpreadsheetTable | Matrix | Title | Spacer | Image | Chart | Stack
)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Worksheet:
    """Immutable sequence of spreadsheet blocks."""

    name: str
    blocks: Sequence[SpreadsheetBlock]
    freeze: Freeze | None = None

    @property
    def tables(self) -> Sequence[SpreadsheetTable]:
        """Every table block of this worksheet, including nested ones."""
        return tuple(iter_tables(self.blocks))

    def __post_init__(self) -> None:
        require_name(self.name, "Worksheet name")
        object.__setattr__(self, "blocks", tuple(self.blocks))


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class SpreadsheetDocument:
    """Backend-independent spreadsheet document intent."""

    worksheets: Sequence[Worksheet]
    metadata: DocumentMetadata = dataclasses.field(default_factory=dict)
    styles: StyleSheet = dataclasses.field(default_factory=lambda: StyleSheet({}))
    theme: DocumentTheme = dataclasses.field(default_factory=DocumentTheme)
    template: TemplateSpecification | None = None
    kind: DocumentKind = dataclasses.field(
        default=DocumentKind.SPREADSHEET,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.template is not None and not isinstance(
            self.template,
            TemplateSpecification,
        ):
            message = "Spreadsheet template must be created with template()"
            raise CaxtonTypeError(message)
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


def _validate_style(value: StyleInput, label: str) -> None:
    if not isinstance(value, (Style, str)):
        message = f"{label} must be a Style or a style name"
        raise CaxtonTypeError(message)


def _block_direction(value: BlockDirection | str) -> BlockDirection:
    try:
        return BlockDirection(value)
    except ValueError as error:
        message = f"Unsupported stack direction {value!r}"
        raise CaxtonValueError(message) from error


def _chart_kind(value: ChartKind | str) -> ChartKind:
    try:
        return ChartKind(value)
    except ValueError as error:
        message = f"Unsupported chart kind {value!r}"
        raise CaxtonValueError(message) from error


def iter_blocks(
    blocks: Sequence[SpreadsheetBlock],
) -> Iterator[SpreadsheetBlock]:
    """Walk blocks depth-first, yielding containers before their items.

    Yields:
        Every declared block, including blocks nested in a ``Stack``.
    """
    for block in blocks:
        yield block
        if isinstance(block, Stack):
            yield from iter_blocks(block.items)


def iter_tables(
    blocks: Sequence[SpreadsheetBlock],
) -> Iterator[SpreadsheetTable]:
    """Walk every table block, including tables nested in a ``Stack``.

    Yields:
        Each declared spreadsheet table in declaration order.
    """
    for block in iter_blocks(blocks):
        if isinstance(block, SpreadsheetTable):
            yield block


__all__ = (
    "DEFAULT_OBJECT_HEIGHT",
    "DEFAULT_OBJECT_WIDTH",
    "AggregateFunction",
    "BlockDirection",
    "Chart",
    "ChartKind",
    "ConditionalRule",
    "Freeze",
    "Image",
    "Matrix",
    "Spacer",
    "SpreadsheetBlock",
    "SpreadsheetDocument",
    "SpreadsheetTable",
    "Stack",
    "TableData",
    "Title",
    "Total",
    "Totals",
    "Worksheet",
    "iter_blocks",
    "iter_tables",
    "when",
)
