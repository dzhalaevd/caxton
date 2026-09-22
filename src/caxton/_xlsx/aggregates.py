"""Excel function names for aggregate footers."""

from caxton.core.models import AggregateFunction

_AGGREGATES = {
    AggregateFunction.SUM: "SUM",
    AggregateFunction.AVG: "AVERAGE",
    AggregateFunction.MIN: "MIN",
    AggregateFunction.MAX: "MAX",
    AggregateFunction.COUNT: "COUNT",
}
