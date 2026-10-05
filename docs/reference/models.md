# `caxton.core.models`

Immutable semantic nodes. These store intent only — never coordinates, resolved
layout, execution state or backend-native objects.

## Document and worksheets

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - SpreadsheetDocument
        - Worksheet
        - SpreadsheetBlock
        - DocumentKind
        - DocumentMetadata

## Tables

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - SpreadsheetTable
        - TableData
        - Column
        - Grouping
        - GroupOrder
        - Total
        - Totals
        - AggregateFunction
        - ConditionalRule
        - when

## Other blocks

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Matrix
        - Title
        - Spacer
        - Image
        - Chart
        - ChartKind
        - Stack
        - BlockDirection
        - Freeze

## Python expressions

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Expression
        - FieldRef
        - PathRef
        - ColumnRef
        - LiteralExpression
        - BinaryExpression
        - TransformExpression
        - AggregateExpr
        - AggregateCallable
        - BinaryOperator
        - CallableSource
        - ColumnSource
        - ColumnSourceInput
        - RowCallable
        - TransformCallable
        - field
        - path
        - ref
        - literal

## Spreadsheet formulas

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Formula
        - FormulaLiteral
        - FormulaBinary
        - FormulaInput
        - FormulaOperator
        - FormulaScalar
        - CellReference
        - RangeReference
        - TableReference
        - SheetReference
        - col
        - table_ref
        - sheet_ref
        - absolute

## Block traversal and defaults

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - DEFAULT_OBJECT_WIDTH
        - DEFAULT_OBJECT_HEIGHT
        - contains_aggregate
        - iter_blocks
        - iter_tables

## Templates

::: caxton.core.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - TemplateSpecification
        - TemplateRepeat
        - TemplateReference
        - TemplateContext
        - TemplateCompilationResult
        - ResolvedTemplateTarget
        - Extension
