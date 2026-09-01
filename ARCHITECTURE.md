# Caxton Architecture

Caxton is a declarative document-generation library. The user describes the
content and meaning of a document, and the compiler and the selected renderer
transform this specification into the target artifact. XLSX is the first primary
format, but its engines and constraints do not define the Core.

## Authority and delivered scope

This file is the normative source for the current architecture and supported
boundaries. `AGENTS.md` translates those boundaries into repository workflow;
the README and examples demonstrate selected public flows. Design notes and use
case documents can explain motivation or proposed APIs, but they do not expand
the compatibility contract described here.

The delivered document family is `SpreadsheetDocument` and the delivered
artifact profile is XLSX. Flow, tabular, and fixed-layout families below define
extension boundaries only: their names in examples do not imply public
constructors, compilers, IRs, or renderers.

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
- Formula intent (`col()`/`table_ref()`/`sheet_ref()`) is limited to
  references, arithmetic, and comparison. Conditional and lookup business
  logic (`IF`, `VLOOKUP`/`XLOOKUP`, `INDEX`/`MATCH`, and similar) is computed
  in the Python row/aggregate layer before rendering; it is never reintroduced
  as new formula node types or as an unvalidated raw-formula-text escape
  hatch. A report generated from Python computes its business rules in
  Python, where they stay typed, tested, and reviewable, not inside a
  generated artifact.

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

Public stability is divided deliberately:

- `caxton` is the recommended short facade and `caxton.api` is the extended
  generative API;
- `caxton.core` contains semantic models, value types, errors, protocols,
  renderer signature types, and versioned read-only IR contracts used by custom
  renderers;
- `caxton.testing` is the stable inspection and comparison surface;
- `caxton._internal`, including bundled renderer implementations, mutable IR
  builders, parsers, planners, and package post-processors, is not public API.

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

Built-in resolution considers, in order, an explicitly supplied renderer, an
explicit backend, an explicit format, target extension or MIME hints, document
kind, required capabilities, workbook operation, and compatible IR versions.
The default is selected only when exactly one bundled route remains. Requirement
analysis is renderer-independent and never reads rows merely to make this
selection.

For a path target, the built-in `FileSink` owns a sibling staging file: the
renderer writes to the destination provided by the sink, and the sink atomically
replaces the target only after the backend completes successfully. For a binary
target, the adapter retries short writes until it delivers the complete output
or raises a stable render error.

## Data, computation, and streaming

The table declaration is `table(source=data, columns=(...))`. Both peer inputs
are keyword-only: the first defines row data and the second defines its ordered
semantic schema. This deliberate table-specific shape prevents a source from
being confused with a column sequence; block factories with one primary value
retain their positional leading argument. The table coerces the input to a
public `DataSource` once and stores the source instead of the original framework
object or a materialized list.

Flat typed factories keep semantic identity, row access, and presentation as
separate model properties. A value origin is always explicit through `source=`
or `formula=`. For the common exact-field case,
`text(source="name", title="Name")` deterministically uses `"name"` as both the
top-level field name and the semantic id. An explicit `id=` overrides that
identity; it is required for callables, paths, expressions, aggregates, and
formulas because those sources do not define a stable semantic name. Factory
parameters remain keyword-only. Built-in
ingestion supports mappings, `NamedTuple`, dataclass and attribute objects, lazy
iterables, and direct custom `DataSource`/`RowAccessor` implementations without
importing Pydantic, ORM, or other frameworks into the Core. DataFrame/Arrow-like
inputs require a separate batch contract.

Coercion recognizes an existing structural `DataSource` first, rejects
DataFrame/Arrow-like and scalar/text/callable inputs with a focused error, wraps
single supported row objects, and otherwise adapts a lazy iterable. It does not
use `asdict`, `model_dump`, `vars`, `dir`, schema inference, or a global adapter
registry. ORM/session lifecycle, eager loading, projection, and prefetch remain
the caller's responsibility.

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
calculate the end of the range. Formula intent stays deliberately narrow:
references plus arithmetic and comparison, so it can express a value that must
stay live and recalculate for the person who opens the artifact. Conditional
branching and lookups belong to the Python row/aggregate layer instead, so
business logic stays where it is typed and tested, not encoded as spreadsheet
formula text the compiler does not otherwise inspect.

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
place `None` last for both ascending and descending order. Float identity folds
`-0.0` into `0.0` and treats all NaN values as one canonical group.

`Matrix` is a spreadsheet-family block with typed row-dimension,
column-dimension, and value columns. Expressions accepted by the convenience
factory are normalized into columns, and its row input uses the same keyword
`source=` as tables. A bare string axis names one exact top-level field, remains
a `Text` dimension, and uses that string as its id; a dot has no path semantics,
and duplicate names receive deterministic numeric suffixes. Callers use
`path(...)` for traversal or an explicit column when semantic type, format,
style, width, grouping, or a stable custom id matters. Its compiler path discovers dynamic keys
in first-seen order unless a dimension declares grouping order, uses the same
strict identity as grouping, and requires an `AggregateExpr` when more than one
source value resolves to a cell. Row-dimension merge intent produces vertical
merges; flattened column headers reject merge intent. Generated
value columns expose their dimension key through the public testing layout, so
tests do not depend on compiler-generated ids. Grouped tables and matrices
buffer semantic input rows internally and consume `ONE_SHOT` sources exactly
once. Aggregate inputs are evaluated during that pass, after their filters, so
the original source row object can be released before grouping. Matrix output
rows are emitted lazily after the dynamic axes are known, so sparse inputs do
not also retain the dense Cartesian output. They are not append-only streaming
plans. Prepared placements are checked against the XLSX sheet bounds (1,048,576
rows by 16,384 columns) before rendering. `DataSource` remains responsible only
for row ingestion and never gains `groupby`, pivot, or aggregation operations.

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

Because structural validation does not consume rows, a clean `validate()`
result cannot guarantee a clean render for shape-dependent blocks. Grouped-table
or matrix preparation can consume a `ONE_SHOT` source before the second placement
check discovers an overlap; after that failure, the source remains consumed.

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

| Operation                  | Adapter                                               |
|----------------------------|-------------------------------------------------------|
| `CREATE_NEW_WORKBOOK`      | default `XlsxWriterRenderer`                          |
| explicit legacy create-new | `OpenpyxlRenderer`                                    |
| `USE_EXISTING_TEMPLATE`    | dedicated `OpenpyxlTemplateRenderer` after inspection |

The template pipeline first builds a read-only `TemplateContext` and then passes
it to the family compiler. A template operation does not silently fall back to
create-new. Constant-memory/write-only is a renderer execution plan with
verifiable capabilities, not a separate document type. Backend hooks and
post-processing are explicit, namespaced, and absent from the Core model.

The XLSX adapter resolves generic `ref(...)` template targets through workbook-
or worksheet-scoped defined names. A normal target is a data-only region; a
`repeat(ref(...))` target copies the named block once per semantic row, including
styles, translated relative formulas, and contained merges. The renderer works
on a private workbook copy and writes to the sink only after rendering, hooks,
and ordered XLSX package post-processing succeed. Pivot package paths and
relationships remain backend-local descriptor data.

Caxton ships as a single distribution. XlsxWriter and OpenPyXL are part of the
base runtime dependencies, but they do not form a shared rendering pipeline:
the built-in XLSX artifact inspector also uses OpenPyXL. Official backends ship
with `caxton`; they do not use separate packages.

## Delivered spreadsheet/XLSX profile

The following behavior is implemented and forms the current feature boundary:

| Area                          | Delivered behavior                                                                                                                                         |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Tables and values             | typed columns, mappings and Python row objects, Python expressions, semantic value normalization, explicit and automatic widths                            |
| Spreadsheet expressions       | semantic cell/range and cross-sheet formulas, conditional formatting, totals, and named table references                                                   |
| Data shaping                  | hierarchical grouping, arbitrary Python aggregates with filters/defaults, and dynamic matrix axes with duplicate-cell conflict detection                   |
| Presentation                  | reusable styles/themes, multiple worksheets, filters, freeze panes, titles, spacers, stacks, images, and charts bound to named tables                      |
| Layout                        | flow placement, explicit A1 anchors, overlap detection, merge ranges, sheet-bound checks, and post-preparation placement checks for shape-dependent blocks |
| Execution                     | standard and constant-memory create-new plans, one-shot protection, atomic file output, binary targets, and stable capability diagnostics                  |
| Templates and XLSX extensions | named-range targets, repeated template blocks, pivot cache refresh, namespaced OpenPyXL hooks, and ordered backend-local package post-processing           |
| Testing                       | semantic inspection/diff, canonical snapshots, explicit-scope layout inspection, XLSX artifact inspection, and optional Hypothesis strategies              |

Charts currently bind to an existing named table; an independent inline chart
`data=` source is not part of the public API. A reusable Python factory can
construct a fresh immutable specification, but bind-time `source_ref()` and
`bind()` placeholders are not implemented.

## Validation, diagnostics, and testing

Validation has three levels: construction-time local invariants, structural
cross-node rules without data reads, and explicitly requested data validation.
Structural validation rejects direct and indirect dependency cycles formed by
Python `ref()` expressions or formula `col()`/`table_ref()`/`sheet_ref()`
references, including cycles that cross worksheets. The diagnostic includes the
complete closed semantic path of the cycle. Cycle detection, like overlap
validation, never consumes row data and completes before requirement analysis
or compilation. These structural issues originate from
`CyclicReferenceError`; `CyclicColumnError` remains the row evaluator's
defensive failure if that internal boundary is invoked without validation.
All library errors inherit from `CaxtonError`; the public categories distinguish
validation, data source/evaluation, invalid operation, unsupported feature, and
render/backend failures. Output delivery failures use `OutputError` rather than
being reported as backend failures. Errors contain a semantic path and an
immutable structured-context snapshot, and exception chaining preserves the
original cause. Multiple validation issues are aggregated; non-fatal issues use
`warnings` categories. Type and value errors in the public construction API use
the Python-compatible `TypeError` and `ValueError` subclasses `CaxtonTypeError`
and `CaxtonValueError`, so callers can also catch them through `CaxtonError`.

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

## Deliberate deferrals

The following are architectural extension points or proposals, not current
public promises:

- Flow, tabular, and fixed-layout models, their IRs and renderers, including CSV,
  DOCX, HTML, PDF, SVG, and image outputs;
- cross-family `DocumentConverter` and loss reports;
- schema inference, `BatchDataSource`, async sources, framework-specific source
  adapters, and public source/type-adapter registries;
- bind-time data placeholders, inline chart data, and a universal testing
  contract spanning semantic, layout, and artifact views;
- entry-point discovery, provider priority/conflict resolution, compiler pass
  managers, global hook/event registries, and universal extension managers.

A deferred item becomes part of the contract only when a concrete public use
case, implementation, focused tests, examples, and this file agrees. Names or
sketches in design documentation do not reserve a public API.
