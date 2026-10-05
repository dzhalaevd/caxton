# Caxton internals

!!! warning

    This section of the documentation is for advanced users. You should probably stay away from these APIs if you don’t
    know what you are doing.

Most applications can stop at documents, `render()` and `write()`. The internal path becomes useful when a generator is
consumed earlier than expected, a renderer rejects a document, or you are implementing a custom renderer. In those
cases, follow the document through the pipeline instead of treating rendering as one opaque call.

## Follow one render

Consider `write(document, "report.xlsx")`. The call crosses several boundaries before the destination changes:

```text
SpreadsheetDocument
    │
    ├─ structural validation
    │
    ├─ requirement analysis
    │       document features, workbook operation, execution constraints
    │
    ├─ renderer resolution
    │       format + backend + capabilities + compatible IR version
    │
    ├─ spreadsheet compilation
    │       preparation + layout + resolved formulas
    │
    ├─ SpreadsheetIR
    │
    ├─ renderer execution
    │       backend objects and execution plan
    │
    └─ output transaction
            commit completed bytes to the path or buffer
```

Each stage has one owner. Structural validation rejects conflicts in the declaration without reading rows. Requirement
analysis describes what the document needs. The resolver chooses a compatible route, and the spreadsheet compiler lowers
the document against that renderer’s declared capabilities. Only the renderer creates OpenPyXL or XlsxWriter objects.
The output transaction keeps their bytes away from the destination until rendering succeeds.

This separation is also how to read an exception. A missing column reference is a validation problem; an unsupported
feature belongs to renderer resolution or execution planning; an engine failure belongs to backend execution; a failed
flush or replacement belongs to delivery. [Testing and diagnostics](troubleshooting.md#locate-the-stage-that-failed)
maps the public exception categories to these stages.

## Keep state in the layer that owns it

The document passed by the application is not gradually turned into a workbook. Caxton keeps the declaration unchanged
and moves derived state into later layers.

| Layer                          | What it owns                                                                      | What it does not own                                                            |
|--------------------------------|-----------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Semantic model                 | Worksheets, blocks, semantic ids, declared anchors, value and presentation intent | Resolved ranges, backend objects, caches, execution state                       |
| Preparation and compiler state | Grouped output, matrix axes, template target shape, resolved layout and formulas  | Public application state or backend workbook objects                            |
| Family IR                      | A versioned, read-only input for a compatible renderer                            | Mutable compiler passes or a universal representation for every document family |
| Renderer                       | Backend objects, physical serialization and its execution plan                    | Changes to the semantic document                                                |
| Output transaction             | Staged bytes and the final commit                                                 | Document semantics or rendering decisions                                       |

An explicit A1 anchor is still semantic intent. The resolved anchor, occupied range and merge coordinates belong to
layout. That distinction lets a document state a fixed placement requirement without carrying mutable compiler results.

The IR boundary is family-specific for the same reason. `SpreadsheetIR` describes a compiled spreadsheet; it is not a
generic document tree that a PDF or flow-document renderer must reinterpret.

## Know when rows are consumed

Construction, structural validation, requirement analysis and renderer resolution do not iterate a row source. They may
read declared source metadata such as repeatability or a known row count.

Compilation is where the paths diverge:

| Document shape                    | First row read                                                                   |
|-----------------------------------|----------------------------------------------------------------------------------|
| Ordinary table with a lazy source | The renderer consumes the table’s IR row stream.                                 |
| Grouped or aggregate table        | Preparation reads the source to determine the output groups and values.          |
| Matrix                            | Preparation reads the source to discover axes and resolve duplicate coordinates. |
| Template target                   | Template compilation prepares the target rows before final placement checks.     |

Preparation consumes a one-shot source once. It does not make that source reusable. The resulting IR may still expose a
`RowStream`, and that stream also rejects a second pass. A custom renderer that needs repeated access must call
`materialized()` deliberately and accept the memory cost.

This timing explains one otherwise surprising failure. A named native table can make `STREAM` incompatible before its
ordinary row stream is entered. Grouping and matrices are different: compilation prepares their shape first, then
XlsxWriter selects an execution plan and rejects shape-dependent buffering. The destination remains untouched, but the
source may already be consumed. Retry with a fresh source.

## Separate route selection from renderer execution

Renderer selection happens before spreadsheet compilation. Requirement analysis produces a backend-neutral description
of the document: required features, workbook operation, compatible IR version and execution constraints. The resolver
compares those requirements with renderer descriptors. An explicit renderer or backend takes priority; otherwise the
format and target hints narrow the bundled routes.

The selected descriptor supplies capabilities to the compiler. The compiler uses them while resolving formulas, layout
and family-specific constraints, but it does not choose the backend.

The renderer makes one later decision: how to execute the compatible IR. For XlsxWriter, `STANDARD` and constant-memory
plans can represent different feature sets. `AUTO` lets the renderer select a compatible plan; `STREAM` requires a
streaming plan and fails if the compiled shape cannot use one. This is execution-plan selection, not renderer
resolution.

Templates take a separate route. The workbook operation is `USE_EXISTING_TEMPLATE`, so resolution cannot silently fall
back to a create-new renderer. Caxton inspects the template, compiles against its named targets, and passes the result
to the template renderer.

## Treat the IR as renderer input

Most users should inspect documents through `caxton.testing`, not through the IR. The public IR exists so a custom
renderer can consume a stable, versioned contract after Caxton has resolved spreadsheet semantics.

Two details matter when implementing one:

- the renderer descriptor must advertise the document family, supported IR versions, workbook operations, execution
  modes and semantic features it can preserve;
- spreadsheet row streams are one-shot, while resolved formula nodes form a closed union that the renderer can handle
  exhaustively.

Pass a custom renderer directly to `render()` or `write()`. Caxton has no global renderer registry or entry-point
discovery. The complete example lives in [Rendering and delivery](render.md#add-a-custom-renderer); the exact contracts
are in [`caxton.core.protocols`](../reference/protocols.md) and
[`caxton.core.ir`](../reference/ir.md).

Mutable IR builders, compiler passes, resolver state and bundled renderer classes are implementation details. Importing
them couples application code to a pipeline stage that may change without a public compatibility promise.

## Understand the output boundary

`render()` supplies a memory sink and returns the completed artifact in `RenderResult.data`. `write()` first normalizes
a path or binary object into an output sink, then wraps it in a transaction.

For a path, the transaction writes a sibling staging file and atomically replaces the destination after the renderer
succeeds. A failed validation, compilation, render or staging write leaves the old path unchanged. For a binary target,
Caxton also waits for a complete artifact before delivery. It rewinds and truncates seekable buffers and retries valid
short writes.

The final buffer delivery itself cannot be rolled back after an external `write()` accepts bytes. If that commit fails,
Caxton raises `OutputError` and chains the original I/O exception. This is why “the target is untouched before commit”
is stronger than “every target can be restored after a failed commit.”

## Extend at a public seam

Choose the smallest public boundary that owns the behavior:

| Need                                                           | Public extension point       | Continue with                                                                |
|----------------------------------------------------------------|------------------------------|------------------------------------------------------------------------------|
| Read an unusual row-oriented source                            | `DataSource`                 | [Tables and data](tables.md#adapt-unusual-sources-at-the-boundary)           |
| Add application-specific value semantics                       | `SemanticType`               | [Values and presentation](presentation.md#add-an-application-specific-value) |
| Serialize a supported family through another backend or format | `Renderer` and the family IR | [Rendering and delivery](render.md#add-a-custom-renderer)                    |
| Adjust an XLSX template with OpenPyXL                          | A namespaced template hook   | [Templates](templates.md#run-a-focused-openpyxl-hook)                        |

Framework lifecycle, ORM query planning and batch execution remain in the application. Engine objects belong inside a
renderer or a template hook. Package XML paths belong to the XLSX route. None of them should appear in a semantic model
or a generic Core protocol.

For changes to Caxton itself, use
[`ARCHITECTURE.md`](https://github.com/dzhalaevd/caxton/blob/main/ARCHITECTURE.md) as the normative dependency and
feature boundary. Underscore-prefixed packages, future document families, registries and deferred extension sketches are
not public contracts.
