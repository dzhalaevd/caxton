from __future__ import annotations

import dataclasses
import math

from caxton.core._compat import final
from caxton.core.errors import CaxtonTypeError, CaxtonValueError


@final
@dataclasses.dataclass(frozen=True, slots=True)
class AutoWidth:
    """Backend-neutral bounds for a content-derived column width."""

    minimum: float = 1
    maximum: float = 80

    def __post_init__(self) -> None:
        minimum = _positive_width(self.minimum, label="minimum")
        maximum = _positive_width(self.maximum, label="maximum")
        if minimum > maximum:
            message = "Auto-width minimum must not exceed its maximum"
            raise CaxtonValueError(message)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)


def resolve_auto_width(value: AutoWidth | bool | None) -> AutoWidth | None:
    """Normalize the convenience boolean form into an explicit policy.

    Returns:
        A resolved policy, or ``None`` when automatic sizing is disabled.

    Raises:
        CaxtonTypeError: If the value is not a supported auto-width input.
    """
    if value is True:
        return AutoWidth()
    if value is False or value is None:
        return None
    if isinstance(value, AutoWidth):
        return value
    message = "Auto width must be a boolean or AutoWidth"
    raise CaxtonTypeError(message)


def _positive_width(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        message = f"Auto-width {label} must be numeric"
        raise CaxtonTypeError(message)
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        message = f"Auto-width {label} must be positive"
        raise CaxtonValueError(message)
    return normalized


__all__ = (
    "AutoWidth",
    "resolve_auto_width",
)
