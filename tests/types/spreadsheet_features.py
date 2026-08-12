from formata import (
    CorporateTheme,
    Freeze,
    Style,
    StyleSheet,
    Total,
    Totals,
    col,
    decimal,
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
            [{"amount": 1}],
            decimal("amount", style="number").width("auto"),
            footer=Totals(items=(Total("amount"),)),
            rules=(when(col("amount") > 0, style="number"),),
            autofilter=True,
            freeze_header=True,
            auto_width=True,
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
