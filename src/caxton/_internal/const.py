import operator
import re
from collections.abc import Callable, Mapping
from typing import Any, Final, TypeAlias

from caxton.core.formatting import BorderLineStyle
from caxton.core.ir import SpreadsheetBlockKind
from caxton.core.models import (
    AggregateFunction,
    BinaryOperator,
    Chart,
    ChartKind,
    FormulaOperator,
    Image,
    Matrix,
    Spacer,
    SpreadsheetTable,
    Stack,
    Title,
)

_OPERATORS: Final[dict[str, str]] = {
    FormulaOperator.ADD: "+",
    FormulaOperator.SUBTRACT: "-",
    FormulaOperator.MULTIPLY: "*",
    FormulaOperator.DIVIDE: "/",
    FormulaOperator.EQUAL: "=",
    FormulaOperator.NOT_EQUAL: "<>",
    FormulaOperator.LESS_THAN: "<",
    FormulaOperator.LESS_THAN_OR_EQUAL: "<=",
    FormulaOperator.GREATER_THAN: ">",
    FormulaOperator.GREATER_THAN_OR_EQUAL: ">=",
}
_PRECEDENCE: Final[dict[str, int]] = {
    FormulaOperator.EQUAL: 1,
    FormulaOperator.NOT_EQUAL: 1,
    FormulaOperator.LESS_THAN: 1,
    FormulaOperator.LESS_THAN_OR_EQUAL: 1,
    FormulaOperator.GREATER_THAN: 1,
    FormulaOperator.GREATER_THAN_OR_EQUAL: 1,
    FormulaOperator.ADD: 2,
    FormulaOperator.SUBTRACT: 2,
    FormulaOperator.MULTIPLY: 3,
    FormulaOperator.DIVIDE: 3,
}

_SEMANTIC_FEATURES: Final[frozenset[str]] = frozenset(
    (
        "semantic:boolean",
        "semantic:date",
        "semantic:datetime",
        "semantic:decimal",
        "semantic:duration",
        "semantic:integer",
        "semantic:link",
        "semantic:money",
        "semantic:percentage",
        "semantic:text",
        "semantic:time",
    ),
)

_MIME_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

_BORDER_STYLES: Final[dict[str, int]] = {
    BorderLineStyle.THIN: 1,
    BorderLineStyle.MEDIUM: 2,
    BorderLineStyle.THICK: 5,
    BorderLineStyle.DASHED: 3,
    BorderLineStyle.DOTTED: 4,
    BorderLineStyle.DOUBLE: 6,
}

_CHART_TYPES: Final[dict[str, str]] = {
    ChartKind.AREA: "area",
    ChartKind.BAR: "bar",
    ChartKind.COLUMN: "column",
    ChartKind.DOUGHNUT: "doughnut",
    ChartKind.LINE: "line",
    ChartKind.PIE: "pie",
    ChartKind.RADAR: "radar",
    ChartKind.SCATTER: "scatter",
}

_AGGREGATES: Final[dict[str, str]] = {
    AggregateFunction.SUM: "SUM",
    AggregateFunction.AVG: "AVERAGE",
    AggregateFunction.MIN: "MIN",
    AggregateFunction.MAX: "MAX",
    AggregateFunction.COUNT: "COUNT",
}

_TITLE_FONT_SIZES: Final[dict[int, float]] = {1: 16.0, 2: 14.0, 3: 12.0}

ROW_HEIGHT_PIXELS: Final[int] = 20
COLUMN_WIDTH_PIXELS: Final[int] = 64
SPREADSHEET_MAX_ROWS: Final[int] = 1_048_576
SPREADSHEET_MAX_COLUMNS: Final[int] = 16_384

_BlockKindPair: TypeAlias = tuple[type, SpreadsheetBlockKind]

_BLOCK_KINDS: Final[tuple[_BlockKindPair, ...]] = (
    (SpreadsheetTable, SpreadsheetBlockKind.TABLE),
    (Matrix, SpreadsheetBlockKind.MATRIX),
    (Title, SpreadsheetBlockKind.TITLE),
    (Spacer, SpreadsheetBlockKind.SPACER),
    (Image, SpreadsheetBlockKind.IMAGE),
    (Chart, SpreadsheetBlockKind.CHART),
    (Stack, SpreadsheetBlockKind.STACK),
)
_OVERLAPPING_KINDS: Final[frozenset[str]] = frozenset(
    (
        SpreadsheetBlockKind.TABLE,
        SpreadsheetBlockKind.MATRIX,
        SpreadsheetBlockKind.TITLE,
        SpreadsheetBlockKind.IMAGE,
        SpreadsheetBlockKind.CHART,
    ),
)

_CELL_ADDRESS: Final[re.Pattern[str]] = re.compile(
    r"^(?P<column>[A-Za-z]+)(?P<row>[1-9][0-9]*)$"
)

BinaryOperation = Callable[[Any, Any], object]

_BINARY_OPERATIONS: Final[Mapping[BinaryOperator, BinaryOperation]] = {
    BinaryOperator.ADD: operator.add,
    BinaryOperator.SUBTRACT: operator.sub,
    BinaryOperator.MULTIPLY: operator.mul,
    BinaryOperator.DIVIDE: operator.truediv,
    BinaryOperator.EQUAL: operator.eq,
    BinaryOperator.NOT_EQUAL: operator.ne,
    BinaryOperator.LESS_THAN: operator.lt,
    BinaryOperator.LESS_THAN_OR_EQUAL: operator.le,
    BinaryOperator.GREATER_THAN: operator.gt,
    BinaryOperator.GREATER_THAN_OR_EQUAL: operator.ge,
    BinaryOperator.AND: lambda left, right: left and right,
    BinaryOperator.OR: lambda left, right: left or right,
}
_NOT_EVALUATED = object()
_SOURCE_END = object()
