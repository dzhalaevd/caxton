# Formulas and references

Caxton has two expression hierarchies that never mix. Choosing between them is
choosing *who computes the value*.

| You want                                   | Use                                   | Result in the file |
|--------------------------------------------|---------------------------------------|--------------------|
| Caxton to compute the value before writing | `field()`, `path()`, `ref()`          | A literal          |
| The spreadsheet to keep computing it       | `col()`, `table_ref()`, `sheet_ref()` | A live formula     |

Mixing them raises a focused error: passing a Python row expression where a
formula is expected reports *"Python row expressions cannot be used as Excel
formulas; use col()"*.

## Python row expressions

`field(name)` reads one exact top-level field of the raw row. `path(*segments)`
traverses a nested structure. `ref(column_id)` reads the already-evaluated value
of another semantic column of the same table.

```python
from caxton import field, money, path, ref, text

text(id="city", source=path("address", "city"))
money(id="profit", source=ref("revenue") - ref("cost"))
money(id="net", source=field("net_amount"))
```

Expressions support the usual binary operators — `+ - * /`, comparisons, `&`
and `|` — and compose into trees:

```python
ref("revenue") * 0.2 > ref("cost")
```

!!! warning "No dependency on formula columns"

    A Python expression cannot reference a formula-backed column. That column's
    value only exists once the artifact is opened, so Caxton has nothing to read.

## Spreadsheet formulas

`col(column_id)` refers to the same row of another column in the same table.
The compiler resolves the semantic id into a physical cell, and the renderer
writes A1 or structured notation.

```python
from caxton import col, decimal

decimal(source="delta").formula(col("price") - col("base_price"))
```

Formulas can also be passed at construction time:

```python
decimal(id="delta", formula=col("price") - col("base_price"))
```

### Absolute and relative axes

```python
col("base_price").absolute()  # $B$2
col("base_price").absolute(row=False)  # $B2
col("base_price").relative(column=False)  # B$2
```

`absolute(column=..., row=...)` sets each axis to exactly the flags you pass, so
`absolute(column=False)` really makes the column relative instead of silently
doing nothing. The free function `absolute(reference, ...)` does the same for a
cell or a range.

### Named tables and cross-sheet references

```python
from caxton import decimal, sheet_ref, table_ref

# The whole "price" column of the table named "sales".
decimal(id="all_prices", formula=table_ref("sales").column("price"))

# One cell of that column, on another worksheet.
decimal(
    id="first_price",
    formula=sheet_ref("Sales").table("sales").column("price").cell(0).absolute(),
)
```

`table_ref(name)` requires the table to declare `name=`. `.column(id)` produces
a range reference; `.cell(row_index)` narrows it to one zero-based data row.

!!! note "Ranges need a known row count"

    Resolving a range means knowing where the table ends. The compiler will not
    make a hidden extra pass over a one-shot or unknown-length source to find
    out; such a document is rejected before writing instead.

## Conditional rules

`when()` builds a conditional-formatting rule from a formula:

```python
from caxton import col, when

when(col("delta") > 0, style="positive")
```

## Aggregates in totals vs. aggregates in values

- A [`Total`](tables-and-columns.md#totals-footers) in a table footer becomes a
  spreadsheet aggregate over the rendered range.
- `AggregateExpr` (via `.agg(...)`) is computed by Caxton and written as a
  literal. See [Grouping and aggregation](grouping-and-aggregation.md).
