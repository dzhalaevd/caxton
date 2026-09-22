"""Capabilities shared by the bundled XLSX adapters."""

_SEMANTIC_FEATURES = frozenset(
    (
        "semantic:boolean",
        "semantic:date",
        "semantic:datetime",
        "semantic:extension",
        "semantic:decimal",
        "semantic:duration",
        "semantic:integer",
        "semantic:link",
        "semantic:money",
        "semantic:percentage",
        "semantic:text",
        "semantic:time",
    ),
)
_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
