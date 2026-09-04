from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, TypeAlias

from caxton.core.errors import CaxtonTypeError

from ._validation import require_name
from .formulas import TableReference
from .templates import TemplateRef


@dataclasses.dataclass(frozen=True, slots=True)
class OpenpyxlHookContext:
    """Narrow XLSX-scoped access to native OpenPyXL objects."""

    native_workbook: Any
    native_sheet: Any


OpenpyxlHook: TypeAlias = Callable[[OpenpyxlHookContext], None]


@dataclasses.dataclass(frozen=True, slots=True)
class OpenpyxlHookExtension:
    """Run one explicit hook after semantic content is rendered."""

    function: OpenpyxlHook
    sheet: str | None = None
    namespace: str = dataclasses.field(default="xlsx.openpyxl", init=False)
    required_capabilities: frozenset[str] = dataclasses.field(
        default=frozenset(("xlsx_openpyxl_hook",)),
        init=False,
    )

    def __post_init__(self) -> None:
        if not callable(self.function):
            message = "OpenPyXL hook must be callable"
            raise CaxtonTypeError(message)
        if self.sheet is not None:
            require_name(self.sheet, "OpenPyXL hook sheet")


@dataclasses.dataclass(frozen=True, slots=True)
class PivotBinding:
    """XLSX-only intent to rebind an existing pivot cache source."""

    target: str
    source: TemplateRef | TableReference
    refresh_on_open: bool = True
    namespace: str = dataclasses.field(default="xlsx.pivot", init=False)
    required_capabilities: frozenset[str] = dataclasses.field(
        default=frozenset(("xlsx_pivot_rebind", "xlsx_pivot_refresh")),
        init=False,
    )

    def __post_init__(self) -> None:
        require_name(self.target, "Pivot target")
        if not isinstance(self.source, (TemplateRef, TableReference)):
            message = "Pivot source must be created with slot() or table_ref()"
            raise CaxtonTypeError(message)


def openpyxl_hook(
    function: OpenpyxlHook,
    *,
    sheet: str | None = None,
) -> OpenpyxlHookExtension:
    """Create an XLSX-namespaced post-render OpenPyXL hook.

    Returns:
        An immutable capability-aware extension.
    """
    return OpenpyxlHookExtension(function=function, sheet=sheet)


def pivot(
    target: str,
    *,
    source: TemplateRef | TableReference,
    refresh_on_open: bool = True,
) -> PivotBinding:
    """Bind an existing XLSX pivot to generated data.

    Returns:
        Immutable XLSX pivot intent.
    """
    return PivotBinding(
        target=target,
        source=source,
        refresh_on_open=refresh_on_open,
    )


pivot_binding = pivot


__all__ = (
    "OpenpyxlHook",
    "OpenpyxlHookContext",
    "OpenpyxlHookExtension",
    "PivotBinding",
    "openpyxl_hook",
    "pivot",
    "pivot_binding",
)
