# Worksheets and blocks

A worksheet turns an ordered set of semantic blocks into a two-dimensional layout. Declare the blocks in reading order
and let the compiler place them. Most worksheets should use this flow; reach for `anchor=` when a coordinate is part of
the requirement, such as a fixed dashboard or an external template.

## Build in reading order

This worksheet contains a heading, a deliberate blank row and a table:

```python
from caxton import Freeze, integer, sheet, spacer, spreadsheet, table, text, title

books = (
    {"title": "Kindred", "author": "Octavia E. Butler", "pages": 288},
    {"title": "Piranesi", "author": "Susanna Clarke", "pages": 272},
)

book_columns = (
    text(source="title", title="Title"),
    text(source="author", title="Author"),
    integer(source="pages", title="Pages"),
)

books_table = table(
    source=books,
    columns=book_columns,
    name="books",
    freeze_header=True,
)

library = spreadsheet(
    sheet(
        "Library",
        title("Reading list", span=3),
        spacer(),
        books_table,
        freeze=Freeze(rows=0, columns=1),
    ),
)
```

No cell addresses are stored in `library`. During layout, the title occupies
`A1:C1`, the spacer advances past row 2 and the table begins at `A3`. A later block would begin below the table.

You can inspect those decisions without opening the finished workbook:

```python
from caxton.testing import inspect_layout

worksheet = inspect_layout(library).worksheet("Library")

assert worksheet.block("block[0]").cell_range == "A1:C1"
assert worksheet.table("books").anchor == "A3"
assert worksheet.freeze == Freeze(rows=3, columns=1)
```

The resolved freeze combines the first worksheet column with the table header at row 3. This is more reliable than
repeating the table's eventual row in the worksheet declaration.

## How blocks occupy the grid

Every block has an anchor and a footprint. The compiler uses both to place the next block and to detect overlaps.

| Block shape             | Footprint                                             |
|-------------------------|-------------------------------------------------------|
| Title                   | One row across its declared `span`.                   |
| Spacer                  | Its declared rows and columns.                        |
| Image or chart          | Pixel dimensions converted to whole cells.            |
| Ordinary table          | Header, known data rows and an optional footer.       |
| Grouped table or matrix | The shape produced by its preparation pass.           |
| Stack                   | The combined footprint of its nested blocks and gaps. |

Tables and matrices carry data semantics. Titles, images and charts add presentation. Spacers and stacks only arrange
other content. All seven remain ordinary immutable blocks inside the worksheet.

## Keep related blocks together

A `stack` gives a small group its own flow direction. For example, two charts can share one row without calculating the
second chart's cell address:

```python
from caxton import chart, stack, table_ref

charts = stack(
    chart(
        table_ref("books"),
        x="title",
        y="pages",
        kind="column",
        title="Pages by book",
        width=320,
        height=200,
    ),
    chart(
        table_ref("books"),
        x="title",
        y="pages",
        kind="bar",
        title="Pages by book",
        width=320,
        height=200,
    ),
    direction="horizontal",
    gap=1,
)
```

Pass `charts` after `books_table` in the worksheet. A horizontal stack measures
`gap` in columns; a vertical stack measures it in rows. Stacks may be nested, and their children remain visible in
layout inspection.

A chart does not own another copy of the data. It binds to a named table and uses semantic column ids for its categories
and values. The compiler needs the table's row count to resolve those ranges. An image is independent: it accepts a path
or raw bytes and uses its declared pixel size for layout.

## Use anchors for fixed positions

Every block accepts an optional A1 anchor:

```python
fixed_table = table(
    source=books,
    columns=book_columns,
    name="books",
    anchor="A3",
)

fixed_chart = chart(
    table_ref("books"),
    x="title",
    y="pages",
    anchor="F3",
)
```

An anchored block keeps that position and still advances the worksheet's flow cursor. The next implicit block therefore
starts after both the existing flow and the anchored block's occupied range. Anchors can still conflict with each other;
`validate()` reports a `block_overlap` issue when two measurable blocks claim the same cells.

Prefer flow while the reading order and the visual order agree. Fixed anchors are useful when the grid itself is part of
the contract, but a sheet made only of coordinates is harder to extend safely.

## Unknown heights need a decision

A tuple or list exposes its row count without being read, so an ordinary table can participate in flow immediately. A
generator does not. Caxton will not consume it during structural validation just to discover where the next block
belongs.

This version is unambiguous because both blocks have explicit anchors:

```python
streamed_books = table(
    source=(book for book in books),
    columns=book_columns,
    anchor="A1",
)

imports = sheet(
    "Imports",
    streamed_books,
    title("Notes", anchor="F1"),
)
```

Remove the title's anchor and layout raises `UnsupportedFeatureError`: placing it below the table would require guessing
the table's height. An explicit block does not restore an unknown flow cursor, so every later block that relies on flow
must also receive an anchor.

Grouped tables and matrices have a related constraint. Their output dimensions depend on the data, so Caxton measures
them during their single preparation pass and checks placement again. A structural `validate()` can therefore pass
before a later render discovers a data-dependent overlap.

Resolved blocks are also checked against the XLSX limits of 1,048,576 rows and 16,384 columns. For a dense dashboard,
inspect the layout before rendering the artifact:

```python
dashboard = spreadsheet(
    sheet(
        "Library",
        title("Reading list", span=3),
        spacer(),
        books_table,
        spacer(rows=2),
        charts,
    ),
)

layout = inspect_layout(dashboard)
assert layout.worksheet("Library").block("block[4]").anchor == "A8"
```
