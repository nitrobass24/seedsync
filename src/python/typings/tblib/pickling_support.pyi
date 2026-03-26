from collections.abc import Callable
from types import TracebackType

def install(
    *exc_classes_or_instances: type[BaseException] | BaseException,
    get_locals: Callable[[TracebackType], dict[str, object]] | None = None,
) -> type[BaseException] | None: ...
