from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from caxton import (  # noqa: WPS347
    ColumnSchema,
    date,
    decimal,
    integer,
    sheet,
    slot,
    spreadsheet,
    table,
    template,
    text,
    write,
)
from caxton.api import xlsx
from caxton.core.models import SpreadsheetDocument

ROOT = Path(__file__).parent
SOURCE = ROOT / "assets" / "workspace_rates_template.xlsx"

rows = json.loads(
    (ROOT / "data.json").read_text(encoding="utf-8"),
    parse_float=Decimal,
)
ROWS = tuple({**row, "day": dt.date.fromisoformat(row["day"])} for row in rows)


class RateColumns(ColumnSchema):
    """Columns written into the template's summary range."""

    location = text(source="location")
    space_id = text(source="space_id")
    offer_code = text(source="offer_code")
    space_type = text(source="space_type")
    rate_model = text(source="rate_model")
    rate = decimal(source="rate")
    day = date(source="day")
    hour = integer(source="hour")
    variance = decimal(source="variance")
    base_rate = decimal(source="base_rate")


def _configure_print_area(context: xlsx.OpenpyxlHookContext) -> None:
    context.native_sheet.print_area = "A1:J27"
    context.native_sheet.page_setup.orientation = "landscape"
    context.native_sheet.page_setup.fitToWidth = 1
    context.native_sheet.page_setup.fitToHeight = 0
    context.native_sheet.sheet_properties.pageSetUpPr.fitToPage = True


def build_report() -> SpreadsheetDocument:
    """Create immutable template intent without opening the source workbook.

    Returns:
        The reusable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Summary",
            table(
                source=ROWS,
                columns=RateColumns.columns,
                into=slot("report_data"),
            ),
        ),
        template=template(
            SOURCE,
            extensions=(
                xlsx.openpyxl_hook(
                    _configure_print_area,
                    sheet="Summary",
                ),
            ),
        ),
    )


def main() -> None:
    """Write a populated copy while leaving the template untouched."""
    target = ROOT / "output" / "workspace_rates_report.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    write(build_report(), target)


if __name__ == "__main__":
    main()
