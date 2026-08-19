# `caxton.core.protocols`

Structural contracts. Implement these to plug in your own data source, output
target or renderer — no registration and no `caxton._internal` import required.

## Data

::: caxton.core.protocols
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — DataSource
        - DataSourceInfo
        - RowAccessor
        - Repeatability

## Rendering and output

::: caxton.core.protocols
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — Renderer
        - OutputSink
        - OutputTarget
        - BinaryWritable
        - BinarySeekable

## Templates

::: caxton.core.protocols
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — TemplateRenderer
        - TemplateInspector

## Renderer contracts and results

::: caxton.core.rendering
    options:
      show_root_heading: false
      show_root_toc_entry: false
