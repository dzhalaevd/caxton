from typing_extensions import assert_type

from caxton import (
    TemplateRepeat,
    TemplateSpecification,
    repeat,
    slot,
    template,
)
from caxton.api import xlsx

specification = template("report.xlsx")
repetition = repeat(slot("report_row"))
hook = xlsx.openpyxl_hook(lambda _context: None, sheet="Report")
pivot = xlsx.pivot("SalesPivot", source=slot("report_data"))

assert_type(specification, TemplateSpecification)
assert_type(repetition, TemplateRepeat)
assert_type(hook, xlsx.OpenpyxlHookExtension)
assert_type(pivot, xlsx.PivotBinding)
