# `caxton.testing`

A stable, pytest-independent inspection and comparison API. Every value it
returns is immutable and backend-neutral.

See [Testing documents](../guides/testing.md) for guidance on which level to use.

## Semantic inspection

::: caxton.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — inspect_spec
        - SpreadsheetSpec
        - WorksheetSpec
        - TableSpec
        - MatrixSpec
        - BlockSpec
        - BlockKind
        - ColumnSpec
        - ConditionalRuleSpec
        - SourceSpec
        - SourceKind
        - FormulaSpec
        - FormulaKind
        - CallableSpec
        - SemanticTypeSpec

## Layout inspection

::: caxton.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — inspect_layout
        - Rows
        - RowsMode
        - SpreadsheetLayout
        - WorksheetLayout
        - TableLayout
        - BlockLayout
        - RowLayout
        - CellLayout
        - CellKind
        - ColumnLayout
        - FooterLayout
        - TotalLayout
        - ChartLayout
        - SeriesLayout
        - ImageLayout
        - TextLayout
        - ConditionalRuleLayout

## Artifact inspection

::: caxton.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — inspect_artifact
        - SpreadsheetArtifact
        - ArtifactWorksheet
        - ArtifactTable
        - ArtifactColumn
        - ArtifactCell
        - ArtifactConditionalFormat
        - ArtifactSource
        - ArtifactInspectionError

## Comparison and snapshots

::: caxton.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — assert_spreadsheet_equal
        - SpreadsheetAssertionError
        - Difference
        - DifferenceKind
        - canonical_snapshot
        - SNAPSHOT_SCHEMA

## Hypothesis strategies

Requires the `hypothesis` extra.

::: caxton.testing.strategies
    options:
      show_root_heading: false
      show_root_toc_entry: false
