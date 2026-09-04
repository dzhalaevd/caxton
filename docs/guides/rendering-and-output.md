# Rendering and output

## Three operations

```python
from caxton import render, validate, write

validate(document)  # structure only, reads no rows
result = render(document)  # bytes in memory
result = write(document, "out.xlsx")  # bytes to a path or buffer
```

Both `render()` and `write()` return a `RenderResult`:

| Field              | Meaning                                                     |
|--------------------|-------------------------------------------------------------|
| `format`           | Resolved format name, e.g. `"xlsx"`.                        |
| `mime_type`        | MIME type of the artifact.                                  |
| `renderer`         | Name of the renderer that produced it, e.g. `"xlsxwriter"`. |
| `bytes_written`    | Size of the artifact.                                       |
| `data` / `content` | Artifact bytes when they were retained.                     |
| `target`           | Destination description for path writes.                    |
| `execution_mode`   | The mode the renderer actually used.                        |
| `execution_plan`   | Backend-local plan name, when the renderer reports one.     |

## Targets

```python
from io import BytesIO
from pathlib import Path

write(document, Path("reports/sales.xlsx"))

buffer = BytesIO()
result = write(document, buffer, format="xlsx")
assert result.data == buffer.getvalue()
```

For a path target, the built-in sink writes to a sibling staging file and
atomically replaces the destination only after the backend finishes — a failed
render never leaves a half-written file. For a binary target, the adapter retries
short writes until the whole artifact is delivered or a stable render error is
raised.

Note that a path target has no extension-independent magic: give the file the
extension you want, or pass `format=` explicitly.

## Choosing a backend

Resolution considers, in order:

1. an explicitly supplied `renderer=`;
2. an explicit `backend=`;
3. an explicit `format=`;
4. target extension or MIME hints;
5. the document kind;
6. required capabilities;
7. the workbook operation;
8. compatible IR versions.

The default is chosen only when exactly one bundled route remains. Requirement
analysis is renderer-independent and never reads rows just to make this choice.

For XLSX the workbook operation decides the adapter:

| Operation                     | Adapter                                                    |
|-------------------------------|------------------------------------------------------------|
| Create a new workbook         | `xlsxwriter` (default)                                     |
| Create a new workbook, legacy | `openpyxl` (request with `backend="openpyxl"`)             |
| Fill an existing template     | The OpenPyXL template renderer, after template inspection. |

A template operation never silently falls back to create-new.

```python
render(document, backend="openpyxl")
```

## Execution modes

```python
from caxton import ExecutionMode, write

write(document, "big.xlsx", mode=ExecutionMode.STREAM)
```

| Mode       | Meaning                                                           |
|------------|-------------------------------------------------------------------|
| `AUTO`     | Let the resolver pick (default).                                  |
| `STANDARD` | Ordinary in-memory workbook construction.                         |
| `STREAM`   | Constant-memory / write-only plan, when the renderer supports it. |

Constant-memory execution is a renderer plan with verifiable capabilities, not a
different document type. If the selected renderer cannot honour the requested
mode, that is reported before the target is touched.

## Custom renderers

A renderer implements the public contract in
[`caxton.core.protocols`](../reference/protocols.md): it accepts a versioned
family IR, an `OutputSink` and a `RenderContext`, and publishes a
`RendererDescriptor` declaring family/IR versions, formats, MIME types and
extensions, workbook operations, capabilities and execution modes.

```python
result = write(document, "out.custom", renderer=MyRenderer())
```

There is no global registry and no entry-point discovery at this stage — pass the
renderer directly. It never needs to import `caxton._internal`.

### Reading table rows

`SpreadsheetTableIR.rows` is a `RowStream`, not a sequence: rows stay lazy and
may come from a generator or a one-shot data source, so the stream is consumed
exactly once.

```python
for row in table.rows.consume():  # or just: for row in table.rows
    ...
```

A second pass raises `InvalidOperationError` rather than silently yielding
nothing. A renderer that genuinely needs two passes pays for it explicitly with
`rows = table.rows.materialized()`, which reads the rows into memory and hands
back a fresh stream; `rows.row_count` is the row count when the source knows it
without reading.

Formula nodes are a closed set: match `ResolvedFormulaNode` exhaustively and a
type checker reports the forgotten branch when the IR grows a node.

Artifact bytes are `RenderResult.data`. The older `.content` alias is deprecated
and emits a `DeprecationWarning`.
