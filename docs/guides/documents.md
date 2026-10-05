# Documents

Most Caxton code produces a `SpreadsheetDocument`. Treat it as a description of one workbook: it says which worksheets
belong together and which settings apply to all of them. It is not an open workbook and does not contain resolved cell
coordinates or backend objects.

Caxton currently ships one public document family, `SpreadsheetDocument`, which renders to XLSX.

## What belongs to a document

```text
SpreadsheetDocument
├── worksheets
│   └── Worksheet
│       └── blocks: tables, titles, images, charts, matrices and stacks
├── metadata
├── styles
├── theme
└── template
```

A worksheet owns an ordered sequence of blocks. The document owns the settings shared by the workbook. Row data belongs
to individual tables and matrices; the output path belongs to `write()`, not to the document.

Here is a complete document with one worksheet and one table:

```python
from caxton import integer, sheet, spreadsheet, table, text

books = (
    {
        "title": "The Left Hand of Darkness",
        "author": "Ursula K. Le Guin",
        "year": 1969,
    },
    {"title": "Kindred", "author": "Octavia E. Butler", "year": 1979},
)

library = spreadsheet(
    sheet(
        "Books",
        table(
            source=books,
            columns=(
                text(source="title", title="Title"),
                text(source="author", title="Author"),
                integer(source="year", title="Year"),
            ),
            name="books",
        ),
    ),
    metadata={"purpose": "reading-list"},
)
```

The call builds an immutable semantic value. It does not open a file or read a row. Block order is significant because
it supplies the worksheet's default layout order; physical placement is resolved later by the compiler.

## Choosing the boundary

The useful test is whether the value can be rendered on its own. One document describes one workbook; a worksheet
describes a named tab; blocks are the units that the layout engine places on that tab.

That boundary becomes useful when a report grows. A builder can own a coherent part of the workbook without knowing
where the result will be written:

```python
from collections.abc import Iterable, Mapping

from caxton import sheet, spreadsheet, table, text
from caxton.core.models import SpreadsheetDocument


def reading_list(
    rows: Iterable[Mapping[str, object]],
    *,
    table_name: str = "books",
) -> SpreadsheetDocument:
    return spreadsheet(
        sheet(
            "Books",
            table(
                source=rows,
                columns=(
                    text(source="title", title="Title"),
                    text(source="author", title="Author"),
                ),
                name=table_name,
            ),
        ),
    )
```

Calling the builder creates a fresh document. Since public nodes are immutable, the caller can pass that value to
validation, testing or rendering without a later step changing its structure.

One trap is easy to miss: construction remains lazy. If `rows` is a generator, the generator belongs to the resulting
document and can be consumed only once. Pass a fresh source to each independently rendered document, or materialize the
rows deliberately when reuse matters.

## Document settings

A worksheet should not decide which template or visual defaults govern the workbook. Those settings live on the
document:

- `metadata` stores application-defined information alongside the semantic document;
- `styles` contains named styles referenced by blocks and columns;
- `theme` supplies workbook-wide presentation defaults;
- `template` selects the existing XLSX workbook that the document fills.

Values, styles and themes describe presentation without exposing OpenPyXL or XlsxWriter objects. Templates are
different: they change the workbook operation from creating a file to filling an existing one. See
[Values and presentation](presentation.md) and [Templates](templates.md) for those workflows.

## Composing independent documents

Sometimes the section is the reusable unit. Build each section as a complete document, then combine them at the workbook
boundary:

```python
from caxton import compose

fiction = ({"title": "Kindred", "author": "Octavia E. Butler"},)
essays = ({"title": "A Room of One's Own", "author": "Virginia Woolf"},)

collection = compose(
    {
        "Fiction": reading_list(fiction, table_name="fiction_books"),
        "Essays": reading_list(essays, table_name="essay_books"),
    },
    metadata={"purpose": "personal-library"},
)
```

The result is another ordinary `SpreadsheetDocument`. Section names qualify worksheet names, so the example produces
`Fiction - Books` and `Essays - Books`. Table and style names remain workbook-wide, which is why the two sections use
distinct table names.

Composition preserves section order and does not read row sources. A qualified reference such as `sheet_ref("Books")`
inside the Fiction child is rebased to `Fiction - Books`. It may refer only to a worksheet in that child; a reference to
another section is rejected during composition. Unqualified column and table references keep their original semantic
identity.

Workbook settings follow explicit conflict rules:

| Setting | Compatible child values | Outer value |
|---------|-------------------------|-------------|
| Metadata | Disjoint keys and equal values are merged. | `metadata=` supplies the complete result metadata. |
| Named styles | Unrelated names and equal definitions are combined. | A style with the conflicting name wins. |
| Theme | One non-default theme, or equal themes, is inherited. | `theme=` selects the result theme. |
| Template | Child templates are rejected. | `template=` belongs to the composed workbook. |

Without the corresponding outer value, a metadata, style or theme conflict raises `InvalidOperationError` instead of
choosing one section silently.

## From document to artifact

Because `library` captures a tuple, its source is reiterable and the same immutable value can pass through the
production path:

```text
SpreadsheetDocument ── validate() ──▶ structural checks
                    ├─ render() ────▶ RenderResult with XLSX bytes
                    └─ write() ─────▶ RenderResult and a delivered XLSX file
```

```python
from caxton import render, validate, write

validate(library)

result = render(library)
assert result.data is not None

write(library, "library.xlsx")
```

`validate()` checks document structure without consuming rows. `render()` keeps the artifact in memory. `write()` sends
it to a path or binary target and owns delivery, including atomic replacement for path writes.

Rendering is the point where lazy data may be consumed. Requirement analysis and renderer resolution check compatibility
before compilation; the compiler then resolves layout, coordinates and formula references against the selected
capability contract. See
[Rendering and delivery](render.md) for renderer selection, execution modes and output targets.

Once the document boundary is clear, continue with
[Tables and data](tables.md) for row sources and schemas, or
[Worksheets and blocks](worksheets-and-blocks.md) for block placement.
