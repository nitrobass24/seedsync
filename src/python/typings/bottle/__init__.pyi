from collections.abc import Callable, Iterator
from typing import Any

# --- Request/Response types ---

class HeaderDict(dict[str, str]):
    def __setitem__(self, key: str, value: str) -> None: ...

class FormsDict(dict[str, str]):
    def get(self, key: str, default: str | None = None) -> str | None: ...  # type: ignore[override]

class WSGIHeaderDict(dict[str, str]):
    def get(self, key: str, default: str | None = None) -> str | None: ...  # type: ignore[override]

class BaseRequest:
    method: str
    path: str
    environ: WSGIHeaderDict
    params: FormsDict
    query: FormsDict
    body: Any
    content_type: str
    content_length: int
    def get_header(self, name: str, default: str | None = None) -> str | None: ...

class BaseResponse:
    status_code: int
    status_line: str
    status: str
    headers: HeaderDict
    content_type: str
    cache_control: str
    def set_header(self, name: str, value: str) -> None: ...
    def add_header(self, name: str, value: str) -> None: ...

request: BaseRequest
response: BaseResponse

# --- Exceptions ---

class HTTPResponse(BaseResponse, Exception):
    def __init__(
        self,
        body: str | bytes = "",
        status: int | str | None = None,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
        **more_headers: str,
    ) -> None: ...

class HTTPError(HTTPResponse):
    def __init__(
        self,
        status: int = 500,
        body: str | None = None,
        exception: Exception | None = None,
        traceback: str | None = None,
        **options: Any,
    ) -> None: ...

# --- Application ---

class Bottle:
    def __init__(self, **kwargs: Any) -> None: ...
    def hook(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def route(
        self,
        path: str | None = None,
        method: str = "GET",
        callback: Callable[..., Any] | None = None,
        **options: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def get(self, path: str | None = None, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def post(self, path: str | None = None, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def put(self, path: str | None = None, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def delete(self, path: str | None = None, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterator[bytes]: ...

# --- Server ---

class ServerAdapter:
    host: str
    port: int
    options: dict[str, Any]
    quiet: bool
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, **options: Any) -> None: ...
    def run(self, handler: Callable[..., Any]) -> None: ...

# --- Utilities ---

def run(
    app: Bottle | Callable[..., Any] | None = None,
    server: str | type[ServerAdapter] | ServerAdapter = "wsgiref",
    host: str = "127.0.0.1",
    port: int = 8080,
    interval: int = 1,
    reloader: bool = False,
    quiet: bool = False,
    plugins: list[Any] | None = None,
    debug: bool | None = None,
    **kargs: Any,
) -> None: ...
def static_file(
    filename: str,
    root: str,
    mimetype: str | bool = True,
    download: bool | str = False,
    charset: str = "UTF-8",
    etag: str | bool | None = None,
) -> HTTPResponse: ...
