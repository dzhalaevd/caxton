# Caxton

[![CI][ci-shield]][ci-url]
[![Codecov][codecov-shield]][codecov-url]
[![PyPI version][pypi-shield]][pypi-url]
[![Python versions][python-shield]][pypi-url]
[![License: MIT][license-shield]][license-url]

---

Caxton is a typed, declarative Python library for building spreadsheet
documents from application data and rendering them to XLSX. Users define the
document structure and semantics; Caxton handles layout, compilation, and
backend-specific output.

> [!WARNING]
> Caxton is pre-alpha and is not ready for production use. The public DSL may
> change until `1.0.0`.

[📚 Documentation](https://dzhalaevd.github.io/caxton/)\
[📑 Changelog](https://github.com/dzhalaevd/caxton/blob/main/CHANGELOG.md)

```python
from caxton import render, sheet, spreadsheet, table, text, write

rows = [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}]

report = spreadsheet(
    sheet(
        "People",
        table(
            source=rows,
            columns=(text(source="name", title="Name"),),
        ),
    ),
)

result = render(report)

write(report, "people.xlsx")
```

More examples are available in the
[example projects](https://github.com/dzhalaevd/caxton/tree/main/example).

The project is licensed under the
[MIT License](https://github.com/dzhalaevd/caxton/blob/main/LICENSE).

## Installation

Caxton requires Python 3.10 or newer. Install it with pip:

```bash
pip install caxton
```

No additional setup is required

<div align="center">

### Works on Open-Source

If you find this project interesting, consider giving it a ⭐

</div>

[ci-shield]: https://github.com/dzhalaevd/caxton/actions/workflows/ci.yml/badge.svg

[ci-url]: https://github.com/dzhalaevd/caxton/actions/workflows/ci.yml

[codecov-shield]: https://codecov.io/gh/dzhalaevd/caxton/graph/badge.svg

[codecov-url]: https://codecov.io/gh/dzhalaevd/caxton

[pypi-shield]: https://img.shields.io/pypi/v/caxton.svg

[pypi-url]: https://pypi.org/project/caxton/

[python-shield]: https://img.shields.io/pypi/pyversions/caxton.svg

[license-shield]: https://img.shields.io/badge/License-MIT-yellow.svg

[license-url]: https://github.com/dzhalaevd/caxton/blob/main/LICENSE
