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
| `auto_width`    | Sizes every column that declares no explicit width.                  |
| `into`          | Template target created with `ref()` or `repeat()`.                  |

`anchor` and `into` are mutually exclusive.

## Row sources

Built-in ingestion supports, without importing your framework:

- mappings — read with `row[field]`;
- objects with attributes, dataclasses and `NamedTuple` — read with the exact attribute;
- any lazy iterable of those;
- your own `DataSource` / `RowAccessor` implementation.

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

## Fluent refinement

Every method returns a new column.

```python
from caxton import money
from caxton.core.formatting import money_format

money(source="revenue", title="Revenue", currency="RUB")
.align("right")
.width(14)
.format(money_format(currency="RUB"))
.styled("emphasis")
```

| Method                              | Effect                                                      |
|-------------------------------------|-------------------------------------------------------------|
| `.titled(str)`                      | Sets the header label. Defaults to the column id.           |
| `.align("left"\|"center"\|"right")` | Horizontal alignment hint.                                  |
| `.width(number)`                    | Explicit width; `.width("auto")` sizes from content.        |
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
