"""Fill the bundled monthly-sales XLSX template through its named data range."""

# ruff: noqa: S101

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

from caxton import (  # noqa: WPS347
    date,
    decimal,
    field,
    integer,
    ref,
    sheet,
    spreadsheet,
    table,
    template,
    text,
    write,
)
from caxton.api import xlsx
from caxton.core.models import SpreadsheetDocument
from caxton.testing import inspect_artifact

ROOT = Path(__file__).parent
SOURCE = ROOT / "assets" / "monthly_sales_template.xlsx"
ROWS = (
    {
        "date": dt.date(2026, 8, 1),
        "product": "Coffee",
        "region": "North",
        "quantity": 4,
        "unit_price": Decimal("12.50"),
    },
    {
        "date": dt.date(2026, 8, 2),
        "product": "Tea",
        "region": "South",
        "quantity": 3,
        "unit_price": Decimal("8.00"),
    },
)


def _configure_print_area(context: xlsx.OpenpyxlHookContext) -> None:
    context.native_sheet.print_area = "A1:F27"


def build_report() -> SpreadsheetDocument:
    """Create immutable template intent without opening the source workbook.

    Returns:
        The reusable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Monthly Report",
            table(
                source=ROWS,
                columns=(
                    date(id="date", source=field("date")),
                    text(id="product", source=field("product")),
                    text(id="region", source=field("region")),
                    integer(id="quantity", source=field("quantity")),
                    decimal(id="unit_price", source=field("unit_price")),
                ),
                into=ref("report_data"),
            ),
        ),
        template=template(
            SOURCE,
            extensions=(
                xlsx.openpyxl_hook(
                    _configure_print_area,
                    sheet="Monthly Report",
                ),
            ),
        ),
    )


def main() -> None:
    """Write and verify a populated copy while leaving the template untouched."""
    target = ROOT / "output" / "monthly_sales_report.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    source_before = SOURCE.read_bytes()
    artifact = inspect_artifact(write(build_report(), target))
    worksheet = artifact.worksheet("Monthly Report")
    assert worksheet.cell("A8").value == dt.datetime(2026, 8, 1)  # noqa: DTZ001
    assert worksheet.cell("F8").formula == '=IF(COUNTA(A8:E8)=0,"",D8*E8)'
    assert SOURCE.read_bytes() == source_before
    print(f"Created {target}")  # noqa: T201, WPS421


if __name__ == "__main__":
    main()
