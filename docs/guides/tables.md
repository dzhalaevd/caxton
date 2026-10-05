# Tables and data

A table joins a lazy row source to an ordered column schema. Caxton does not
infer columns from the first row or eagerly reshape rows in an ordinary table.
Declared grouping and aggregation prepare the source once and may change its
output shape; a matrix also discovers its axes from data. You declare those
operations explicitly.

## Start with one row shape

Rows may be mappings or Python objects. A frozen dataclass works well when the
application already has a typed record:

```python
import dataclasses

from caxton import integer, table, text


@dataclasses.dataclass(frozen=True)
class Book:
    title: str
    author: str
    pages: int


books = (
    Book("Kindred", "Octavia E. Butler", 288),
    Book("Piranesi", "Susanna Clarke", 272),
)

books_table = table(
    source=books,
    columns=(
        text(source="title", title="Title"),
        text(source="author", title="Author"),
        integer(source="pages", title="Pages"),
    ),
    name="books",
)
```

The two uses of `source` operate at different levels. `table(source=books)`
supplies rows. `text(source="title")` reads one exact field from each row.
Keeping both arguments keyword-only makes that distinction visible at the call
site.

A mapping uses `row[field]`. Dataclasses, `NamedTuple` values and ordinary
objects use exact attribute access. A bare mapping or object is treated as one
row; an iterable supplies many rows.

Caxton does not call `asdict()`, `model_dump()`, `vars()` or `dir()`. It reads
only the fields named by the schema, when the rows are evaluated.

## Keep identity separate from storage

A column carries three names with different jobs:

| Name | Used for |
|------|----------|
| `id` | References, charts, grouping and testing views. |
| `source` | Reading a value from the input row. |
| `title` | The header shown in the workbook. |

For an exact string source, the source also becomes the default id. The first
column above therefore has id `title`, reads the `title` attribute and displays
`Title`. Do not repeat the same value as both arguments: write
`text(source="title")`, not `text(id="title", source="title")`.

Declare all three when the application name and the visible label should move
independently:

```python
book_title = text(
    id="book_title",
    source="title",
    title="Book",
)
```

Changing `title="Book title"` later does not break a chart or expression that
refers to `book_title`. Specify `id` only when it intentionally differs from an
exact string source, or when a callable, nested path, expression or spreadsheet
formula provides no exact field name from which Caxton can derive one.

Table names serve the same purpose at the next level. Name a table when another
block or a testing view must find it. Names are workbook-wide, including after
several documents have been composed.

## Read nested and derived values explicitly

A dot inside a string is an ordinary field name. Use `path()` when the data is
nested:

```python
from caxton import path


@dataclasses.dataclass(frozen=True)
class Edition:
    year: int


@dataclasses.dataclass(frozen=True)
class CatalogEntry:
    title: str
    edition: Edition


published = integer(
    id="published",
    source=path("edition", "year"),
    title="Published",
)
```

If a value needs the complete row, a callable source receives that original
object:

```python
label = text(
    id="label",
    source=lambda book: f"{book.title} by {book.author}",
    title="Label",
)
```

Use a callable for application-owned row logic. Use `field()`, `path()` and
`ref()` expressions when dependencies should remain visible to validation and
inspection. Live spreadsheet formulas are a separate value source evaluated by
the finished workbook.

## Reuse the schema, bind the rows later

`ColumnSchema` gives a stable name and order to a reusable column tuple. It
does not inspect rows or create a second schema object at runtime:

```python
from collections.abc import Iterable

from caxton import ColumnSchema
from caxton.core.models import SpreadsheetTable


class BookColumns(ColumnSchema):
    title = text(source="title", title="Title")
    author = text(source="author", title="Author")
    pages = integer(source="pages", title="Pages")


def catalog_table(rows: Iterable[Book]) -> SpreadsheetTable:
    return table(
        source=rows,
        columns=BookColumns.columns,
        name="books",
    )
```

Pass `BookColumns.columns`, not the class itself. The class-body order is the
table order, and each public attribute name must match its column id. A subclass
may replace a column without moving it or append new columns at the end. For a
one-off ordering, build an explicit tuple from the named attributes.

The schema is the reusable part. Each call to `catalog_table()` binds it to a
fresh row source and returns a new immutable table.

## Laziness is part of the contract

Creating a table wraps its input once but does not request a row. Structural
validation is also non-consuming:

```python
from caxton import render, sheet, spreadsheet, validate

events: list[str] = []


def incoming_books():
    events.append("started")
    yield Book("A Wizard of Earthsea", "Ursula K. Le Guin", 205)


streamed_table = catalog_table(incoming_books())
document = spreadsheet(sheet("Books", streamed_table))

validate(document)
assert events == []

render(document)
assert events == ["started"]
```

What happens on a second operation depends on the source:

| Input | Repeatability | Row count |
|-------|---------------|-----------|
| Built-in container such as `list` or `tuple` | `REITERABLE` | Known without reading rows. |
| Iterator or generator | `ONE_SHOT` | Unknown. |
| Other iterable | `UNKNOWN` | Unknown; Caxton does not call `len()` on it. |
| Custom `DataSource` | Reported by `DataSourceInfo`, otherwise `UNKNOWN`. | Reported by `DataSourceInfo`, otherwise unknown. |

A second pass over a one-shot source raises `DataSourceConsumedError`; it never
silently produces an empty table. Materialize the rows deliberately when two
documents or two renders need independent passes:

```python
reusable_books = tuple(incoming_books())
```

An unknown row count also affects flow layout and table-range references. See
[Worksheets and blocks](worksheets-and-blocks.md) before placing another
implicit block after a streamed table.

## Group rows when one output row represents a group

Call `.grouped()` on the columns that define the output groups. Their declaration order defines the hierarchy, from the
outer group to the inner group:

```python
from caxton import field

inventory = (
    {"genre": "Fiction", "format": "Hardcover", "copies": 2},
    {"genre": "Fiction", "format": "Paperback", "copies": 4},
    {"genre": "Essays", "format": "Paperback", "copies": 3},
)

inventory_summary = table(
    source=inventory,
    columns=(
        text(source="genre", title="Genre").grouped(
            merge=True,
            order="ascending",
        ),
        text(source="format", title="Format").grouped(),
        integer(
            id="copies",
            source=field("copies").agg(sum),
            title="Copies",
        ),
    ),
)
```

Each leaf group produces one output row. `first_seen` is the default order; `ascending` and `descending` sort one level,
with `None` last. `merge=True` asks the renderer to merge adjacent cells that belong to the same group. Group identity
keeps the Python type and decimal scale, so `True`, `1`, `Decimal("1")` and `Decimal("1.0")` are distinct keys.

Grouping prepares the complete source once because the number and order of output rows depend on its values. A generator
is still consumed in one pass, but the grouped result is shape-dependent and cannot use XlsxWriter's append-only
streaming plan.

## Use a matrix when data values should become columns

A matrix uses source values to discover its row and column axes. Choose it when a dimension such as format belongs across
the top of the result instead of down an ordinary column:

```python
from caxton import matrix

copies_by_format = matrix(
    source=inventory,
    row=text(source="genre", title="Genre").grouped(order="ascending"),
    column=text(source="format", title="Format").grouped(order="ascending"),
    value=integer(
        id="copies",
        source=field("copies").agg(sum),
        title="Copies",
    ),
)
```

The row and column axes may each contain one dimension or a sequence. A typed column carries its title, format, width and
ordering into the result. The matrix discovers axis keys during its single preparation pass, so its width and height are
data-dependent.

Several source rows may map to the same matrix coordinate. Use an aggregate value when that is valid; a plain value
raises `MatrixConflictError` rather than choosing one row. Missing coordinates produce empty cells. After axis discovery,
Caxton can emit sparse output rows without retaining a dense Cartesian result.

See [Formulas and computation](formulas.md#know-where-aggregation-happens) for the aggregate scope used by ordinary
tables, grouped tables and matrices.

## Adapt unusual sources at the boundary

The public `DataSource` protocol has two required operations: iterate rows and
read one named field. `DataSourceInfo` may additionally report repeatability
and a row count.

This source translates an external field convention without changing the
table's semantic schema:

```python
from collections.abc import Iterator, Mapping, Sequence

from caxton.core.protocols import Repeatability


class CatalogRows:
    _fields = {
        "title": "bookTitle",
        "author": "bookAuthor",
        "pages": "pageCount",
    }

    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self._rows = rows

    @property
    def repeatability(self) -> Repeatability:
        return Repeatability.REITERABLE

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        return iter(self._rows)

    def get_value(self, row: Mapping[str, object], field: str) -> object:
        return row[self._fields[field]]


external_rows = CatalogRows(
    (
        {
            "bookTitle": "Kindred",
            "bookAuthor": "Octavia E. Butler",
            "pageCount": 288,
        },
    ),
)

external_table = table(
    source=external_rows,
    columns=BookColumns.columns,
    name="external_books",
)
```

Use this boundary for row-oriented sources with unusual access rules. Pandas,
Polars and Arrow inputs are rejected because their columnar execution model
needs a separate batch contract. ORM query planning, eager loading and session
lifetime also stay in the application; Caxton only consumes the rows it is
given. The complete extension contracts are documented in
[`caxton.core.protocols`](../reference/protocols.md).
