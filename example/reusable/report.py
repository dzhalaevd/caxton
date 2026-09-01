"""Reuse one report factory with different row sets until source_ref/bind exists."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from pathlib import Path

from caxton import (  # noqa: WPS347
    date,
    field,
    money,
    sheet,
    spreadsheet,
    table,
    text,
    write,
)
from caxton.core.models import SpreadsheetDocument


def sales_report(
    rows: Iterable[Mapping[str, object]],
    *,
    customer: str,
) -> SpreadsheetDocument:
    """Bind rows by constructing a fresh immutable graph from one layout.

    Returns:
        An immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows,
                columns=(
                    date(
                        id="date",
                        source=field("date"),
                        title="Date",
                    ),
                    text(
                        id="product",
                        source=field("product"),
                        title="Product",
                    ),
                    money(
                        id="revenue",
                        source=field("revenue"),
                        title="Revenue",
                        currency="USD",
                    ),
                ),
                name="sales",
            ),
        ),
        metadata={"customer": customer},
    )


def main() -> None:
    """Render two documents without mutating or copying a shared model."""
    rows = (
        {
            "date": dt.date(2026, 8, 11),
            "product": "Coffee",
            "revenue": 1200,
        },
    )
    output = Path(__file__).with_name("output")
    output.mkdir(parents=True, exist_ok=True)
    write(sales_report(rows, customer="North"), output / "north.xlsx")
    write(sales_report(rows, customer="South"), output / "south.xlsx")
    print(f"Created reports in {output}")  # noqa: T201, WPS421


if __name__ == "__main__":
    main()
