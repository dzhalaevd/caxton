import dataclasses
from typing import ClassVar

from typing_extensions import assert_type

from caxton import (
    AutoWidth,
    Column,
    ColumnSchema,
    Formula,
    SemanticType,
    Text,
    field,
    literal,
)
from caxton.core.formatting import Alignment, StyleInput
from caxton.core.models import ColumnSource, LiteralExpression


class Rating(SemanticType):
    name: ClassVar[str] = "rating"


class Columns(ColumnSchema):
    rating = Column(semantic_type=Rating(), source="rating")
    label = Column(semantic_type=Text(), source="label")


column = Column(semantic_type=Rating(), source="rating")

broad = Column(
    semantic_type=Text(),
    id="label",
    source=field("name"),
    alignment="right",
    auto_width=True,
)

replaced = dataclasses.replace(
    broad,
    alignment="center",  # type: ignore[arg-type]
    auto_width=True,  # type: ignore[arg-type]
)

assert_type(column, Column)
assert_type(column.id, str)
assert_type(column.source, ColumnSource | None)
assert_type(column.excel_formula, Formula | None)
assert_type(column.alignment, Alignment | None)
assert_type(column.auto_width, AutoWidth | None)
assert_type(column.style, StyleInput | None)
assert_type(broad, Column)
assert_type(broad.alignment, Alignment | None)
assert_type(broad.auto_width, AutoWidth | None)
assert_type(replaced, Column)
assert_type(Columns.rating, Column)
assert_type(Columns.rating.id, str)
assert_type(Columns.columns, tuple[Column, ...])
assert_type(literal(None), LiteralExpression)
