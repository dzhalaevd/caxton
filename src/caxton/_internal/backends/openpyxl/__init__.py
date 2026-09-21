from __future__ import annotations

import importlib

from caxton._internal.const import _OPENPYXL_EXPORTS


def __getattr__(name: str) -> object:  # noqa: WPS413
    module_name = _OPENPYXL_EXPORTS.get(name)
    if module_name is None:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)
    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


__all__ = ("OpenpyxlRenderer", "OpenpyxlTemplateRenderer")
