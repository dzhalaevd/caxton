# Quickstart

This page installs Caxton and builds two spreadsheet documents with the public
`caxton` facade. The second example also uses the public `caxton.testing` API to
inspect the result.

## Installation

Caxton requires **Python 3.10 or newer**. XlsxWriter and OpenPyXL are installed
with the package, so no additional dependency is needed to create XLSX files.

=== "uv"

    ```bash
    uv add caxton
    ```

=== "pip"

    ```bash
    pip install caxton
    ```

=== "poetry"

    ```bash
    poetry add caxton
    ```

## Using Caxton

A Caxton document is an immutable description of its content. Build that
description with public factories, then pass it to `write()` to create a file or
to `render()` to get the artifact bytes in memory.

### Create a simple table

This complete example turns a sequence of mappings into `people.xlsx`:

```python
from caxton import sheet, spreadsheet, table, text, write

people = (
    {"name": "Ada Lovelace", "role": "Mathematician"},
    {"name": "Grace Hopper", "role": "Computer scientist"},
)

report = spreadsheet(
    sheet(
        "People",
        table(
            source=people,
            columns=(
                text(source="name", title="Name"),
                text(source="role", title="Role"),
            ),
        ),
    ),
)

write(report, "people.xlsx")
```

Column sources name fields in each input row. Their titles are the labels shown
in the spreadsheet. Caxton accepts mappings, dataclasses, `NamedTuple` values,
and plain objects without registration.

### Calculated values

The next report calculates profit from two semantic columns, validates the
document, checks its compiled layout, and renders it in memory.

```python
from decimal import Decimal

from caxton import money, ref, render, sheet, spreadsheet, table, text, validate
from caxton.testing import Rows, inspect_artifact, inspect_layout

sales = (
    {"product": "Coffee", "revenue": Decimal(1250), "cost": Decimal(700)},
    {"product": "Tea", "revenue": Decimal(920), "cost": Decimal(510)},
)

columns = (
    text(source="product", title="Product"),
    money(source="revenue", title="Revenue", currency="RUB"),
    money(source="cost", title="Cost", currency="RUB"),
    money(
        id="profit",
        source=ref("revenue") - ref("cost"),
        title="Profit",
        currency="RUB",
    ),
)

report = spreadsheet(
    sheet(
        "Sales",
        table(
            source=sales,
            columns=columns,
            name="sales",
            anchor="A3",
            freeze_header=True,
        ),
    ),
    metadata={"example": "quickstart"},
)

validate(report)

layout = inspect_layout(report, rows=Rows.sample(1))
sales_table = layout.worksheet("Sales").table("sales")
assert sales_table.anchor == "A3"
assert sales_table.row(0)["profit"] == Decimal(550)

result = render(report)
assert result.data is not None

artifact = inspect_artifact(result)
assert artifact.worksheet("Sales").cell("D4").value == 550
```

`ref()` reads the evaluated value of another semantic column, so `profit` is
computed by Caxton before rendering. Use
[`col()`](../guides/formulas.md) when the finished spreadsheet
should contain a live formula instead.

`validate()` checks structure without consuming rows. `inspect_layout()` reads
only the requested scope, while `inspect_artifact()` checks the completed file.

## Next steps

- [Overview](overview.md) — why the model looks like this.
- [Tables and data](../guides/tables.md) — row sources, schemas, ids and titles.
- [Rendering and delivery](../guides/render.md) — backends, execution modes and output targets.
- [Examples](https://github.com/dzhalaevd/caxton/tree/main/example) — complete runnable projects.
