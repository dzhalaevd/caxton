"""Build and verify a small multi-sheet XLSX report with the current public API."""

# ruff: noqa: S101

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from caxton import (  # noqa: WPS347
    money,
    ref,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    validate,
    write,
)
from caxton.core.formatting import money_format
from caxton.core.models import Column, SpreadsheetDocument
from caxton.testing import Rows, inspect_artifact, inspect_layout, inspect_spec

SALES = (
    {"product": "Coffee", "revenue": Decimal(1250), "cost": Decimal(700)},
    {"product": "Tea", "revenue": Decimal(920), "cost": Decimal(510)},
)


def sales_columns(*, include_profit: bool = True) -> tuple[Column, ...]:
    """Compose columns dynamically while preserving semantic identities.

    Returns:
        The columns selected for the report.
    """
    columns = (
        text("product").titled("Product").width(18),
        money("revenue", currency="RUB")
        .titled("Revenue")
        .format(money_format(currency="RUB")),
        money("cost", currency="RUB")
        .titled("Cost")
        .format(money_format(currency="RUB")),
    )
    if not include_profit:
        return columns
    profit = money(
        "profit",
        source=ref("revenue") - ref("cost"),
        currency="RUB",
    ).titled("Profit")
    return *columns, profit.format(money_format(currency="RUB"))


def build_report(rows: Iterable[Mapping[str, object]]) -> SpreadsheetDocument:
    """Create one report containing a detail and a reference worksheet.

    Returns:
        An immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Sales",
            table(
                rows,
                *sales_columns(),
                name="sales",
                anchor="A3",
            ),
        ),
        sheet(
            "Owners",
            table(
                ({"team": "Retail", "owner": "Ada"},),
                text("team").titled("Team"),
                text("owner").titled("Owner"),
                name="owners",
            ),
        ),
        metadata={"example": "basic"},
    )


def verify_report(document: SpreadsheetDocument) -> None:  # noqa: WPS218
    """Exercise semantic, layout, memory, buffer and artifact boundaries."""
    validate(document)

    spec = inspect_spec(document)
    sales_spec = spec.worksheet("Sales").table("sales")
    assert sales_spec.column_ids == ("product", "revenue", "cost", "profit")

    layout = inspect_layout(document, rows=Rows.sample(1))
    sales_layout = layout.worksheet("Sales").table("sales")
    assert sales_layout.anchor == "A3"
    assert sales_layout.row(0)["profit"] == Decimal(550)

    rendered = render(document)
    assert rendered.data is not None
    assert rendered.renderer == "xlsxwriter"

    artifact = inspect_artifact(rendered)
    sales_artifact = artifact.worksheet("Sales").table("sales")
    assert sales_artifact.column_titles == ("Product", "Revenue", "Cost", "Profit")
    assert artifact.worksheet("Sales").cell("D4").value == 550

    buffer = BytesIO()
    buffered = write(document, buffer, format="xlsx")
    assert buffered.data == buffer.getvalue()


def main() -> None:
    """Run the complete example and write its final artifact."""
    document = build_report(SALES)
    verify_report(document)
    output = Path(__file__).with_name("output") / "basic_report.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    write(document, output)
    print(f"Created {output}")  # noqa: T201, WPS421


if __name__ == "__main__":
    main()
