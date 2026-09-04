from typing import Literal

from typing_extensions import assert_type

from caxton import (
    AutoWidth,
    DocumentTheme,
    FontStyle,
    Freeze,
    Style,
    StyleSheet,
    Total,
    Totals,
    col,
    date_format,
    decimal,
    field,
    sheet,
    spreadsheet,
    table,
    time_format,
    when,
)

assert_type(date_format().variant, Literal["iso", "short", "long"])
assert_type(time_format().clock, Literal[12, 24])

styles = StyleSheet({"number": Style(fill="#D9EAF7")})
document = spreadsheet(
    sheet(
        "Data",
        table(
            source=[{"amount": 1}],
            columns=(
                decimal(
                    id="amount",
                    source=field("amount"),
                    style="number",
                ).width(AutoWidth(minimum=10, maximum=30)),
            ),
            footer=Totals(items=(Total("amount"),)),
            rules=(when(col("amount") > 0, style="number"),),
            autofilter=True,
            freeze_header=True,
            auto_width=AutoWidth(minimum=15),
        ),
        freeze=Freeze(rows=0, columns=1),
    ),
    styles=styles,
    theme=DocumentTheme(
        default=Style(font=FontStyle(name="Arial")),
        header=Style(
            font=FontStyle(name="Arial", bold=True, color="#FFFFFF"),
            fill="#004B8D",
        ),
        total=Style(font=FontStyle(name="Arial", bold=True)),
    ),
)
