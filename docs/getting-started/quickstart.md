# Quickstart

This page builds a small sales report, checks it, and writes it to disk. Every
snippet uses only the public `caxton` facade.

## 1. Describe the data

Caxton reads rows through a lazy data source. Mappings, dataclasses,
`NamedTuple` values and plain attribute objects all work without registration.

```python
from decimal import Decimal

SALES = (
    {"product": "Coffee", "revenue": Decimal(1250), "cost": Decimal(700)},
    {"product": "Tea", "revenue": Decimal(920), "cost": Decimal(510)},
)
```

## 2. Declare columns

A column has a semantic `id`, a semantic type and a value source. A string
`source` names an exact top-level row field and also supplies the `id` when it
is omitted. Expressions and formulas require an explicit `id`.

```python
from caxton import money, ref, text

columns = (
    text(source="product", title="Product").width(18),
    money(source="revenue", title="Revenue", currency="RUB"),
    money(source="cost", title="Cost", currency="RUB"),
    money(
        id="profit",
        source=ref("revenue") - ref("cost"),
        title="Profit",
        currency="RUB",
    ),
)
```

`ref()` reads the evaluated value of another semantic column, so `profit` is
computed by Caxton before rendering. If you want the *artifact* to keep a live
formula instead, use [`col()`](../guides/formulas-and-references.md).

## 3. Compose the document

```python
from caxton import sheet, spreadsheet, table

report = spreadsheet(
    sheet(
        "Sales",
        table(
            source=SALES,
            columns=columns,
            name="sales",
            anchor="A3",
            freeze_header=True,
        ),
    ),
    metadata={"example": "quickstart"},
)
```

`table()` coerces the row source once and stores it — it does **not** read any
row yet.

## 4. Validate before rendering

```python
from caxton import validate

validate(report)
```

`validate()` checks structure — duplicate column ids, unknown references,
overlapping blocks — without consuming data.

!!! note

    A clean `validate()` cannot guarantee a clean render for blocks whose shape
    depends on the data (grouped tables and matrices). Those are re-checked
    after their single preparation pass.

## 5. Inspect what the compiler decided

```python
from caxton.testing import Rows, inspect_layout, inspect_spec

spec = inspect_spec(report)
assert spec.worksheet("Sales").table("sales").column_ids == (
    "product",
    "revenue",
    "cost",
    "profit",
)

layout = inspect_layout(report, rows=Rows.sample(1))
sales = layout.worksheet("Sales").table("sales")
assert sales.anchor == "A3"
assert sales.row(0)["profit"] == Decimal(550)
```

`inspect_spec()` never reads rows. `inspect_layout()` reads them only when you
ask for a scope with `Rows.sample(n)` or `Rows.all()`.

## 6. Render or write

```python
from io import BytesIO

from caxton import render, write

# In memory: the artifact bytes come back on the result.
result = render(report)
assert result.renderer == "xlsxwriter"
assert result.data is not None

# To a path: written atomically through a staging file.
write(report, "sales.xlsx")

# To a binary buffer.
buffer = BytesIO()
written = write(report, buffer, format="xlsx")
assert written.data == buffer.getvalue()
```

## 7. Check the finished file

```python
from caxton.testing import inspect_artifact

artifact = inspect_artifact(result)
worksheet = artifact.worksheet("Sales")
assert worksheet.table("sales").column_titles == ("Product", "Revenue", "Cost", "Profit")
assert worksheet.cell("D4").value == 550
```

## Next steps

- [Core concepts](concepts.md) — why the model looks like this.
- [Tables and columns](../guides/tables-and-columns.md) — sources, ids, titles.
- [Rendering and output](../guides/rendering-and-output.md) — backends, modes, sinks.
