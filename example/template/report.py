"""Fill an existing monthly-sales workbook and return a new XLSX.

The intended flow opens ``assets/monthly_sales_template.xlsx``, resolves the
named data anchor, repeats the styled template row for every sale, and preserves
the workbook's formulas, chart and pivot-related package parts. After lowering,
the XLSX backend updates the pivot source, marks it for refresh, applies scoped
package post-processing and writes ``output/monthly_sales_report.xlsx`` without
mutating the source template. A namespaced OpenPyXL hook may configure the print
area, but no backend-native object enters the semantic model.

This remains documentation-only until Formata exposes template inspection,
named anchors, row repetition, pivot binding and backend extension contracts.
"""
