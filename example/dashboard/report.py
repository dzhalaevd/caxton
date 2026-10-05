import base64
import json
from pathlib import Path

from caxton import (  # noqa: WPS347
    ColumnSchema,
    Style,
    StyleSheet,
    chart,
    decimal,
    image,
    sheet,
    spacer,
    spreadsheet,
    stack,
    table,
    table_ref,
    text,
    title,
    write,
)
from caxton.core.models import SpreadsheetDocument

ROOT = Path(__file__).parent
ROWS = tuple(
    json.loads((ROOT / "data.json").read_text(encoding="utf-8")),
)

LOGO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFElEQVR4nGP8"
    "z8DwnwEJMKEL0FYAAG3fAxAqNQyzAAAAAElFTkSuQmCC",
)


class SalesColumns(ColumnSchema):
    """Columns used by the dashboard's sales table."""

    day = text(
        source="day",
        title="Day",
    )
    revenue = decimal(
        source="revenue",
        title="Revenue",
        style="number",
    )


def build_report() -> SpreadsheetDocument:
    """Compose a worksheet from blocks using compiler-resolved placement.

    Returns:
        A reusable immutable spreadsheet specification.
    """
    sales = table(
        source=ROWS,
        columns=SalesColumns.columns,
        name="sales",
    )
    return spreadsheet(
        sheet(
            "Dashboard",
            title("Daily revenue", span=2),
            spacer(),
            sales,
            spacer(rows=2),
            stack(
                chart(
                    table_ref("sales"),
                    x="day",
                    y="revenue",
                    kind="column",
                    title="Revenue by day",
                ),
                image(LOGO, width=128, height=64, name="logo"),
                gap=1,
            ),
        ),
        styles=StyleSheet({"number": Style(align="right")}),
    )


def main() -> None:
    """Render the dashboard and verify the positions the compiler resolved."""
    target = ROOT / "output" / "dashboard.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    document = build_report()
    write(document, target)


if __name__ == "__main__":
    main()
