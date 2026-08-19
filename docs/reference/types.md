# `caxton.core.types`

Backend-independent semantic value types. The column factories in
[`caxton.api`](api.md) attach one of these for you; construct them directly only
when writing a custom renderer or a custom column.

::: caxton.core.types
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — SemanticType
        - Text
        - Integer
        - Decimal
        - Money
        - Percentage
        - Boolean
        - Date
        - Time
        - DateTime
        - Duration
        - Link
