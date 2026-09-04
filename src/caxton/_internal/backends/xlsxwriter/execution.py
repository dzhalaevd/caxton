"""Select a compatible XlsxWriter workbook execution plan."""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from caxton.core.errors import UnsupportedFeatureError
from caxton.core.rendering import ExecutionMode, ExecutionRequirements


@dataclasses.dataclass(frozen=True, slots=True)
class StandardExecutionPlan:
    """XLSX plan for features that require ordinary workbook behavior."""

    name: ClassVar[str] = "standard"
    mode: ClassVar[ExecutionMode] = ExecutionMode.STANDARD
    data_passes: ClassVar[int] = 1

    @property
    def workbook_options(self) -> dict[str, bool]:
        """Isolated XlsxWriter options for this invocation."""
        return {"strings_to_formulas": False, "strings_to_urls": False}


@dataclasses.dataclass(frozen=True, slots=True)
class ConstantMemoryExecutionPlan:
    """Append-only XLSX plan that retains only the current worksheet row."""

    name: ClassVar[str] = "constant_memory"
    mode: ClassVar[ExecutionMode] = ExecutionMode.STREAM
    data_passes: ClassVar[int] = 1

    @property
    def workbook_options(self) -> dict[str, bool]:
        """Isolated XlsxWriter options for this invocation."""
        return {
            "constant_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        }


ExecutionPlan = StandardExecutionPlan | ConstantMemoryExecutionPlan


def select_execution_plan(requirements: ExecutionRequirements) -> ExecutionPlan:
    """Select a compatible XlsxWriter execution strategy.

    Returns:
        The execution plan for one render operation.

    Raises:
        UnsupportedFeatureError: If streaming would violate document needs.
    """
    _reject_incompatible_stream(requirements)
    plan = _preferred_plan(requirements)
    if requirements.requires_single_pass and plan.data_passes != 1:
        message = "Execution plan would make multiple passes over row data"
        raise UnsupportedFeatureError(
            message,
            context={"execution_plan": plan.name},
        )
    return plan


def _reject_incompatible_stream(requirements: ExecutionRequirements) -> None:
    stream_compatible = requirements.append_only and not requirements.has_named_tables
    if requirements.mode is not ExecutionMode.STREAM or stream_compatible:
        return
    reason = "document_is_not_append_only"
    if requirements.has_named_tables:
        reason = "native_table"
    elif requirements.requires_buffering:
        reason = "shape_dependent_buffering"
    message = "Streaming XLSX is incompatible with this document"
    raise UnsupportedFeatureError(
        message,
        context={"execution_mode": "stream", "reason": reason},
    )


def _preferred_plan(requirements: ExecutionRequirements) -> ExecutionPlan:
    stream_compatible = requirements.append_only and not requirements.has_named_tables
    if requirements.mode is ExecutionMode.STREAM:
        return ConstantMemoryExecutionPlan()
    if requirements.mode is ExecutionMode.AUTO and stream_compatible:
        return ConstantMemoryExecutionPlan()
    return StandardExecutionPlan()


__all__ = (
    "ConstantMemoryExecutionPlan",
    "ExecutionPlan",
    "StandardExecutionPlan",
    "select_execution_plan",
)
