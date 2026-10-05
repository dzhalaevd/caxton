# Templates

A template changes the workbook operation. Caxton opens an existing XLSX package, resolves the places it may edit,
writes semantic content into a private copy, and delivers a new file. The source template stays untouched.

Use this route when the workbook already carries layout that belongs outside Python: print settings, carefully sized
regions, existing formulas, or reporting sheets maintained by someone else.

## Choose who owns the workbook

Without a template, Caxton creates a workbook and owns its structure. With a template, the existing workbook owns the
worksheets and the native layout around each target.

| | New workbook | Existing template |
|---|---|---|
| Declaration | `spreadsheet(...)` | `spreadsheet(..., template=template(...))` |
| Workbook operation | Create | Use existing template |
| Default XLSX route | XlsxWriter | Dedicated OpenPyXL template renderer |
| Worksheets | Created from the document | Must already exist in the template |
| Placement | Flow or `anchor=` | Flow, `anchor=`, or a named template target |
| Presentation inside a target | Declared by Caxton | Owned by the template |

Caxton chooses the operation before selecting a renderer. A template request never falls back to creating a blank
workbook, even if the source cannot be read or a target is missing.

Declare the template on the document:

```python
from pathlib import Path

from caxton import sheet, spreadsheet, template

source = Path("assets/catalog-template.xlsx")

catalog = spreadsheet(
    sheet("Catalog"),
    template=template(source),
)
```

`template()` records immutable intent; it does not open the path. The `.xlsx` suffix selects the format when the source
is a path. For uploaded bytes or an extensionless path, declare it when detection is not possible:

```python
uploaded_bytes = source.read_bytes()
specification = template(uploaded_bytes, format="xlsx")
```

An explicit format that conflicts with the detected package raises `TemplateFormatError` instead of choosing one
silently.

## Write into a named range

Named ranges are the contract between the workbook and the semantic document. Suppose the template defines
`book_rows` as `'Catalog'!$A$5:$C$24`. Bind a table to it with `into=slot(...)`:

```python
from decimal import Decimal

from caxton import money, slot, table, text, write

books = (
    {
        "title": "Kindred",
        "author": "Octavia E. Butler",
        "price": Decimal("14.50"),
    },
    {
        "title": "Piranesi",
        "author": "Susanna Clarke",
        "price": Decimal("12.00"),
    },
)

book_table = table(
    source=books,
    columns=(
        text(source="title"),
        text(source="author"),
        money(source="price", currency="USD"),
    ),
    into=slot("book_rows"),
)

catalog = spreadsheet(
    sheet("Catalog", book_table),
    template=template("assets/catalog-template.xlsx"),
)

write(catalog, "output/catalog.xlsx")
```

The first column maps to the left edge of the range, the first row maps to its top edge, and Caxton writes data rows
without adding a header. Put visible headers in the template itself.

`slot()` belongs to the template namespace. It names an XLSX defined name; `ref()` names a semantic column and cannot be
used here. `into=` and `anchor=` are mutually exclusive because the named range already supplies the physical location.

The name must resolve to one rectangular range on the worksheet declared by `sheet()`. Matching is case-insensitive. A
worksheet-scoped name wins over a workbook-scoped name on that sheet. Missing, ambiguous, invalid, and cross-sheet
targets raise focused `TemplateRefError` subclasses.

A normal slot is bounded. The range must have at least as many columns as the table, and its height must hold every
output row. Caxton does not expand it.

### Let the template own presentation

A slot is a data-only target. Caxton writes values and formula intent into the existing cells but keeps their native
styles. Presentation options that would compete with the template are rejected before target rows are prepared:

- table and column styles, display formats, alignment, width, and automatic width;
- header styles, totals, conditional rules, autofilters, and frozen headers;
- a named native table created through `name=`;
- merged grouping cells.

Apply number formats, fills, borders, alignment, column widths, and any header design in the template. Semantic types
still control value validation: a `Money` column writes a numeric amount, while the target cell's existing number format
controls how the workbook displays it.

## Repeat a designed region

A fixed slot replaces values inside one range. Use `repeat(slot(...))` when the range is a complete visual block that
should appear once per semantic row:

```python
from caxton import repeat

book_cards = table(
    source=books,
    columns=(
        text(source="title"),
        text(source="author"),
        money(source="price", currency="USD"),
    ),
    into=repeat(slot("book_card")),
)
```

If `book_card` covers `A5:D7`, each input row receives a three-row copy. Caxton writes the semantic columns from the
top-left cell of each copy. The rest of the block comes from the template.

Each copy retains the block's styles and contained merged cells. Relative formulas inside the block are translated to
the new row; absolute axes stay fixed. If the repeat inserts rows, later template targets and defined names are shifted
to their new positions.

OpenPyXL cannot safely update every workbook structure after inserting rows. Caxton therefore rejects a repeat when
external formulas or structures such as charts, native tables, conditional formatting, data validation, or print areas
could be corrupted. Move those dependencies inside the repeated block, redesign the sheet so no insertion is needed, or
use a fixed slot.

An empty source leaves the original block in place and clears its values. The structure remains available for the next
generated workbook; no stale sample row is delivered.

## Run a focused OpenPyXL hook

Some workbook settings have no backend-neutral Caxton model. An OpenPyXL hook may adjust those settings after semantic
content has been rendered:

```python
from caxton.api import xlsx


def configure_printing(context: xlsx.OpenpyxlHookContext) -> None:
    worksheet = context.native_sheet
    worksheet.print_area = "A1:F30"
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True


catalog = spreadsheet(
    sheet("Catalog", book_table),
    template=template(
        "assets/catalog-template.xlsx",
        extensions=(xlsx.openpyxl_hook(configure_printing, sheet="Catalog"),),
    ),
)
```

The hook receives the native workbook and the selected native worksheet. If `sheet=` is omitted, the first worksheet
in the semantic document is used. Hooks run in declaration order after Caxton has written semantic content and before
the workbook is saved.

Hooks are explicitly XLSX- and OpenPyXL-specific. Keep them small: every cell or workbook property changed by a hook is
outside the backend-neutral preservation contract. The extension declares the capability it needs, so an incompatible
renderer fails during preflight rather than ignoring the hook.

An existing pivot cache has a narrower extension of its own:

```python
template(
    "assets/catalog-template.xlsx",
    extensions=(
        xlsx.pivot(
            "CatalogPivot",
            source=slot("book_rows"),
            refresh_on_open=True,
        ),
    ),
)
```

The pivot and its cache must already exist in the template. The data slot needs a header row immediately above it.
Caxton rebinds the cache source after the workbook is saved and marks it for refresh when requested; package paths and
relationships stay inside the XLSX implementation.

## Know the preservation boundary

Caxton edits a private workbook copy. Its guarantees are about which semantic regions it changes, not byte-for-byte
identity of the resulting XLSX package.

| Area | Guaranteed behavior |
|------|---------------------|
| Source template | Never modified. A path is read as input only. |
| Cells outside Caxton blocks and template targets | Left to the template unless a repeated insertion, hook, or explicit extension affects them. |
| Cells mapped to semantic columns | Old values, formulas, and hyperlinks are cleared; new semantic values or formulas are written; existing cell styles remain. |
| Unused rows in a fixed slot | Cleared so old sample data and hyperlinks do not leak into the output. |
| Extra target columns beyond the semantic table | Existing formulas and styles remain; other literal values and their hyperlinks are cleared. |
| Repeated regions | Contained styles, relative formulas, and merges are copied for each semantic row. External formulas and affected workbook structures outside the block cause a conservative rejection before insertion. |
| Output target | Receives the completed bytes only after rendering, hooks, and XLSX package post-processing all succeed. |

The output package is loaded and serialized by OpenPyXL, so Caxton does not promise that unrelated XML parts remain
byte-identical. If a native workbook feature is important to your application, keep a minimal fixture and verify the
completed artifact in a focused test.

Template and extension targets are resolved before target rows are materialized. A missing range, absent pivot, or
unsupported hook capability therefore fails before a one-shot row source is consumed. If a failure happens later,
atomic output delivery still leaves an existing target file untouched.

For the public template values and extension declarations, see
[`caxton.core.models`](../reference/models.md) and
[`caxton.api`](../reference/api.md).
