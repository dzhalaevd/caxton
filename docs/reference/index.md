# API reference

These pages are generated from the source with
[mkdocstrings](https://mkdocstrings.github.io/).

## Stability

Public stability is divided deliberately:

| Module                                    | Status                                                                |
|-------------------------------------------|-----------------------------------------------------------------------|
| [`caxton`](caxton.md)                     | Recommended short facade. Start here.                                 |
| [`caxton.api`](api.md)                    | The extended generative API and the render/write/validate operations. |
| [`caxton.core.models`](models.md)         | Immutable semantic nodes.                                             |
| [`caxton.core.types`](types.md)           | Semantic value types.                                                 |
| [`caxton.core.formatting`](formatting.md) | Backend-neutral presentation vocabulary.                              |
| [`caxton.core.protocols`](protocols.md)   | Contracts for data sources, sinks and renderers.                      |
| [`caxton.core.ir`](ir.md)                 | Versioned read-only IR used by custom renderers.                      |
| [`caxton.core.errors`](errors.md)         | The public exception and warning hierarchy.                           |
| [`caxton.testing`](testing.md)            | Stable inspection and comparison surface.                             |

!!! danger "Not public API"

    `caxton._internal` — including the bundled renderer implementations, mutable
    IR builders, parsers, planners and package post-processors — is an
    implementation detail. It may change in any release without notice.

## Choosing an import

```python
from caxton import spreadsheet, table, text, write  # everyday work
from caxton.api import xlsx  # XLSX escape hatches
from caxton.core.models import SpreadsheetDocument  # type annotations
from caxton.core.protocols import DataSource, Renderer  # custom integrations
from caxton.testing import inspect_artifact, inspect_spec  # tests
```
