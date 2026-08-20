# Caxton

[![CI][ci-shield]][ci-url]
[![Codecov][codecov-shield]][codecov-url]
[![PyPI version][pypi-shield]][pypi-url]
[![Python versions][python-shield]][pypi-url]
[![License: MIT][license-shield]][license-url]

---

Declarative Python library for describing and generating documents
from application data. Users define the document structure and semantics, while
renderers handle output formats and backend-specific details

[📚 Documentation](https://dzhalaevd.github.io/caxton/)\
[📑 Changelog](CHANGELOG.md)

```python
from caxton import render, sheet, spreadsheet, table, text, write

rows = [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}]

report = spreadsheet(
    sheet(
        "People",
        table(
            rows,
            text("name").titled("Name"),
        ),
    ),
)

result = render(report)

write(report, "people.xlsx")
```

More examples are available in the [example projects](example)

The project is licensed under the [MIT](LICENSE)

## Installation

Install Caxton with pip:

```
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

[license-url]: LICENSE
