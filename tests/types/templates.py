from typing_extensions import assert_type

from caxton import (
    TemplateRepeat,
    TemplateSpecification,
    ref,
    repeat,
    template,
)
from caxton.api import xlsx

specification = template("report.xlsx")
repetition = repeat(ref("report_row"))
hook = xlsx.openpyxl_hook(lambda _context: None, sheet="Report")
pivot = xlsx.pivot("SalesPivot", source=ref("report_data"))

assert_type(specification, TemplateSpecification)
assert_type(repetition, TemplateRepeat)
assert_type(hook, xlsx.OpenpyxlHookExtension)
assert_type(pivot, xlsx.PivotBinding)
