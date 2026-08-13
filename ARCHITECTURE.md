# Caxton Architecture

Caxton is a declarative document-generation library. The user describes the
content and meaning of a document, and the compiler and the selected renderer
transform this specification into the target artifact. XLSX is the first primary
format, but its engines and constraints do not define the Core.

## Core invariants

- The public generative API creates immutable semantic nodes directly; it does
  not expose a separate public builder graph. Fluent operations return a new node.
- The Semantic Model stores intent, but it does not store coordinates, layout
  decisions, execution state, caches, or backend-native objects.
- Nested collections are available only as immutable/read-only values.
- An entity `id` is separate from its value source (`source`) and label (`title`).
- Validation and compilation do not modify the Semantic Model.
- A document family owns its model, validation, compiler, IR, and testing view;
  no universal super-model or super-IR exists.
- I/O belongs to operations and sinks, not to the document model.

Structural immutability does not imply universal hashability or repeatable
execution: a semantic node can reference a stateful or one-shot `DataSource`.

## Public boundaries and dependencies

```text
caxton                 short public facade
├── api                 factories and render/write/validate
├── core
│   ├── models          immutable semantic nodes
│   ├── types           semantic value types
│   ├── formatting      backend-neutral presentation vocabulary
│   ├── protocols       DataSource, Renderer, and other contracts
│   ├── ir              versioned read-only family IR
│   └── errors
├── testing             public inspection and comparison API
└── _internal           orchestration, compilers, resolver, and backends
```

The allowed dependency direction is:

```text
api ───────→ core       testing ───→ core, _internal
api ───────→ _internal  _internal ─→ core
backends ──→ public core contracts
```

`core` does not import `api`, `_internal`, testing, or backend engines.
`_internal` does not import `api`. The public API does not return OpenPyXL,
XlsxWriter, XML, or PDF canvas objects. Mutable compiler passes, the resolver,
caches, and execution plans are not compatibility contracts.

## Semantic Model and families

The common `Document` contract contains only shared semantics (`kind`, metadata).
Families do not inherit capabilities from one another:

| Family       | Semantics                          | Typical targets       |
|--------------|------------------------------------|-----------------------|
| Spreadsheet  | worksheets, grid, formulas, ranges | XLSX, ODS             |
| Flow         | sections, paragraphs, pagination   | DOCX, HTML, PDF       |
| Tabular      | schema and ordered records         | CSV, TSV, simple XLSX |
| Fixed layout | pages and positioned blocks        | PDF, SVG, images      |

Shared tabular data uses `TableData` (`schema` + `DataSource`), but the visual
`SpreadsheetTable` and `FlowTable` remain family-specific nodes. Business
concepts (`Receipt`, `Invoice`, or a specific `Report`) are composed in the
application layer from neutral nodes and do not become Core families.

Backend-independent semantic types include `Text`, `Integer`, `Decimal`,
`Boolean`, `Date`, `Time`, `DateTime`, `Duration`, `Money`, `Percentage`, and
`Link`. Formatting (alignment, border, color, font, display format, and width
hints) is stored separately from value semantics. The renderer controls the
physical representation and emits a capability diagnostic when it cannot
preserve the semantics.

## Pipeline

```text
Public API + raw inputs
    ↓  DataSource coercion without reading rows
Immutable Semantic Model
    ↓  structural validation
Requirement analysis → RequiredCapabilities + WorkbookOperation
    ↓  resolver checks the renderer descriptor and IR compatibility
Family compiler × selected renderer capabilities
    ↓
Versioned read-only Family IR
    ↓
Renderer → OutputSink → RenderResult
```

Requirement analysis does not depend on the renderer. The compiler performs
lowering: it resolves references, coordinates, layout, and other physical
decisions without writing them back to the model. The renderer serializes the
agreed IR version and owns the backend-specific execution plan.

`render()` uses a memory sink and returns `RenderResult`; `write()` normalizes a
path, buffer, or another target into an `OutputSink`. The system rejects an
incompatible or ambiguous renderer before writing starts.

For a path target, the built-in `FileSink` owns a sibling staging file: the
renderer writes to the destination provided by the sink, and the sink atomically
replaces the target only after the backend completes successfully. For a binary
target, the adapter retries short writes until it delivers the complete output
or raises a stable render error.

## Data, computation, and streaming

`table(data, ...)` coerces the input to a public `DataSource` once and stores the
source instead of the original framework object or a materialized list. Built-in
ingestion supports mappings, `NamedTuple`, dataclass and attribute objects, lazy
iterables, and direct custom `DataSource`/`RowAccessor` implementations without
importing Pydantic, ORM, or other frameworks into the Core. DataFrame/Arrow-like
inputs require a separate batch contract.

Mapping access uses `row[field]`; object access uses the exact attribute.
Explicit `path(...)` defines nested traversal; a single semantic row evaluator
evaluates callables and expressions. An error from an existing property or
descriptor does not appear as a missing-field error.

Python row expressions and spreadsheet formulas form separate semantic
hierarchies. `field()`/`path()` read raw data-source values and `ref()` reads
the evaluated value of another semantic column; all three are evaluated by the
library before rendering, while `col()`, `table_ref()`, and `sheet_ref()`
remain formula intent. `field()` never resolves a column id and `ref()` never
reads a row field, so the two namespaces cannot be confused. The
compiler resolves their semantic IDs into cell/range nodes in the Spreadsheet
IR; the XLSX renderer materializes A1 or structured references. A Python
expression cannot depend on a formula-backed column because its value appears
only in the artifact. A range reference requires a known `row_count`: the
compiler does not perform a hidden pass over a one-shot or `UNKNOWN` source to
calculate the end of the range.

  Aggregation is expression intent represented by backend-independent
`AggregateExpr(function, expressions, where, default)`. The initial execution adapter
passes one Python value sequence per expression to an arbitrary Python callable;
it does not normalize inputs or remove `None`. An ungrouped aggregate uses the
whole source as one scope, while grouped tables use one leaf group per scope.
When filtering leaves a scope empty, an explicitly declared `default` is returned
without invoking the callable; without a default, the callable retains authority
over the empty input and any failure is reported as `AggregateEvaluationError`.
Grouping belongs to `SpreadsheetTable` columns rather than a separate public
`GroupedTable`; order defaults to first seen, and the compiler derives exact row
and merge ranges from resolved hierarchical scopes. Group hierarchy follows the
physical declaration order of grouped columns. Dimension identity is strict:
Python value types are distinct, and `Decimal` scale is preserved, so `True`,
`1`, `Decimal("1")`, and `Decimal("1.0")` form separate groups. Sorted groups
place `None` last for both ascending and descending order.

`Matrix` is a spreadsheet-family block with typed row-dimension,
column-dimension, and value columns. Expressions accepted by the convenience
factory are normalized into columns; explicit columns carry semantic type,
format, style, width, and stable ids. Its compiler path discovers dynamic keys
in first-seen order, uses the same strict identity as grouping, and requires an
`AggregateExpr` when more than one source value resolves to a cell. Generated
value columns expose their dimension key through the public testing layout, so
tests do not depend on compiler-generated ids. Grouped tables and matrices
buffer semantic rows internally and
consume `ONE_SHOT` sources exactly once. They are not append-only streaming
plans. `DataSource` remains responsible only for row ingestion and never gains
`groupby`, pivot, or aggregation operations.

## Spreadsheet block layout

A worksheet holds a closed set of spreadsheet blocks: `SpreadsheetTable`,
`Matrix`, `Title`, `Spacer`, `Image`, `Chart`, and the `Stack` flow container.
Blocks carry intent only; the compiler owns placement. A dedicated layout pass
walks the declared blocks in order, measures each one, and assigns a physical
anchor and occupied range before any IR node is built. Ordinary-table
measurements are structural: one header row plus non-consuming `row_count` plus
an optional footer row. Grouped tables and matrices are measured from their
single-pass prepared result because their output shape differs from the input.
Titles occupy one row; images and charts convert their declared pixel size into
whole cells.

Explicit `anchor` remains the escape hatch. An anchored block keeps its declared
position and still advances the flow cursor, so a following implicit block never
lands inside it. Overlaps between statically measurable blocks are reported as
`block_overlap` validation issues before any source is consumed, even when the
worksheet also contains a shape-dependent grouped table or matrix. Prepared
shapes receive a second placement check before rendering. When a table height is
unknown the flow cursor becomes invalid instead of guessing; the next implicit
block raises an `UnsupportedFeatureError` and the document keeps working if
every following block is anchored explicitly.

Charts bind to data through `table_ref(...)` plus semantic column ids. The
compiler resolves them into physical ranges of the placed table, so a chart, like
a range reference, requires a known `row_count`.

A source declares its repeatability as `REITERABLE`, `ONE_SHOT`, or `UNKNOWN`.
Coercion and structural validation do not read rows. A second pass over a
one-shot source raises `DataSourceConsumedError`; an unknown source does not
permit a hidden repeated pass. A multi-pass feature is rejected before writing
or uses an explicit documented buffering policy. Data validation and semantic
inspection never read rows implicitly. Ordinary layout inspection reads rows
only with an explicit `sample`/`full` scope; grouped/matrix layout compilation
still performs its documented single-pass buffering because shape resolution
requires the complete source.

An error while retrieving the next row from an iterator is a
`DataSourceIterationError`, not a backend failure, and it preserves the index of
the next row and the original cause.

## Renderer and XLSX

The public `Renderer` accepts a versioned family IR, an `OutputSink`, and a
`RenderContext`, while its descriptor declares family/IR versions, formats,
MIME types/extensions, workbook operations, capabilities, and execution modes.
A custom renderer can be passed directly without importing `_internal`; no
global provider registry or entry-point discovery exists at this stage.

For XLSX, the workbook operation is determined before adapter selection:

| Operation                  | Adapter                                             |
|----------------------------|-----------------------------------------------------|
| `CREATE_NEW_WORKBOOK`      | default `XlsxWriterRenderer`                        |
| explicit legacy create-new | `OpenpyxlRenderer`                                  |
| `USE_EXISTING_TEMPLATE`    | planned `OpenpyxlTemplateRenderer` after inspection |

The template pipeline first builds a read-only `TemplateContext` and then passes
it to the family compiler. A template operation does not silently fall back to
create-new. Constant-memory/write-only is a renderer execution plan with
verifiable capabilities, not a separate document type. Backend hooks and
post-processing are explicit, namespaced, and absent from the Core model.

Caxton ships as a single distribution. XlsxWriter and OpenPyXL are part of the
base runtime dependencies, but they do not form a shared rendering pipeline:
the built-in XLSX artifact inspector also uses OpenPyXL. Official backends ship
with `caxton`; they do not use separate packages.

## Validation, diagnostics, and testing

Validation has three levels: construction-time local invariants, structural
cross-node rules without data reads, and explicitly requested data validation.
All library errors inherit from `CaxtonError`; the public categories distinguish
validation, data source/evaluation, invalid operation, unsupported feature, and
render/backend failures. Errors contain a semantic path and structured context,
and exception chaining preserves the original cause. Multiple validation issues
are aggregated; non-fatal issues use `warnings` categories. Type and value
errors in the public construction API use the Python-compatible `TypeError` and
`ValueError` subclasses `CaxtonTypeError` and `CaxtonValueError`, so callers
can also catch them through `CaxtonError`.

`caxton.testing` is a stable, pytest-independent API with three levels:

- semantic inspection by IDs, domain-aware comparison, and canonical snapshots;
- read-only family layout inspection with an explicit row scope;
- backend-neutral inspection of a completed artifact.

The XLSX inspector uses OpenPyXL only inside the implementation and returns
immutable public values. The public API does not expose internal IR storage,
parsers, or diff algorithms.

## Extension

- A new operation is added as a function, not as a method on every semantic node.
- Direct custom objects use small structural protocols without a registry.
- A new backend implements the public renderer contract and accepts the existing IR.
- A new family adds its own model/compiler/IR without extending the other families.
- Conversion between families uses an explicit `DocumentConverter` and returns a
  loss report; changing the backend within a family remains a render operation.
- Registries, discovery, pass managers, and universal hook systems appear only
  with a validated use case.
