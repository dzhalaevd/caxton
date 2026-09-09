# `caxton.api`

The extended generative API. `caxton` re-exports most of it; import
`caxton.api` directly for the backend-specific escape hatches.

## Factories and operations

Identical to the [`caxton`](caxton.md) facade — `caxton.api` is where they are
defined.

```python
from caxton.api import (
    Column,
    ColumnSchema,
    SemanticType,
    Text,
    literal,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    validate,
    write,
)
```

`Column(...)` is the normalized generic constructor. `ColumnSchema` provides
named reusable column tuples, and `literal()` creates a constant Python row
expression. Built-in semantic types and `SemanticType` are exported here and
from the short `caxton` facade.

## Formatting and format helpers

```python
from caxton.api import (
    AutoWidth,
    Style,
    StyleSheet,
    custom_format,
    date_format,
    decimal_format,
    money_format,
    percentage_format,
    time_format,
)
```

See [`caxton.core.formatting`](formatting.md) for the full documentation.

## XLSX escape hatches

Backend-specific, namespaced, and never part of the core model.

::: caxton.api.xlsx
    options:
      show_root_heading: false
      show_root_toc_entry: false
