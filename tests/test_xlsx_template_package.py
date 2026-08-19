from __future__ import annotations

import zipfile
from io import BytesIO

from openpyxl.xml.functions import fromstring

from caxton._internal.backends.openpyxl.package import (  # noqa: PLC2701
    PivotPatch,
    PivotPostProcessor,
    XlsxPackage,
    inspect_pivots,
    run_postprocessors,
)

_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _pivot_package() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/pivotTables/pivotTable1.xml",
            f'<pivotTableDefinition xmlns="{_SHEET_NS}" name="SalesPivot"/>',
        )
        archive.writestr(
            "xl/pivotTables/_rels/pivotTable1.xml.rels",
            (
                f'<Relationships xmlns="{_REL_NS}">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/pivotCacheDefinition" '
                'Target="../pivotCache/pivotCacheDefinition1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/pivotCache/pivotCacheDefinition1.xml",
            (
                f'<pivotCacheDefinition xmlns="{_SHEET_NS}" refreshOnLoad="0">'
                '<cacheSource type="worksheet">'
                '<worksheetSource sheet="Old" ref="A1:B2"/>'
                "</cacheSource>"
                "</pivotCacheDefinition>"
            ),
        )
    return buffer.getvalue()


def test_pivot_postprocessor_uses_resolved_descriptor_and_preserves_parts() -> None:
    source_payload = _pivot_package()
    descriptor = inspect_pivots(source_payload)[0]
    rendered = XlsxPackage.from_bytes(source_payload)
    rendered.write(
        "xl/pivotCache/pivotCacheDefinition1.xml",
        b"<lost-by-roundtrip/>",
    )
    processor = PivotPostProcessor(
        source=XlsxPackage.from_bytes(source_payload),
        patches=(
            PivotPatch(
                descriptor=descriptor,
                sheet="Report",
                cell_range="$A$3:$F$12",
                refresh_on_open=True,
            ),
        ),
    )

    output = run_postprocessors(rendered.to_bytes(), (processor,))

    package = XlsxPackage.from_bytes(output)
    cache_part = descriptor.cache_definition_part
    assert cache_part is not None
    root = fromstring(package.read(cache_part))
    worksheet_source = root.find(f".//{{{_SHEET_NS}}}worksheetSource")
    assert root.get("refreshOnLoad") == "1"
    assert root.get("enableRefresh") == "1"
    assert worksheet_source is not None
    assert worksheet_source.get("sheet") == "Report"
    assert worksheet_source.get("ref") == "A3:F12"
    assert package.read(descriptor.definition_part) == XlsxPackage.from_bytes(
        source_payload,
    ).read(descriptor.definition_part)
