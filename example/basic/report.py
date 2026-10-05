from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path

from caxton import (  # noqa: WPS347
    ColumnSchema,
    money,
    ref,
    sheet,
    spreadsheet,
    table,
    text,
    write,
)
from caxton.core.formatting import money_format
from caxton.core.models import SpreadsheetDocument

ROOT = Path(__file__).parent
DATA = json.loads(
    (ROOT / "data.json").read_text(encoding="utf-8"),
    parse_float=Decimal,
)
SALES = tuple(DATA["sales"])
OWNERS = tuple(DATA["owners"])

RUB_FORMAT = money_format(currency="RUB")


class SalesColumns(ColumnSchema):
    product = text(
        source="product",
        title="Product",
    ).width(18)
    revenue = money(
        source="revenue",
        title="Revenue",
        currency="RUB",
    ).format(RUB_FORMAT)
    cost = money(
        source="cost",
        title="Cost",
        currency="RUB",
    ).format(RUB_FORMAT)
    profit = money(
        id="profit",
        source=ref("revenue") - ref("cost"),
        title="Profit",
        currency="RUB",
    ).format(RUB_FORMAT)


class OwnerColumns(ColumnSchema):
    team = text(
        source="team",
        title="Team",
    )
    owner = text(
        source="owner",
        title="Owner",
    )


def build_report(rows: Iterable[Mapping[str, object]]) -> SpreadsheetDocument:
    return spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows,
                columns=SalesColumns.columns,
                name="sales",
                anchor="A3",
            ),
        ),
        sheet(
            "Owners",
            table(
                source=OWNERS,
                columns=OwnerColumns.columns,
                name="owners",
            ),
        ),
        metadata={"example": "basic"},
    )


def main() -> None:
    """Run the complete example and write its final artifact."""
    document = build_report(SALES)
    output = ROOT / "output" / "basic_report.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    write(document, output)


if __name__ == "__main__":
    main()
