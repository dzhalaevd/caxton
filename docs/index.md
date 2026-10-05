# Caxton

**Declarative document generation for Python.**

Caxton lets you describe what a document contains and what its values mean. The compiler and selected renderer decide
where everything goes and how to represent it in the target format.

!!! warning "Pre-alpha"

    Caxton is under active development and is not ready for production use. The
    delivered surface is the spreadsheet document family rendered to XLSX; see
    [Architecture](https://github.com/dzhalaevd/caxton/blob/main/ARCHITECTURE.md) for the exact boundary.

## Compare the APIs

Each example builds the same small sales report. XlsxWriter and OpenPyXL work with cells and number formats. Caxton
describes a table, its columns, and what their values mean.

=== "xlsxwriter"

    ```python
    import xlsxwriter

    workbook = xlsxwriter.Workbook("report.xlsx")
    worksheet = workbook.add_worksheet("Sales")
    money = workbook.add_format({"num_format": '"RUB" #,##0.00'})

    sales = [
        ("Book", 1200, 2),
        ("Pen", 150, 10),
    ]

    worksheet.set_column("B:B", 12, money)
    worksheet.set_column("D:D", 12, money)
    worksheet.write_row("A1", ("Product", "Price", "Quantity", "Total"))

    for row, (product, price, quantity) in enumerate(sales, start=1):
        worksheet.write_row(row, 0, (product, price, quantity, price * quantity))

    workbook.close()
    ```

=== "openpyxl"

    ```python
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sales"

    sales = [
        ("Book", 1200, 2),
        ("Pen", 150, 10),
    ]

    worksheet.append(("Product", "Price", "Quantity", "Total"))
    for product, price, quantity in sales:
        worksheet.append((product, price, quantity, price * quantity))

    for row in worksheet.iter_rows(min_row=2):
        row[1].number_format = '"RUB" #,##0.00'
        row[3].number_format = '"RUB" #,##0.00'

    workbook.save("report.xlsx")
    ```

=== "caxton"

    ```python
    from caxton import integer, money, ref, sheet, spreadsheet, table, text, write

    sales = [
        {"product": "Book", "price": 1200, "quantity": 2},
        {"product": "Pen", "price": 150, "quantity": 10},
    ]

    columns = (
        text(source="product", title="Product"),
        money(source="price", title="Price", currency="RUB"),
        integer(source="quantity", title="Quantity"),
        money(
            id="total",
            source=ref("price") * ref("quantity"),
            title="Total",
            currency="RUB",
        ),
    )

    report = spreadsheet(sheet("Sales", table(source=sales, columns=columns)))
    write(report, "report.xlsx")
    ```

The Caxton specification does not assign cell addresses or construct backend-specific number formats. It describes the
columns once and leaves placement and XLSX representation to the selected renderer.

## What you get

<div class="grid cards" markdown>

-   __Semantic columns__

    Columns carry semantic types `money`, `percentage`, `date`, `duration` instead of number formats. The renderer
    chooses the representation.

-   __Immutable specifications__

    Public semantic-node factories return frozen nodes. Each fluent method returns a new one. A report factory can
    therefore be reused for different row sets without copying or mutation.

-   __Lazy data__

    Building and validating a document never reads a row. One-shot sources are tracked and a hidden second pass is
    rejected instead of silently producing an empty table.

-   __Testing tools__

    [`caxton.testing`](reference/testing.md) inspects intent, compiled layout, and the finished artifact — without
    exposing OpenPyXL or XlsxWriter objects.

</div>
