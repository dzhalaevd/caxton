# Rendering and delivery

A Caxton document describes a workbook; rendering turns that description into an artifact. The document does not own a
filename, a byte buffer or a spreadsheet engine. Those choices belong to the render call, so one immutable document can
serve different destinations. Reusing it across operations that read data also requires reiterable sources; immutability
does not reset a generator.

The examples below use one small catalog:

```python
from caxton import sheet, spreadsheet, table, text

catalog = spreadsheet(
    sheet(
        "Catalog",
        table(
            source=(
                {"title": "Kindred", "author": "Octavia E. Butler"},
                {"title": "Piranesi", "author": "Susanna Clarke"},
            ),
            columns=(
                text(source="title", title="Title"),
                text(source="author", title="Author"),
            ),
            name="books",
        ),
    ),
)
```

## Choose where the artifact goes

Use `render()` when the caller needs XLSX bytes in memory:

```python
from caxton import render

result = render(catalog)
assert result.data is not None
xlsx_bytes = result.data
```

This is a natural fit for an HTTP response, object storage client or test that immediately inspects the finished
workbook. The complete artifact remains in `result.data`, so a large export also remains in process memory.

Use `write()` with a path when the file is the result you want to keep:

```python
from pathlib import Path

from caxton import write

result = write(catalog, Path("catalog.xlsx"))
assert result.data is None
assert result.target == "catalog.xlsx"
```

The path suffix supplies the format hint. A path without a suffix falls back to XLSX, and an explicit `format=` takes
precedence over the suffix. Keeping the two consistent makes the artifact unambiguous to other programs.

A writable binary object is useful when another library owns the destination:

```python
from io import BytesIO

from caxton import write

buffer = BytesIO()
result = write(catalog, buffer, format="xlsx")

assert result.data == buffer.getvalue()
```

Buffers have no filename from which to infer a format. XLSX is the default, but passing `format="xlsx"` makes the
boundary explicit. Buffer writes retain the completed bytes in `result.data`; path writes do not.

| Destination                         | Operation  | Artifact bytes in `result.data` | Typical use                        |
|-------------------------------------|------------|---------------------------------|------------------------------------|
| Caxton-owned memory                 | `render()` | Yes                             | HTTP responses, tests, object APIs |
| Filesystem path                     | `write()`  | No                              | Reports and scheduled exports      |
| Writable binary object or `BytesIO` | `write()`  | Yes                             | Framework and library integrations |

All three return a `RenderResult`. Its `format`, `mime_type`, `renderer`, `bytes_written`, `execution_mode` and
`execution_plan` describe what actually happened. The older `content` property is a deprecated alias for `data`.

## Let the workbook operation guide backend selection

For a new XLSX workbook, Caxton uses XlsxWriter by default. Select the create-new OpenPyXL adapter only when an
integration requires it:

```python
result = render(catalog, backend="openpyxl")
assert result.renderer == "openpyxl"
```

Templates follow a different route. Adding a template to the document changes the workbook operation from “create a
workbook” to “fill this workbook,” and Caxton selects the dedicated `openpyxl-template` renderer. It does not fall back
to a create-new backend if the template route is incompatible. See [Templates](templates.md) for that workflow.

Renderer selection happens before compilation and before row data is read. Caxton checks the requested format, document
kind, IR version, workbook operation, required features and execution mode against the renderer descriptor. An
unsupported backend or capability therefore fails before a destination is changed.

Pass `backend=` when choosing between bundled implementations of the same format. Pass `renderer=` when supplying a
renderer object of your own; the explicit renderer still has to satisfy the same compatibility checks.

## Choose an execution mode

Execution mode controls how the selected renderer builds the artifact. It does not change the document model or the
shape of the resulting workbook.

| Mode       | Behavior                                                                                 |
|------------|------------------------------------------------------------------------------------------|
| `AUTO`     | Let the renderer choose a compatible plan. This is the default.                          |
| `STANDARD` | Use ordinary workbook construction, including features that need non-append-only access. |
| `STREAM`   | Request a constant-memory or write-only plan from a renderer that supports one.          |

The XlsxWriter renderer can use either standard or constant-memory execution. In `AUTO`, it chooses constant-memory for
append-only worksheets and standard execution when the document needs a named XLSX table or shape-dependent buffering.
OpenPyXL create-new and template rendering currently support standard execution only.

Request streaming when bounded workbook memory is a requirement rather than a preference:

```python
from caxton import ExecutionMode, sheet, spreadsheet, table, text, write

rows = ({"title": title} for title in ("Kindred", "Piranesi"))
reading_list = spreadsheet(
    sheet(
        "Reading list",
        table(
            source=rows,
            columns=(text(source="title", title="Title"),),
        ),
    ),
)

result = write(
    reading_list,
    "reading-list.xlsx",
    mode=ExecutionMode.STREAM,
)
assert result.execution_plan == "constant_memory"
```

The table is deliberately unnamed: creating a native XLSX table needs standard execution. Grouping, matrices and other
features that prepare the complete output shape can also rule out streaming. Caxton does not commit the output target
when `STREAM` is rejected. A named table is rejected before its ordinary row stream is entered, but grouped tables and
matrices may consume their single preparation pass before XlsxWriter reports `shape_dependent_buffering`. Use a fresh
source if you plan to retry those documents with `STANDARD`.

Streaming does not make a one-shot source reusable. A generator is still consumed once by the successful render; create
a fresh document or materialize the rows before rendering it again.

## Know when the destination changes

Path delivery is transactional. Caxton renders to a sibling staging file, then atomically replaces the destination only
after the renderer succeeds. If validation, row evaluation or the backend fails, an existing file remains unchanged and
an absent target remains absent.

Binary targets also receive data only after rendering succeeds. A seekable buffer is rewound to offset zero, overwritten
and truncated, so old trailing bytes cannot survive a shorter artifact. Forward-only writers receive the finished
artifact in chunks, and Caxton retries valid short writes until every byte is delivered.

The distinction matters during delivery failure. A filesystem replacement is atomic. A general buffer or stream cannot
promise rollback once its own `write()` method has accepted bytes; Caxton reports such failures as `OutputError` and
preserves the original exception as the cause.

## Add a custom renderer

A custom renderer implements the public `Renderer` protocol and declares its contract in a `RendererDescriptor`. The
pipeline supplies a compiled, read-only `SpreadsheetIR`, an `OutputSink` and a resolved `RenderContext`.

This small renderer writes worksheet names as plain text. Its descriptor advertises an empty feature set, so the example
document contains empty worksheets; a production renderer must declare every semantic feature it can handle.

```python
from caxton import render, sheet, spreadsheet
from caxton.core.ir import SPREADSHEET_IR_VERSION, SpreadsheetIR
from caxton.core.models import DocumentKind
from caxton.core.protocols import OutputSink
from caxton.core.rendering import (
    RenderContext,
    RendererCapabilities,
    RendererDescriptor,
    RenderResult,
)


class WorksheetListRenderer:
    descriptor = RendererDescriptor(
        name="worksheet-list",
        version="1.0",
        formats=frozenset(("txt",)),
        mime_types=frozenset(("text/plain",)),
        extensions=frozenset((".txt",)),
        capabilities=RendererCapabilities(
            ir_versions={
                DocumentKind.SPREADSHEET: frozenset((SPREADSHEET_IR_VERSION,)),
            },
        ),
    )

    def render(
        self,
        document: SpreadsheetIR,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        payload = (
            "\n".join(sheet.name for sheet in document.worksheets) + "\n"
        ).encode()
        written = sink.write(payload)
        return RenderResult(
            format=context.format,
            mime_type="text/plain",
            renderer=self.descriptor.name,
            bytes_written=written,
        )


document = spreadsheet(sheet("Catalog"), sheet("Archive"))
result = render(document, format="txt", renderer=WorksheetListRenderer())
assert result.data == b"Catalog\nArchive\n"
```

Pass a renderer directly to `render()` or `write()`; there is no global registry or entry-point discovery. Keep engine
objects inside the adapter and consume each `SpreadsheetTableIR.rows` stream once. If an algorithm truly needs repeated
access, call `table.rows.materialized()` deliberately and account for the memory cost.

The public contracts are listed in [`caxton.core.protocols`](../reference/protocols.md), and the versioned spreadsheet
IR is documented in [`caxton.core.ir`](../reference/ir.md).
