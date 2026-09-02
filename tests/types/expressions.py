from typing_extensions import assert_type

from caxton import field
from caxton.core.models import TransformExpression


def status_title(value: object) -> str:
    return str(value).title()


assert_type(field("status").transform(status_title), TransformExpression)
