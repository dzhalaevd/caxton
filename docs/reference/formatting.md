# `caxton.core.formatting`

Backend-neutral presentation vocabulary. Formatting is stored separately from
value semantics: the renderer chooses the physical representation and reports a
capability diagnostic when it cannot preserve the intent.

## Styles

::: caxton.core.formatting
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — Style
        - StyleSheet
        - FontStyle
        - FillStyle
        - Borders
        - BorderLine
        - BorderLineStyle
        - CellAlignment
        - Alignment
        - VerticalAlignment

## Themes

::: caxton.core.formatting
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — DocumentTheme
        - CorporateTheme

## Display formats

::: caxton.core.formatting
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        — decimal_format
        - money_format
        - percentage_format
        - date_format
        - time_format
        - custom_format
        - DecimalFormat
        - MoneyFormat
        - PercentageFormat
        - DateFormat
        - TimeFormat
        - CustomFormat
