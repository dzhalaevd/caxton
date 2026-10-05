from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from caxton import (  # noqa: WPS347
    Column,
    ColumnSchema,
    Date,
    Money,
    Text,
    compose,
    literal,
    sheet,
    spreadsheet,
    table,
    write,
)
from caxton.core.models import SpreadsheetDocument

ROOT = Path(__file__).parent


class SalesColumns(ColumnSchema):
    """Canonical named order shared by every sales report."""

    date = Column(semantic_type=Date(), source="date", title="Date")
    product = Column(semantic_type=Text(), source="product", title="Product")
    revenue = Column(
        semantic_type=Money(currency="USD"),
        source="revenue",
        title="Revenue",
    )
    channel = Column(
        semantic_type=Text(),
        id="channel",
        source=literal("direct"),
        title="Channel",
    )


def sales_report(
    rows: Iterable[Mapping[str, object]],
    *,
    customer: str,
    table_name: str = "sales",
) -> SpreadsheetDocument:
    """Construct a fresh immutable report from the shared layout and rows.

    Returns:
        An immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows,
                columns=SalesColumns.columns,
                name=table_name,
            ),
        ),
        metadata={"customer": customer},
    )


def combined_sales_report(
    rows: Iterable[Mapping[str, object]],
) -> SpreadsheetDocument:
    """Compose independently reusable regional reports into one workbook.

    Returns:
        An immutable spreadsheet containing both regional sections. The input is
        snapshotted once so generator rows can be reused safely by both sections.
    """
    reusable_rows = tuple(rows)
    return compose(
        {
            "North": sales_report(
                reusable_rows,
                customer="North",
                table_name="north_sales",
            ),
            "South": sales_report(
                reusable_rows,
                customer="South",
                table_name="south_sales",
            ),
        },
        metadata={"customer": "All regions"},
    )


def main() -> None:
    rows = tuple(
        {**row, "date": dt.date.fromisoformat(row["date"])}
        for row in json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    )
    output = ROOT / "output"
    output.mkdir(parents=True, exist_ok=True)
    write(sales_report(rows, customer="North"), output / "north.xlsx")
    write(sales_report(rows, customer="South"), output / "south.xlsx")
    write(combined_sales_report(rows), output / "combined.xlsx")


if __name__ == "__main__":
    main()
