from __future__ import annotations

from collections.abc import Mapping

from typing_extensions import assert_type

from caxton import (
    DocumentTheme,
    SpreadsheetDocument,
    Style,
    StyleSheet,
    TemplateSpecification,
    Worksheet,
    compose,
    sheet,
    spreadsheet,
)

document = spreadsheet(sheet("Summary"))
sections: Mapping[str, SpreadsheetDocument] = {"Parameters": document}
metadata: Mapping[str, object] = {"owner": "security"}
styles: Mapping[str, Style] = {"heading": Style(fill="#D9EAF7")}
theme = DocumentTheme(default=Style(fill="#FFFFFF"))
template = TemplateSpecification(source="report.xlsx", format="xlsx")

assert_type(
    compose(
        sections,
        metadata=metadata,
        styles=styles,
        theme=theme,
        template=template,
    ),
    SpreadsheetDocument,
)
assert_type(compose(sections, styles=StyleSheet(styles)), SpreadsheetDocument)

worksheet: Worksheet = sheet("Wrong level")
optional_document: SpreadsheetDocument | None = document

compose({"Section": worksheet})  # type: ignore[dict-item]
compose({"Section": optional_document})  # type: ignore[dict-item]
compose({1: document})  # type: ignore[dict-item]
