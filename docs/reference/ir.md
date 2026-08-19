# `caxton.core.ir`

The versioned, read-only spreadsheet intermediate representation. A custom
renderer receives a `SpreadsheetIR` and serializes the IR version it declared
support for.

Mutable IR builders, compiler passes and execution plans are **not** part of this
contract.

::: caxton.core.ir
    options:
      show_root_heading: false
      show_root_toc_entry: false
