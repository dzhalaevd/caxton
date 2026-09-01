# Installation

Caxton requires **Python 3.10 or newer** and ships as a single distribution.
XlsxWriter and OpenPyXL are base runtime dependencies, so no extra is needed to
render or inspect XLSX files.

=== "uv"

    ```bash
    uv add caxton
    ```

=== "pip"

    ```bash
    pip install caxton
    ```

## Optional extras

| Extra        | Installs     | Use it for                                                    |
|--------------|--------------|---------------------------------------------------------------|
| `hypothesis` | `hypothesis` | The property-based strategies in `caxton.testing.strategies`. |

```bash
uv add "caxton[hypothesis]"
```

## Verify the installation

```python
import caxton

print(caxton.__version__)
```

## Supported versions

Caxton is tested on CPython 3.10, 3.11, 3.12, 3.13 and 3.14 across Linux, macOS and
Windows, using both the built wheel and the source distribution.

## Working on Caxton itself

Clone the repository and create the locked development environment with
[uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/dzhalaevd/caxton.git
cd caxton
uv sync
```

See [Contributing](../contributing.md) for the check commands.
