from __future__ import annotations

from typing import ClassVar, Generic, TypeVar

from formata.core.errors import FormataTypeError

NodeT = TypeVar("NodeT")


class BinaryOperatorMixin(Generic[NodeT]):
    """Operator surface shared by the expression and formula hierarchies.

    A hierarchy supplies its own operator enum and node type by implementing
    ``_binary`` and ``_reverse``; every dunder below is declared once here so
    the two hierarchies cannot drift apart.
    """

    __slots__ = ()
    __hash__ = object.__hash__

    node_label: ClassVar[str] = "Nodes"

    def __bool__(self) -> bool:
        message = f"{self.node_label} cannot be used as boolean values"
        raise FormataTypeError(message)

    def _binary(self, operator_name: str, other: object) -> NodeT:
        """Combine this node with ``other`` on the right.

        Raises:
            NotImplementedError: If a hierarchy does not implement it.
        """
        raise NotImplementedError

    def _reverse(self, operator_name: str, other: object) -> NodeT:
        """Combine this node with ``other`` on the left.

        Raises:
            NotImplementedError: If a hierarchy does not implement it.
        """
        raise NotImplementedError

    def __add__(self, other: object) -> NodeT:
        return self._binary("ADD", other)

    def __radd__(self, other: object) -> NodeT:
        return self._reverse("ADD", other)

    def __sub__(self, other: object) -> NodeT:
        return self._binary("SUBTRACT", other)

    def __rsub__(self, other: object) -> NodeT:
        return self._reverse("SUBTRACT", other)

    def __mul__(self, other: object) -> NodeT:
        return self._binary("MULTIPLY", other)

    def __rmul__(self, other: object) -> NodeT:
        return self._reverse("MULTIPLY", other)

    def __truediv__(self, other: object) -> NodeT:
        return self._binary("DIVIDE", other)

    def __rtruediv__(self, other: object) -> NodeT:
        return self._reverse("DIVIDE", other)

    def __eq__(self, other: object) -> NodeT:  # type: ignore[override]
        return self._binary("EQUAL", other)

    def __ne__(self, other: object) -> NodeT:  # type: ignore[override]
        return self._binary("NOT_EQUAL", other)

    def __lt__(self, other: object) -> NodeT:
        return self._binary("LESS_THAN", other)

    def __le__(self, other: object) -> NodeT:
        return self._binary("LESS_THAN_OR_EQUAL", other)

    def __gt__(self, other: object) -> NodeT:
        return self._binary("GREATER_THAN", other)

    def __ge__(self, other: object) -> NodeT:
        return self._binary("GREATER_THAN_OR_EQUAL", other)

    def __and__(self, other: object) -> NodeT:
        return self._binary("AND", other)

    def __rand__(self, other: object) -> NodeT:
        return self._reverse("AND", other)

    def __or__(self, other: object) -> NodeT:
        return self._binary("OR", other)

    def __ror__(self, other: object) -> NodeT:
        return self._reverse("OR", other)


__all__ = ("BinaryOperatorMixin",)
