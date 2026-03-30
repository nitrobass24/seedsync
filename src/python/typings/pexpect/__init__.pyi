from pexpect import exceptions as exceptions

EOF: type[exceptions.EOF]
TIMEOUT: type[exceptions.TIMEOUT]

class spawn:
    before: bytes | None
    after: bytes | type[exceptions.EOF] | type[exceptions.TIMEOUT] | None
    exitstatus: int | None

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        timeout: int = 30,
        maxread: int = 2000,
        searchwindowsize: int | None = None,
        logfile: object | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        encoding: str | None = None,
    ) -> None: ...
    def expect(
        self,
        pattern: str
        | type[exceptions.EOF]
        | type[exceptions.TIMEOUT]
        | list[str | type[exceptions.EOF] | type[exceptions.TIMEOUT]],
        timeout: float = -1,
        searchwindowsize: int = -1,
    ) -> int: ...
    def sendline(self, s: str = "") -> int: ...
    def setwinsize(self, rows: int, cols: int) -> None: ...
    def isalive(self) -> bool: ...
    def close(self, force: bool = True) -> None: ...
