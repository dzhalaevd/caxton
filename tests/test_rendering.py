from __future__ import annotations

import datetime as dt
import decimal as decimal_module
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import pytest

from formata import (  # noqa: WPS347
    FormataError,
    RenderError,
    UnsupportedFeatureError,
    ValidationError,
    boolean,
    date,
    datetime,
    decimal,
    duration,
    field,
    integer,
    link,
    money,
    percentage,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    time,
    write,
)
from formata._internal import operations as operations_module  # noqa: PLC2701
from formata._internal.compiler import spreadsheet as compiler_module  # noqa: PLC2701
from formata._internal.resolver import BuiltinRendererResolver  # noqa: PLC2701
from formata._internal.validation import validate_spreadsheet  # noqa: PLC2701
from formata.core.formatting import money_format
from formata.core.ir import SPREADSHEET_IR_VERSION
from formata.core.models import DocumentKind, SpreadsheetDocument
from formata.core.protocols import OutputSink
from formata.core.rendering import (
    RENDERER_CONTRACT_VERSION,
    RenderContext,
    RendererCapabilities,
    RendererDescriptor,
    RenderResult,
    RequiredCapabilities,
    WorkbookOperation,
)
from formata.testing import ArtifactInspectionError, inspect_artifact

_RENDERER_FEATURES = frozenset(
    (
        "alignment",
        "column_width",
        "display_format",
        "explicit_anchor",
        "native_table",
        "semantic:decimal",
        "semantic:money",
        "semantic:text",
        "table",
    ),
)


class StubRenderer:
    payload: ClassVar[bytes] = b"stub"

    def __init__(
        self,
        name: str = "stub",
        *,
        contract_version: int = RENDERER_CONTRACT_VERSION,
        features: frozenset[str] = _RENDERER_FEATURES,
        ir_versions: frozenset[int] | None = None,
    ) -> None:
        supported_versions = (
            frozenset((SPREADSHEET_IR_VERSION,)) if ir_versions is None else ir_versions
        )
        self.descriptor = RendererDescriptor(
            name=name,
            version="1.0",
            formats=frozenset(("xlsx",)),
            mime_types=frozenset(("application/test",)),
            extensions=frozenset((".xlsx",)),
            capabilities=RendererCapabilities(
                ir_versions={
                    DocumentKind.SPREADSHEET: supported_versions,
                },
                features=features,
            ),
            contract_version=contract_version,
        )

    def render(
        self,
        _document: object,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        written = sink.write(self.payload)
        return RenderResult(
            format=context.format,
            mime_type="application/test",
            renderer=self.descriptor.name,
            bytes_written=written,
        )


class ShortWriter:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> int:
        accepted = max(1, len(data) // 2)
        self.data.extend(data[:accepted])
        return accepted


def _sales_document() -> SpreadsheetDocument:
    return spreadsheet(
        sheet(
            "Sales",
            table(
                [{"gross_value": 90, "cost_value": 30}],
                money("gross", source="gross_value", currency="USD")
                .title("Gross")
                .align("right")
                .width(18)
                .format(money_format(currency="USD")),
                money("cost", source="cost_value"),
                decimal("margin", source=field("gross") - field("cost")),
                name="sales",
                anchor="D10",
            ),
        ),
    )


def test_render_produces_readable_xlsx() -> None:  # noqa: WPS218
    result = render(_sales_document())

    assert result.data is not None
    assert result.data.startswith(b"PK")
    assert result.renderer == "xlsxwriter"
    assert result.format == "xlsx"
    worksheet = inspect_artifact(result).worksheet("Sales")
    assert worksheet.cell("D10").value == "Gross"
    assert worksheet.cell("D10").bold
    assert worksheet.cell("D11").value == 90
    assert worksheet.cell("D11").alignment == "right"
    assert worksheet.cell("D11").number_format == '"USD" #,##0.00'
    assert worksheet.cell("F11").value == 60
    assert worksheet.column("D").width == 18
    assert worksheet.table("sales").cell_range == "D10:F11"
    assert worksheet.table("sales").column_titles == ("Gross", "cost", "margin")
    assert worksheet.table("sales").row_count == 1


def test_result_content_alias() -> None:
    result = render(_sales_document())

    assert result.content == result.data
    assert result.content is not None
    assert result.content.startswith(b"PK")


def test_mime_type_selects_xlsx_renderer() -> None:
    result = render(
        _sales_document(),
        format="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert result.format == "xlsx"
    assert result.renderer == "xlsxwriter"


def test_artifact_selectors_report_missing() -> None:
    artifact = inspect_artifact(render(_sales_document()))
    worksheet = artifact.worksheet("Sales")

    with pytest.raises(LookupError, match="Cell 'A1' was not observed"):
        worksheet.cell("a1")
    with pytest.raises(LookupError, match="Column 'A' was not observed"):
        worksheet.column("a")
    with pytest.raises(LookupError, match="Table 'missing' was not found"):
        worksheet.table("missing")


def test_xlsxwriter_lowers_supported_scalar_types() -> None:
    document = spreadsheet(
        sheet(
            "Values",
            table(
                [
                    {
                        "boolean": True,
                        "date": dt.date(2026, 8, 11),
                        "datetime": dt.datetime(2026, 8, 11, 12, 30),  # noqa: DTZ001
                        "decimal": decimal_module.Decimal("1.25"),
                        "duration": dt.timedelta(hours=27),
                        "integer": 2,
                        "link": "https://example.com",
                        "percentage": 0.25,
                        "time": dt.time(12, 30),
                    },
                ],
                boolean("boolean"),
                date("date"),
                datetime("datetime"),
                decimal("decimal"),
                duration("duration"),
                integer("integer"),
                link("link"),
                percentage("percentage"),
                time("time"),
            ),
        ),
    )

    worksheet = inspect_artifact(render(document)).worksheet("Values")

    formats = tuple(
        worksheet.cell(address).number_format
        for address in ("B2", "C2", "D2", "E2", "H2", "I2")
    )

    assert formats == (
        "yyyy-mm-dd",
        "yyyy-mm-dd hh:mm:ss",
        "0.00",
        "[h]:mm:ss",
        "0.00%",
        "hh:mm:ss",
    )
    assert worksheet.cell("G2").hyperlink == "https://example.com"


def test_artifact_format_conflict_is_rejected() -> None:
    result = render(_sales_document())

    with pytest.raises(ValueError, match="conflicts with source format"):
        inspect_artifact(result, format="pdf")


def test_artifact_accepts_raw_bytes() -> None:
    result = render(_sales_document())

    assert result.data is not None
    assert inspect_artifact(result.data).worksheet("Sales").cell("F11").value == 60


@pytest.mark.parametrize("payload", [b"not xlsx", b"PK\x03\x04truncated"])
def test_invalid_xlsx_has_stable_error(payload: bytes) -> None:
    with pytest.raises(ArtifactInspectionError) as captured:
        inspect_artifact(payload)

    assert captured.value.context == {"format": "xlsx", "source": "bytes"}
    assert captured.value.__cause__ is not None


def test_write_saves_xlsx_to_path(tmp_path: Path) -> None:
    target = tmp_path / "report.xlsx"

    result = write(_sales_document(), target)

    assert result.target == str(target)
    assert result.data is None
    assert result.bytes_written == target.stat().st_size
    assert inspect_artifact(result).worksheet("Sales").cell("F11").value == 60


def test_renderer_preflight_does_not_consume_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"name": "Ada"}

    document = spreadsheet(sheet("People", table(rows(), text("name"))))

    with pytest.raises(RenderError):
        render(document, format="pdf")

    assert not visited


def test_renderer_rejects_incompatible_ir_version() -> None:
    renderer = StubRenderer(ir_versions=frozenset((999,)))

    with pytest.raises(UnsupportedFeatureError, match="lacks required"):
        render(_sales_document(), renderer=renderer)


def test_explicit_custom_renderer_is_selected() -> None:
    renderer = StubRenderer()

    result = render(_sales_document(), renderer=renderer)

    assert result.renderer == "stub"
    assert result.data == StubRenderer.payload


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_explicit_backend_is_selected(backend: str) -> None:
    result = render(_sales_document(), backend=backend)

    assert result.renderer == backend
    assert inspect_artifact(result).worksheet("Sales").table("sales").row_count == 1


def test_incompatible_renderer_contract() -> None:
    renderer = StubRenderer(contract_version=999)

    with pytest.raises(UnsupportedFeatureError, match="contract version"):
        render(_sales_document(), renderer=renderer)


def test_missing_renderer_capabilities() -> None:
    renderer = StubRenderer(features=frozenset())

    with pytest.raises(UnsupportedFeatureError, match="lacks required"):
        render(_sales_document(), renderer=renderer)


def test_write_supports_binary_buffer() -> None:
    target = BytesIO()

    result = write(_sales_document(), target)

    assert result.target is None
    assert result.data == target.getvalue()
    assert result.bytes_written == len(target.getvalue())
    assert inspect_artifact(result).worksheet("Sales").cell("F11").value == 60


def test_write_retries_short_binary_writes() -> None:
    target = ShortWriter()

    result = write(_sales_document(), target)

    assert result.bytes_written == len(target.data)
    assert result.data == bytes(target.data)
    assert inspect_artifact(result).worksheet("Sales").cell("F11").value == 60


def test_artifact_preserves_buffer_position() -> None:
    payload = render(_sales_document()).data
    assert payload is not None
    source = BytesIO(payload)
    source.seek(4)

    assert inspect_artifact(source).worksheet("Sales").cell("F11").value == 60
    assert source.tell() == 4


def test_write_rejects_unsupported_target() -> None:
    with pytest.raises(TypeError, match="Unsupported output target"):
        write(_sales_document(), object())  # type: ignore[arg-type]


def test_ambiguous_renderer_selection_is_rejected() -> None:
    resolver = BuiltinRendererResolver(
        (StubRenderer("first"), StubRenderer("second")),
    )
    required = RequiredCapabilities(
        document_kind=DocumentKind.SPREADSHEET,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
    )

    with pytest.raises(RenderError, match="ambiguous"):
        resolver.select(required, format_name="xlsx")


def test_template_has_no_create_fallback() -> None:
    required = RequiredCapabilities(
        document_kind=DocumentKind.SPREADSHEET,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
        workbook_operation=WorkbookOperation.USE_EXISTING_TEMPLATE,
    )

    with pytest.raises(RenderError, match="No renderer is available"):
        BuiltinRendererResolver().select(required, format_name="xlsx")


def test_create_renderer_rejects_template() -> None:
    required = RequiredCapabilities(
        document_kind=DocumentKind.SPREADSHEET,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
        workbook_operation=WorkbookOperation.USE_EXISTING_TEMPLATE,
    )

    with pytest.raises(UnsupportedFeatureError, match="lacks required"):
        BuiltinRendererResolver((StubRenderer(),)).select(
            required,
            format_name="xlsx",
        )


def test_write_rejects_name_collision_early(
    tmp_path: Path,
) -> None:
    document = spreadsheet(
        sheet("First", table([{"value": 1}], text("value"), name="Sales")),
        sheet("Second", table([{"value": 2}], text("value"), name="sales")),
    )
    target = tmp_path / "existing.xlsx"
    original = b"existing artifact"
    target.write_bytes(original)

    with pytest.raises(ValidationError):
        write(document, target)

    assert target.read_bytes() == original


def test_render_validates_structure_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def recording_validation(document: SpreadsheetDocument) -> None:
        nonlocal calls
        calls += 1
        validate_spreadsheet(document)

    monkeypatch.setattr(
        operations_module,
        "validate_spreadsheet",
        recording_validation,
    )
    monkeypatch.setattr(
        compiler_module,
        "validate_spreadsheet",
        recording_validation,
    )

    render(_sales_document())

    assert calls == 1


def test_construction_uses_formata_errors() -> None:
    with pytest.raises(FormataError):
        text("name").width(0)
    with pytest.raises(FormataError):
        text("name").align("diagonal")
    with pytest.raises(FormataError):
        spreadsheet(metadata={"unsupported": object()})
