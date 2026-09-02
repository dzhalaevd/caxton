from caxton import (
    AutoWidth,
    CorporateTheme,
    Freeze,
    Style,
    StyleSheet,
    Total,
    Totals,
    col,
    decimal,
    field,
    sheet,
    spreadsheet,
    table,
    when,
)

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
    theme=CorporateTheme(
        font="Arial",
        header_fill="#004B8D",
        header_font_color="#FFFFFF",
    ),
)
