# Caxton

**Declarative document generation for Python.**

Caxton lets you describe *what* a document contains and *what its values mean*.
The compiler and the selected renderer decide *where* everything goes and how the
target format represents it.

!!! warning "Pre-alpha"

    Caxton is under active development and is not ready for production use. The
    delivered surface is the spreadsheet document family rendered to XLSX; see
    [Architecture](architecture.md) for the exact boundary.

## A first document

```python
from caxton import render, sheet, spreadsheet, table, text, write

rows = [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}]

report = spreadsheet(
    sheet(
        "People",
        table(
            source=rows,
            columns=(text(source="name", title="Name"),),
        ),
    ),
)

result = render(report)

write(report, "people.xlsx")
```

## What you get

<div class="grid cards" markdown>

-   __Semantic, not physical__

    Columns carry semantic types — `money`, `percentage`, `date`, `duration` —
    instead of number formats. The renderer chooses the representation.

-   __Immutable specifications__

    Every factory returns a frozen node and every fluent method returns a new
    one, so a report factory can be reused for different row sets without
    copying or mutation.

-   __Lazy data__

    Building and validating a document never reads a row. One-shot sources are
    tracked and a hidden second pass is rejected instead of silently producing
    an empty table.

-   __Testable output__

    [`caxton.testing`](reference/testing.md) inspects intent, compiled layout,
    and the finished artifact — without exposing OpenPyXL or XlsxWriter objects.

</div>

## Where to go next

- [Installation](getting-started/installation.md) — add Caxton to a project.
- [Quickstart](getting-started/quickstart.md) — build, verify and write a report.
- [Core concepts](getting-started/concepts.md) — the model, the pipeline, the vocabulary.
- [Guides](guides/tables-and-columns.md) — task-oriented walkthroughs.
- [API reference](reference/index.md) — generated from the source.
