from pathlib import Path

from caxton import (
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
    field,
    matrix,
    sheet,
    sheet_ref,
    spreadsheet,
    table,
    table_ref,
    text,
    when,
    write as write_spreadsheet,
)
from caxton.core.models import SpreadsheetDocument
from caxton.testing import inspect_artifact


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
    production = (
        {
            "shop": "A",
            "field": "X",
            "month": "Jan",
            "oil_rate": 10,
            "active": True,
        },
        {
            "shop": "A",
            "field": "X",
            "month": "Feb",
            "oil_rate": 12,
            "active": True,
        },
        {
            "shop": "A",
            "field": "Y",
            "month": "Jan",
            "oil_rate": 7,
            "active": False,
        },
        {
            "shop": "B",
            "field": "Z",
            "month": "Jan",
            "oil_rate": 8,
            "active": True,
        },
    )
    grouped = table(
        production,
        text("shop").titled("Shop").grouped(merge=True),
        text("field").titled("Field").grouped(),
        decimal(
            "active_oil",
            source=field("oil_rate").agg(
                sum,
                where=field("active"),
                default=0,
            ),
            style="number",
        ).titled("Active oil"),
        header_style=Style(font=FontStyle(bold=True), fill="#D9EAF7"),
    )
    production_matrix = matrix(
        production,
        row=field("shop"),
        column=field("month"),
        value=decimal(
            "oil_total",
            source=field("oil_rate").agg(sum),
            style="number",
        ),
        header_style=Style(font=FontStyle(bold=True), fill="#D9EAF7"),
    )
    return spreadsheet(
        sheet("Sales", sales, freeze=Freeze(rows=0, columns=1)),
        sheet("Summary", summary),
        sheet("Grouped", grouped),
        sheet("Matrix", production_matrix),
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


def main() -> None:  # noqa: WPS213, WPS218
    """Render the implemented slice and verify formulas in the XLSX artifact."""
    target = Path(__file__).parent / "output" / "advanced.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = inspect_artifact(write_spreadsheet(build_report(), target))
    _require(
        artifact.worksheet("Sales").cell("C2").formula == "=A2-$B2",
        "Sales formula was not rendered",
    )
    sales = artifact.worksheet("Sales")
    _require(sales.freeze_panes == "B2", "Freeze pane was not rendered")
    _require(sales.cell("B4").value == "Total", "Total label was not rendered")
    _require(
        sales.cell("C4").formula == "=SUM(C2:C3)",
        "Total formula was not rendered",
    )
    summary = artifact.worksheet("Summary")
    _require(
        summary.cell("A2").formula == "='Sales'!$A$2",
        "Cross-sheet formula was not rendered",
    )
    _require(
        summary.cell("B2").formula == "=sales[Price]",
        "Structured reference was not rendered",
    )
    grouped = artifact.worksheet("Grouped")
    _require(grouped.merged_ranges == ("A2:A3",), "Group merge was not rendered")
    _require(grouped.cell("C2").value == 22, "Group aggregate is incorrect")
    _require(grouped.cell("C3").value == 0, "Empty aggregate default is incorrect")
    production_matrix = artifact.worksheet("Matrix")
    _require(production_matrix.cell("B1").value == "Jan", "Jan header is missing")
    _require(production_matrix.cell("C1").value == "Feb", "Feb header is missing")
    _require(production_matrix.cell("B2").value == 17, "Jan matrix value is wrong")
    _require(production_matrix.cell("C2").value == 12, "Feb matrix value is wrong")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


if __name__ == "__main__":
    main()
