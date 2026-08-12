from pathlib import Path

from formata import (
    CorporateTheme,
    FontStyle,
    Freeze,
    Style,
    StyleSheet,
    Total,
    Totals,
    col,
    decimal,
    decimal_format,
    sheet,
    sheet_ref,
    spreadsheet,
    table,
    table_ref,
    when,
    write as write_spreadsheet,
)
from formata.core.models import SpreadsheetDocument
from formata.testing import inspect_artifact


def build_report() -> SpreadsheetDocument:
    """Create the working formula/reference part of the advanced flow.

    Returns:
        A reusable immutable spreadsheet specification.
    """
    sales = table(
        [
            {"price": 10, "base_price": 8},
            {"price": 15, "base_price": 12},
        ],
        decimal("price", style="number").titled("Price").width("auto"),
        decimal("base_price", style="number").titled("Base price"),
        decimal("delta")
        .titled("Delta")
        .formula(
            col("price") - col("base_price").absolute(row=False),
        ),
        name="sales",
        header_style=Style(
            font=FontStyle(bold=True),
            fill="#D9EAF7",
            align="center",
            border_bottom="thin",
        ),
        footer=Totals(items=(Total("price"), Total("delta"))),
        rules=(when(col("delta") > 0, style="positive"),),
        autofilter=True,
        freeze_header=True,
        auto_width=True,
    )
    summary = table(
        [{}],
        decimal(
            "first_price",
            formula=(
                sheet_ref("Sales").table("sales").column("price").cell(0).absolute()
            ),
        ).titled("First price"),
        decimal(
            "all_prices",
            formula=table_ref("sales").column("price"),
        ).titled("Named range"),
        name="summary",
    )
    return spreadsheet(
        sheet("Sales", sales, freeze=Freeze(rows=0, columns=1)),
        sheet("Summary", summary),
        styles=StyleSheet(
            {
                "number": Style(display_format=decimal_format(grouping=True)),
                "positive": Style(fill="#C6EFCE", font_color="#006100"),
            },
        ),
        theme=CorporateTheme(
            font="Arial",
            header_fill="#004B8D",
            header_font_color="#FFFFFF",
        ),
    )


def main() -> None:  # noqa: WPS218
    """Render the implemented slice and verify formulas in the XLSX artifact."""
    target = Path(__file__).parent / "output" / "advanced.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = inspect_artifact(write_spreadsheet(build_report(), target))
    assert artifact.worksheet("Sales").cell("C2").formula == "=A2-$B2"  # noqa: S101
    sales = artifact.worksheet("Sales")
    assert sales.freeze_panes == "B2"  # noqa: S101
    assert sales.cell("B4").value == "Total"  # noqa: S101
    assert sales.cell("C4").formula == "=SUM(C2:C3)"  # noqa: S101
    summary = artifact.worksheet("Summary")
    assert summary.cell("A2").formula == "='Sales'!$A$2"  # noqa: S101
    assert summary.cell("B2").formula == "=sales[Price]"  # noqa: S101


if __name__ == "__main__":
    main()


# Title, spacer, image and chart blocks are covered by example/dashboard.
# Grouping and matrix layout remain deferred to stage 5.
