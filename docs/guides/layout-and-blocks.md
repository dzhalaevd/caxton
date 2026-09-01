# Worksheet layout

A worksheet holds a closed set of blocks. Blocks carry intent; the compiler owns
placement.

| Block             | Factory    | Measured as                                   |
|-------------------|------------|-----------------------------------------------|
| Table             | `table()`  | Header row + row count + optional footer row. |
| Matrix            | `matrix()` | Its prepared output shape.                    |
| Title             | `title()`  | One row, spanning `span` columns.             |
| Spacer            | `spacer()` | Declared rows × columns.                      |
| Image             | `image()`  | Pixel size converted to whole cells.          |
| Chart             | `chart()`  | Pixel size converted to whole cells.          |
| Stack (container) | `stack()`  | The blocks it contains, plus gaps.            |

## Flow placement

Blocks are placed in declaration order:

```python
from caxton import sheet, spacer, spreadsheet, table, title

spreadsheet(
    sheet(
        "Dashboard",
        title("Daily revenue", span=2),
        spacer(rows=1),
        table(
            source=rows,
            columns=(text(source="day"), decimal(source="revenue")),
            name="sales",
        ),
    ),
)
```

A dedicated layout pass walks the blocks, measures each one and assigns a
physical anchor and occupied range before any IR node is built. You never do row
arithmetic yourself.

## Stacks

`stack()` groups blocks and flows them in one direction:

```python
from caxton import chart, image, stack, table_ref

stack(
    chart(table_ref("sales"), x="day", y="revenue", kind="column", title="Revenue by day"),
    image(logo_bytes, width=128, height=64, name="logo"),
    direction="vertical",  # or "horizontal"
    gap=1,
)
```

## Explicit anchors

`anchor="A3"` is the escape hatch. An anchored block keeps its declared position
*and* still advances the flow cursor, so a following implicit block never lands
inside it.

```python
table(source=rows, columns=columns, name="sales", anchor="A3")
```

## Overlaps and unknown heights

Overlaps between statically measurable blocks are reported as `block_overlap`
validation issues before any source is consumed. Blocks whose shape depends on
the data get a second placement check after preparation.

When a table's height is unknown, the flow cursor becomes invalid rather than
guessing: the next *implicit* block raises `UnsupportedFeatureError`. The
document still works if every following block declares an explicit anchor.

Prepared placements are checked against XLSX sheet bounds (1,048,576 rows by
16,384 columns) before rendering.

## Freeze panes

Worksheet-level freezing lives on the sheet; table-level header freezing lives on
the table.

```python
from caxton import Freeze, sheet

sheet("Sales", sales_table, freeze=Freeze(rows=1, columns=1))
```

```python
table(source=rows, columns=columns, freeze_header=True)
```

`Freeze` must include at least one row or column.

## Charts

Charts bind to an existing **named** table plus semantic column ids:

```python
from caxton import chart, table_ref

chart(
    table_ref("sales"),
    x="day",
    y=["revenue", "cost"],
    kind="column",
    title="Revenue by day",
    width=480,
    height=288,
)
```

The compiler resolves the reference into physical ranges of the placed table, so
a chart — like a range reference — requires a known row count. An independent
inline `data=` source for charts is a deliberate deferral.

## Images

```python
from caxton import image

image("assets/logo.png", width=128, height=64, name="logo", description="Company logo")
image(logo_bytes, width=128, height=64)
```

Images accept a path or raw bytes and are sized in pixels, which the layout pass
converts into whole cells.
