from collections.abc import Callable
from typing import Any

def install(
    *exc_classes_or_instances: type[BaseException] | BaseException,
    get_locals: Callable[[Any], dict[str, object]] | None = None,
) -> type[BaseException] | None: ...
