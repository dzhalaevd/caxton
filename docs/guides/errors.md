# Errors and validation

## Three levels of validation

| Level            | When                               | Reads rows? |
|------------------|------------------------------------|-------------|
| Local invariants | At construction, inside a factory  | No          |
| Structural rules | `validate()`, and before rendering | No          |
| Data validation  | Only when you explicitly ask       | Yes         |

Construction-time checks catch a bad width or an empty title immediately, at the
call site where you made the mistake. Structural checks catch cross-node problems
— unknown column references, duplicate ids, overlapping blocks — before any
source is touched.

```python
from caxton import ValidationError, validate

try:
    validate(document)
except ValidationError as error:
    for issue in error.issues:
        print(issue.code, issue.path, issue.message)
```

`ValidationError` aggregates multiple problems. Each `Issue` carries a message,
a semantic `path`, a `code` and structured `context`, so failures can be
inspected programmatically rather than string-matched.

## The exception hierarchy

Everything inherits from `CaxtonError`, which carries `message`, `path` and
`context`, and preserves the original cause through exception chaining.

```text
CaxtonError
├── CaxtonTypeError        (also a TypeError)
├── CaxtonValueError       (also a ValueError)
├── InvalidOperationError
├── UnsupportedFeatureError
├── ValidationError
│   └── SchemaError
│       ├── ColumnNotFoundError
│       └── DuplicateColumnError
├── DataSourceError
│   ├── UnsupportedDataSourceError
│   ├── DataSourceConsumedError
│   └── DataSourceIterationError
├── DataEvaluationError
│   ├── FieldAccessError
│   ├── MissingFieldError
│   ├── SourceEvaluationError
│   ├── AggregateEvaluationError
│   ├── CyclicColumnError
│   ├── GroupingError
│   └── MatrixConflictError
└── RenderError
    ├── BackendError
    └── TemplateError
        ├── TemplateFormatError
        └── TemplateRefError
            ├── MissingTemplateRefError
            ├── AmbiguousTemplateRefError
            ├── IncompatibleTemplateRefError
            └── InvalidTemplateRefError
```

Because `CaxtonTypeError` and `CaxtonValueError` also subclass the Python
built-ins, existing `except TypeError` / `except ValueError` handlers keep
working, and you can still catch everything with `except CaxtonError`.

## Errors worth knowing

| Error                      | Usually means                                                                                                   |
|----------------------------|-----------------------------------------------------------------------------------------------------------------|
| `DataSourceConsumedError`  | A one-shot source was asked for a second pass.                                                                  |
| `DataSourceIterationError` | Fetching the next row failed; keeps the next row index and the cause.                                           |
| `MissingFieldError`        | The declared field is absent from the row.                                                                      |
| `FieldAccessError`         | An existing property or descriptor raised while being read.                                                     |
| `CyclicColumnError`        | `ref()` chains form a cycle.                                                                                    |
| `MatrixConflictError`      | Several source values land in one matrix cell without an aggregate.                                             |
| `UnsupportedFeatureError`  | The selected target cannot represent the request — including an implicit block after a table of unknown height. |
| `TemplateRefError`         | A named template target is missing, ambiguous or of the wrong shape.                                            |

An error while retrieving the next row is a `DataSourceIterationError`, not a
backend failure — an important distinction when a database cursor dies mid-write.
Likewise, an error raised by an existing property never appears as a
"missing field" error.

## Warnings

Non-fatal issues are reported through warning categories rather than exceptions:

- `CaxtonWarning` — the base category;
- `DocumentWarning` — a document-level concern;
- `PerformanceWarning` — a choice that will be slow or memory-hungry;
- `ExperimentalFeatureWarning` — behaviour that may still change.

```python
import warnings

from caxton import render
from caxton.core.errors import PerformanceWarning

with warnings.catch_warnings():
    warnings.simplefilter("error", category=PerformanceWarning)
    render(document)
```

The warning categories live in `caxton.core.errors`; the exception classes are
also re-exported from the short `caxton` facade.

## Failure timing

Caxton resolves requirements, workbook operation, capabilities and renderer
compatibility **before** opening or writing the target. A capability or template
failure therefore happens while the destination is still untouched, and a failed
path write leaves the previous file intact.
