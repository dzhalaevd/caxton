from __future__ import annotations

from typing import NoReturn

from caxton.core.errors import OutputError


def raise_output_error(
    message: str,
    *,
    error: OSError | ValueError,
    operation: str,
    target: str | None = None,
    target_type: str | None = None,
) -> NoReturn:
    """Translate a destination failure into a contextual output error.

    Raises:
        OutputError: Always, chaining the original destination error.
    """
    context = {
        "exception_type": type(error).__name__,
        "operation": operation,
    }
    if target is not None:
        context["target"] = target
    if target_type is not None:
        context["target_type"] = target_type
    raise OutputError(message, context=context) from error
