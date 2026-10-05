import json
from pathlib import Path

from caxton import (  # noqa: WPS347
    AutoWidth,
    ColumnSchema,
    DocumentTheme,
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
    write,
)
from caxton.core.models import Matrix, SpreadsheetDocument, SpreadsheetTable

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
sales_rows = tuple(DATA["sales"])
orders = tuple(DATA["orders"])

DEFAULT_DOC_THEME = DocumentTheme(
    default=Style(font=FontStyle(name="Arial")),
    header=Style(
        font=FontStyle(name="Arial", bold=True, color="#FFFFFF"),
        fill="#004B8D",
    ),
    total=Style(font=FontStyle(name="Arial", bold=True)),
)

DOC_STYLE = StyleSheet(
    {
        "number": Style(display_format=decimal_format(grouping=True)),
        "positive": Style(fill="#C6EFCE", font_color="#006100"),
    },
)

TABLE_HEADER_STYLE = Style(font=FontStyle(bold=True), fill="#D9EAF7")

SALES_HEADER_STYLE = Style(
    font=FontStyle(bold=True),
    fill="#D9EAF7",
    align="center",
    border_bottom="thin",
)


class SalesColumns(ColumnSchema):
    """Columns for the sales table."""

    price = decimal(
        source="price",
        title="Price",
        style="number",
    ).width("auto")
    base_price = decimal(
        source="base_price",
        title="Base price",
        style="number",
    )
    delta = decimal(
        id="delta",
        formula=col("price") - col("base_price").absolute(row=False),
        title="Delta",
    )


class SummaryColumns(ColumnSchema):
    """Columns containing references to the sales table."""

    first_price = decimal(
        id="first_price",
        title="First price",
        formula=(sheet_ref("Sales").table("sales").column("price").cell(0).absolute()),
    )
    all_prices = decimal(
        id="all_prices",
        title="Named range",
        formula=table_ref("sales").column("price"),
    )


class OrderColumns(ColumnSchema):
    """Grouped order columns and aggregate values."""

    region = text(
        source="region",
        title="Region",
    ).grouped(merge=True)
    product = text(
        source="product",
        title="Product",
    ).grouped()
    fulfilled_units = decimal(
        id="fulfilled_units",
        title="Fulfilled units",
        source=field("units").agg(
            sum,
            where=field("fulfilled"),
            default=0,
        ),
        style="number",
    )


def _sales_table() -> SpreadsheetTable:
    return table(
        source=sales_rows,
        columns=SalesColumns.columns,
        name="sales",
        header_style=SALES_HEADER_STYLE,
        footer=Totals(items=(Total("price"), Total("delta"))),
        rules=(when(col("delta") > 0, style="positive"),),
        autofilter=True,
        freeze_header=True,
        auto_width=AutoWidth(minimum=12, maximum=40),
    )


def _summary_table() -> SpreadsheetTable:
    return table(
        source=[{}],
        columns=SummaryColumns.columns,
        name="summary",
    )


def _grouped_orders_table() -> SpreadsheetTable:
    return table(
        source=orders,
        columns=OrderColumns.columns,
        header_style=TABLE_HEADER_STYLE,
    )


def _monthly_units_matrix() -> Matrix:
    return matrix(
        source=orders,
        row="region",
        column="month",
        value=decimal(
            id="units_total",
            source=field("units").agg(sum),
            style="number",
        ),
        header_style=TABLE_HEADER_STYLE,
    )


def build_report() -> SpreadsheetDocument:
    """Build the advanced report with formulas, grouping, and a matrix.

    Returns:
        A reusable immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet("Sales", _sales_table(), freeze=Freeze(rows=0, columns=1)),
        sheet("Summary", _summary_table()),
        sheet("Grouped Orders", _grouped_orders_table()),
        sheet("Monthly Units", _monthly_units_matrix()),
        styles=DOC_STYLE,
        theme=DEFAULT_DOC_THEME,
    )


def main() -> None:
    """Render the advanced retail report as an XLSX artifact."""
    target = ROOT / "output" / "advanced.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    write(build_report(), target)


if __name__ == "__main__":
    main()
