# `caxton`

The short public facade. Everything here is re-exported from
[`caxton.api`](api.md) and `caxton.core`, so importing from `caxton` is the
recommended default.

## Document and block factories

::: caxton
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — spreadsheet
        - sheet
        - table
        - matrix
        - title
        - spacer
        - image
        - chart
        - stack

## Column factories

::: caxton
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — text
        - integer
        - decimal
        - money
        - percentage
        - boolean
        - date
        - time
        - datetime
        - duration
        - link

## Expressions, formulas and rules

::: caxton
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — field
        - path
        - ref
        - col
        - table_ref
        - sheet_ref
        - absolute
        - when

## Operations

::: caxton
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — validate
        - render
        - write
        - ExecutionMode

## Templates and data sources

::: caxton
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — template
        - repeat
        - data_source
