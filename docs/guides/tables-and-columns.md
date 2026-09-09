# Tables and columns

## Creating a table

```python
from caxton import table, text

people = table(
    source=[{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}],
    columns=(text(source="name", title="Name"),),
    name="people",
)
```

`table()` accepts two required keyword-only arguments: `source` for the rows and
`columns` for the ordered semantic schema. The remaining options are:

| Option          | Meaning                                                              |
|-----------------|----------------------------------------------------------------------|
| `name`          | Semantic table name used by `table_ref()`, charts and testing views. |
| `anchor`        | Explicit A1 placement instead of flow layout.                        |
| `style`         | Style (or style name) applied to data cells.                         |
| `header_style`  | Style applied to the header row.                                     |
| `footer`        | A `Totals` row, or a bare sequence of `Total` aggregates.            |
| `rules`         | Conditional formatting rules created with `when()`.                  |
| `autofilter`    | Adds the spreadsheet autofilter to the table range.                  |
| `freeze_header` | Keeps this table's header row visible.                               |
| `auto_width`    | Sizes columns without explicit widths; accepts `True` or `AutoWidth`. |
| `into`          | Template target created with `ref()` or `repeat()`.                  |

`anchor` and `into` are mutually exclusive.

Use `AutoWidth` when content-derived widths need bounds:

```python
from caxton import AutoWidth, table

table(
    source=rows,
    columns=columns,
    auto_width=AutoWidth(minimum=15, maximum=40),
)
```

`auto_width=True` uses the default range from 1 through 80. A column-level
policy overrides the table policy, while `.width(number)` keeps that column at
an explicit width. The two are mutually exclusive on one column: `.width()` and
`.width("auto")` each clear the other, and setting both at once on a directly
constructed `Column` is an error rather than a silent precedence.

## Row sources

Built-in ingestion supports, without importing your framework:

- mappings — read with `row[field]`;
- objects with attributes, dataclasses and `NamedTuple` — read with the exact attribute;
- any lazy iterable of those;
- your own `DataSource` / `RowAccessor` implementation.

Your own source only has to know how to iterate. Field access is already
solved — take it from the public accessors:

```python
from caxton import DefaultRowAccessor


class CursorSource:
    get_value = DefaultRowAccessor()

    def __init__(self, cursor):
        self._cursor = cursor

    def iter_rows(self):
        return iter(self._cursor)
```

`MappingRowAccessor` and `AttributeRowAccessor` pin the semantics explicitly
when rows are known to be one shape. The accepted input is spelled out by the
`RowSourceInput` alias, so a scalar or `None` is a type error rather than a
runtime one.

```python
import dataclasses


@dataclasses.dataclass(frozen=True)
class Sale:
    product: str
    revenue: int


table(
    source=[Sale("Coffee", 1250)],
    columns=(text(source="product"), integer(source="revenue")),
)
```

Caxton never calls `asdict`, `model_dump`, `vars` or `dir`, and never infers a
schema. DataFrame- and Arrow-like inputs are rejected with a focused error
rather than silently materialized; ORM session lifecycle, eager loading and
projection stay your responsibility.

Nested structures need an explicit path:

```python
from caxton import path, text

text(id="city", source=path("address", "city"))
```

A callable source receives the original row object:

```python
text(id="label", source=lambda row: f"{row['product']} ({row['region']})")
```

When a function needs one resolved value instead of the complete row, transform
an expression explicitly:

```python
from caxton import field, text


def status_title(status: object | None) -> str:
    if status is None:
        return ""
    return {"new": "Новое"}.get(str(status), str(status))


text(
    id="status",
    source=field("status").transform(status_title),
    title="Статус проверки",
)
```

`.transform()` receives the evaluated `field()`, `path()`, or `ref()` value for
each row. The input remains visible to validation and semantic testing. A
literal is only a constant value and has no implicit current-row context:

```python
from caxton import Column, Text, literal

Column(
    semantic_type=Text(),
    id="monitoring_method",
    source=literal("automatic"),
)
```

## Column factories

One factory per semantic type, all with the same keyword-only shape:
`factory(*, source=None, id=None, title=None, formula=None, style=None)`.

| Factory      | Semantic type | Typical Python value           |
|--------------|---------------|--------------------------------|
| `text`       | `Text`        | `str`                          |
| `integer`    | `Integer`     | `int`                          |
| `decimal`    | `Decimal`     | `Decimal`, `float`             |
| `money`      | `Money`       | `Decimal` (plus a `currency=`) |
| `percentage` | `Percentage`  | `Decimal`, `float`             |
| `boolean`    | `Boolean`     | `bool`                         |
| `date`       | `Date`        | `datetime.date`                |
| `time`       | `Time`        | `datetime.time`                |
| `datetime`   | `DateTime`    | `datetime.datetime`            |
| `duration`   | `Duration`    | `datetime.timedelta`           |
| `link`       | `Link`        | `str`                          |

A column defines **either** a Python `source` **or** an Excel `formula` — never
both and never neither. A string source also becomes the id when `id` is omitted;
callables, expressions, paths and formulas require an explicit semantic id.
Passing both source and formula raises `CaxtonValueError`.

## Generic columns

Use `Column(...)` when the semantic type is application-defined or has already
been resolved as data. It is also the uniform declaration style used in a
`ColumnSchema`:

```python
from typing import ClassVar

from caxton import Column, Money, SemanticType


class Rating(SemanticType):
    name: ClassVar[str] = "rating"


rating = Column(semantic_type=Rating(), source="rating", title="Rating")
amount = Column(
    semantic_type=Money(currency="RUB"),
    source="amount",
    title="Amount",
)
```

The constructor accepts only keyword arguments. Its state-oriented spelling is
`excel_formula=`, while type-specific factories keep the friendly `formula=`
name. Stored `Column.excel_formula` therefore does not collide with the fluent
`.formula(...)` method. Likewise, `width_hint=` is stored state, while
`.width(...)` is the fluent operation and `caxton.testing.ColumnSpec.width` is
the inspection field.

Exactly one of `source` and `excel_formula` is required. `width_hint` and
`auto_width` are also mutually exclusive: `width_hint` accepts a positive
number only and is authoritative — it fixes the column width and disables
automatic sizing for it, including the table-level policy — while
`auto_width=True` and `.width("auto")` select automatic sizing. The constructor normalizes an alignment string, an auto-width boolean,
style input, string source, callable source and formula into the same narrow
immutable state produced by the factories.

Column `source=` describes one cell value; table `source=` supplies the rows.
The semantic type must be a `SemanticType` instance, never a factory, class,
Python type or registry name.

## Reusable column schemas

`ColumnSchema` names, orders and reuses ordinary immutable columns. It does not
infer columns or validate row data:

```python
from caxton import Column, ColumnSchema, DateTime, Money, Text, table


class SalesColumns(ColumnSchema):
    product = Column(semantic_type=Text(), source="product", title="Product")
    amount = Column(
        semantic_type=Money(currency="USD"),
        source="amount",
        title="Amount",
    )
    created_at = Column(
        semantic_type=DateTime(),
        source="created_at",
        title="Created",
    )


sales = table(source=rows, columns=SalesColumns.columns)
```

The class-body declaration order is canonical. A subclass override keeps the
inherited position, and a new column is appended:

```python
class CompactSalesColumns(SalesColumns):
    amount = SalesColumns.amount.titled("Total")
    status = Column(semantic_type=Text(), source="status")
```

Pass `Schema.columns`, never the schema class itself. A declaration's public
attribute name must equal its column ID. Therefore formulas, paths, transforms,
aggregates, callables and literal expressions repeat that attribute name in an
explicit `id=`; the schema validates the already-built column and never changes
its identity. Factory-created columns are accepted too—uniform `Column(...)`
inside schemas is a documentation convention, not a collector restriction.

Changing the defining class-body order updates every `Schema.columns` consumer.
When only one consumer needs another order, compose an explicit tuple from the
named attributes. Compose independent schemas with
`(*IdentityColumns.columns, *AuditColumns.columns)` and remove columns through
explicit tuple filtering; mixins and multiple inheritance are rejected.
Rebinding a class attribute after creation does not rebuild the canonical
tuple, so use a subclass or tuple for variants.

Refer to a schema column by its attribute rather than by a repeated string, so
a rename fails at import instead of at validation:

```python
footer = Totals(items=(Total(SalesColumns.revenue.id),))
rule = when(col(SalesColumns.revenue.id) > 1000, style="highlight")
```

Physical order is semantic for grouped tables: grouped columns define hierarchy
in that order. It can also move an implicit totals label, which uses the first
non-aggregated column; set `Totals(label_column=...)` when that position must be
stable. A schema is reusable organization, not a promise that every future
document family supports every column feature.

## Fluent refinement

Every method returns a new column.

```python
from caxton import AutoWidth, money
from caxton.core.formatting import money_format

money(source="revenue", title="Revenue", currency="RUB")
.align("right")
.width(AutoWidth(minimum=14, maximum=30))
.format(money_format(currency="RUB"))
.styled("emphasis")
```

| Method                              | Effect                                                      |
|-------------------------------------|-------------------------------------------------------------|
| `.titled(str)`                      | Sets the header label. Defaults to the column id.           |
| `.align("left"\|"center"\|"right")` | Horizontal alignment hint.                                  |
| `.width(number)`                    | Sets an explicit fixed width.                               |
| `.width("auto" \| AutoWidth(...))` | Sizes from content, optionally within declared bounds.      |
| `.format(display_format)`           | Backend-independent display format.                         |
| `.styled(Style \| "name")`          | Inline style or a name from the document `StyleSheet`.      |
| `.formula(formula)`                 | Replaces the Python source with a live spreadsheet formula. |
| `.grouped(merge=…, order=…)`        | Declares one hierarchical grouping level.                   |

## Totals footers

```python
from caxton import Total, Totals, decimal, table

table(
    source=rows,
    columns=(decimal(source="price"), decimal(source="delta")),
    footer=Totals(
        label="Total",
        items=(Total("price"), Total("delta", "avg")),
    ),
)
```

`Total(column, function="sum")` names the column it is placed in and aggregates
that column. Supported functions are `sum`, `avg`, `min`, `max` and `count`.
A bare sequence works too — `footer=(Total("price"),)` — and is wrapped into a
`Totals` row with the default label.

`Totals.label_column` chooses where the label is written; without it, the first
column that carries no aggregate is used.

## Conditional formatting

```python
from caxton import col, when

table(
    source=rows,
    columns=(decimal(source="delta"),),
    rules=(when(col("delta") > 0, style="positive"),),
)
```

The condition is a *spreadsheet* formula, evaluated by the artifact against the
table's data range, so the highlight stays live when a user edits the file.

## Reusing a table shape

Because nodes are immutable, reuse means calling the factory again:

```python
def sales_report(rows, *, customer: str):
    return spreadsheet(
        sheet("Sales", table(source=rows, columns=columns, name="sales")),
        metadata={"customer": customer},
    )


write(sales_report(north_rows, customer="North"), "north.xlsx")
write(sales_report(south_rows, customer="South"), "south.xlsx")
```

Bind-time placeholders (`source_ref()` / `bind()`) are a deliberate deferral —
they are not part of the public API.
