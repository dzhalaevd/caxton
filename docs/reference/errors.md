# `caxton.core.errors`

Every library exception inherits from `CaxtonError` and carries a semantic path
plus structured context. `CaxtonTypeError` and `CaxtonValueError` also subclass
the Python built-ins, so existing handlers keep working.

See [Errors and validation](../guides/errors.md) for the hierarchy at a glance.

## Base

::: caxton.core.errors
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — CaxtonError
        - CaxtonTypeError
        - CaxtonValueError
        - InvalidOperationError
        - UnsupportedFeatureError

## Validation

::: caxton.core.errors
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — ValidationError
        - SchemaError
        - ShapeError
        - ColumnNotFoundError
        - DuplicateColumnError
        - Issue
        - Notification

## Data

::: caxton.core.errors
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — DataSourceError
        - UnsupportedDataSourceError
        - DataSourceConsumedError
        - DataSourceIterationError
        - DataEvaluationError
        - FieldAccessError
        - MissingFieldError
        - SourceEvaluationError
        - AggregateEvaluationError
        - CyclicColumnError
        - GroupingError
        - MatrixConflictError

## Rendering and templates

::: caxton.core.errors
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — RenderError
        - BackendError
        - TemplateError
        - TemplateFormatError
        - TemplateRefError
        - MissingTemplateRefError
        - AmbiguousTemplateRefError
        - IncompatibleTemplateRefError
        - InvalidTemplateRefError

## Warnings

::: caxton.core.errors
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — CaxtonWarning
        - DocumentWarning
        - PerformanceWarning
        - ExperimentalFeatureWarning
