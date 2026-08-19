<div align="center">

# Caxton

**Declarative document generation for Python**

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stars][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]

</div>

---

| 🏗️ This project is currently under development and is **not ready for production use**. |
|------------------------------------------------------------------------------------------|

## :mag: About

Declarative Python library for describing and generating documents
from application data. Users define the document structure and semantics, while
renderers handle output formats and backend-specific details.

## :alembic: Built With

![Python][python-shield]
![Excel][excel-shield]
![uv][uv-shield]
![wps][wemake-shield]

## Quick start

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

More examples are available in the [example projects](example).

## :books: Documentation

Full documentation is at [dzhalaevd.github.io/caxton](https://dzhalaevd.github.io/caxton/).

## :scroll: Licensing

- The project is licensed under the [MIT](LICENSE)

<div align="center">

### Works on Open-Source

If you find this project interesting, consider giving it a ⭐

</div>


[contributors-shield]: https://img.shields.io/github/contributors/dzhalaevd/caxton.svg?style=for-the-badge

[contributors-url]: https://github.com/dzhalaevd/caxton/graphs/contributors

[forks-shield]: https://img.shields.io/github/forks/dzhalaevd/caxton.svg?style=for-the-badge

[forks-url]: https://github.com/dzhalaevd/caxton/network/members

[stars-shield]: https://img.shields.io/github/stars/dzhalaevd/caxton.svg?style=for-the-badge

[stars-url]: https://github.com/dzhalaevd/caxton/stargazers

[issues-shield]: https://img.shields.io/github/issues/dzhalaevd/caxton.svg?style=for-the-badge

[issues-url]: https://github.com/dzhalaevd/caxton/issues

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54

[uv-shield]: https://img.shields.io/badge/uv-%23DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white

[fastapi-shield]: https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi

[sqlalchemy-shield]: https://img.shields.io/badge/sqlalchemy-%23D71F00.svg?style=for-the-badge&logo=sqlalchemy&logoColor=white

[pytest-shield]: https://img.shields.io/badge/pytest-%23ffffff.svg?style=for-the-badge&logo=pytest&logoColor=2f9fe3

[telegram-shield]: https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white

[react-shield]: https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB

[typescript-shield]: https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white

[vite-shield]: https://img.shields.io/badge/vite-%23646CFF.svg?style=for-the-badge&logo=vite&logoColor=white

[postgres-shield]: https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white

[otel-shield]: https://img.shields.io/badge/OpenTelemetry-FFFFFF?style=for-the-badge&logo=opentelemetry&logoColor=black

[grafana-shield]: https://img.shields.io/badge/grafana-%23F46800.svg?style=for-the-badge&logo=grafana&logoColor=white

[prometheus-shield]: https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=Prometheus&logoColor=white

[docker-shield]: https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white

[wemake-shield]: https://img.shields.io/badge/Style_WPS-%23000000.svg?style=for-the-badge&logo=python&logoColor=white

[excel-shield]: https://img.shields.io/badge/Microsoft_Excel-217346?style=for-the-badge&logo=microsoft-excel&logoColor=white
