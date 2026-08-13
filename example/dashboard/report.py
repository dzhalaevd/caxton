import base64
from pathlib import Path

from caxton import (
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
    write as write_spreadsheet,
)
from caxton.core.models import SpreadsheetDocument
from caxton.testing import inspect_artifact, inspect_layout

LOGO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFElEQVR4nGP8"
    "z8DwnwEJMKEL0FYAAG3fAxAqNQyzAAAAAElFTkSuQmCC",
)


def build_report() -> SpreadsheetDocument:
    """Compose one worksheet from blocks without any manual row arithmetic.

    Returns:
        A reusable immutable spreadsheet specification.
    """
    sales = table(
        [
            {"day": "2026-08-10", "revenue": 1200},
            {"day": "2026-08-11", "revenue": 1580},
            {"day": "2026-08-12", "revenue": 1410},
        ],
        text("day").titled("Day"),
        decimal("revenue", style="number").titled("Revenue"),
        name="sales",
    )
    return spreadsheet(
        sheet(
            "Dashboard",
            title("Daily revenue", span=2),
            spacer(rows=1),
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


def main() -> None:  # noqa: WPS218
    """Render the dashboard and verify the positions the compiler resolved."""
    target = Path(__file__).parent / "output" / "dashboard.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    document = build_report()

    worksheet = inspect_layout(document).worksheet("Dashboard")
    assert worksheet.block("block[0]").cell_range == "A1:B1"  # noqa: S101
    assert worksheet.table("sales").anchor == "A3"  # noqa: S101
    assert worksheet.charts[0].anchor == "A9"  # noqa: S101
    assert worksheet.charts[0].series[0].values == "B4:B6"  # noqa: S101
    assert worksheet.images[0].anchor == "A25"  # noqa: S101

    artifact = inspect_artifact(write_spreadsheet(document, target))
    dashboard = artifact.worksheet("Dashboard")
    assert dashboard.cell("A1").value == "Daily revenue"  # noqa: S101
    assert dashboard.cell("A3").value == "Day"  # noqa: S101
    assert "A1:B1" in dashboard.merged_ranges  # noqa: S101


if __name__ == "__main__":
    main()
