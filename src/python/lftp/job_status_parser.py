# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import re

from common import AppError

from .job_status import LftpJobStatus


class LftpJobStatusParserError(AppError):
    pass


# Shared regex fragments.
#
# These live at module scope (rather than as ``__``-mangled class attributes)
# so the pre-compiled patterns below can interpolate them without tripping over
# name mangling. The class attributes on ``LftpJobStatusParser`` simply alias
# these so ``_size_to_bytes``, ``_eta_to_seconds`` and ``__parse_queue`` keep
# resolving the same strings they always did.

# python doesn't support partial inline-modified flags, so we need
# to capture all case-sensitive cases here
_SIZE_UNITS_REGEX = (
    r"b|B|"
    r"k|kb|kib|K|Kb|KB|KiB|Kib|"
    r"m|mb|mib|M|Mb|MB|MiB|Mib|"
    r"g|gb|gib|G|Gb|GB|GiB|Gib"
)
_TIME_UNITS_REGEX = r"(?P<eta_d>\d+d)?(?P<eta_h>\d+h)?(?P<eta_m>\d+m)?(?P<eta_s>\d+s)?"

_QUOTED_FILE_NAME_REGEX = r"`(?P<name>.*)'"

_QUEUE_DONE_REGEX = r"^\[(?P<id>\d+)\]\sDone\s\(queue\s\(.+\)\)"


# Pre-compiled patterns used by __parse_jobs.
#
# These were previously compiled inside __parse_jobs on every parse() call,
# which runs on the controller thread every status poll. Compiling them once
# at import time is behavior-preserving (regex compilation is referentially
# transparent) and avoids the per-cycle recompile cost.

# pget header
_RE_PGET_HEADER = re.compile(
    r"^\[(?P<id>\d+)\]\s+"
    r"pget\s+"
    r"(?P<flags>.*?)\s+"
    r"(?P<lq>['\"]|)(?P<remote>.+)(?P=lq)\s+"  # greedy on purpose
    r"-o\s+"
    r"(?P<rq>['\"]|)(?P<local>.+)(?P=rq)$"  # greedy on purpose
)

# mirror header (downloading)
_RE_MIRROR_HEADER = re.compile(
    r"^\[(?P<id>\d+)\]\s+"
    r"mirror\s+"
    r"(?P<flags>.*?)\s+"
    r"(?P<lq>['\"]|)(?P<remote>.+)(?P=lq)\s+"  # greedy on purpose
    r"(?P<rq>['\"]|)(?P<local>.+)(?P=rq)\s+"  # greedy on purpose
    r"--\s+"
    rf"(?P<szlocal>\d+\.?\d*\s?({_SIZE_UNITS_REGEX})?)"  # size=0 has no units
    r"\/"
    rf"(?P<szremote>\d+\.?\d*\s?({_SIZE_UNITS_REGEX})?)\s+"  # size=0 has no units
    r"\((?P<pctlocal>\d+)%\)"
    rf"(\s+(?P<speed>\d+\.?\d*\s?({_SIZE_UNITS_REGEX}))\/s)?$"
)

# mirror header (connecting or receiving file list)
_RE_MIRROR_FL_HEADER = re.compile(
    r"^\[(?P<id>\d+)\]\s+"
    r"mirror\s+"
    r"(?P<flags>.*?)\s+"
    r"(?P<lq>['\"]|)(?P<remote>.+)(?P=lq)\s+"  # greedy on purpose
    r"(?P<rq>['\"]|)(?P<local>.+)(?P=rq)$"  # greedy on purpose
)

# Data patterns
_RE_FILENAME = re.compile(r"\\transfer\s" + _QUOTED_FILE_NAME_REGEX)

_RE_CHUNK_AT = re.compile(
    (
        r"^" + _QUOTED_FILE_NAME_REGEX + r"\s+"
        r"at\s+"
        r"\d+\s+"  # this is NOT the local size
        r"(?:\(\d+%\)\s+)?"  # this is NOT the local percent
        r"((?P<speed>\d+\.?\d*\s?({sz}))\/s\s+)?"
        r"(eta:(?P<eta>{eta})\s+)?"
        r"\s*\[(?P<desc>.*)\]$"
    ).format(sz=_SIZE_UNITS_REGEX, eta=_TIME_UNITS_REGEX)
)

_RE_CHUNK_AT2 = re.compile(
    r"^" + _QUOTED_FILE_NAME_REGEX + r"\s+"
    r"at\s+"
    r"\d+\s+"  # this is NOT the local size
    r"(?:\(\d+%\))"  # this is NOT the local percent
)

_RE_CHUNK_GOT = re.compile(
    (
        r"^" + _QUOTED_FILE_NAME_REGEX + r",\s+"
        r"got\s+"
        r"(?P<szlocal>\d+)\s+"
        r"of\s+"
        r"(?P<szremote>\d+)\s+"
        r"\((?P<pctlocal>\d+)%\)"
        r"(\s+(?P<speed>\d+\.?\d*\s?({sz}))\/s)?"
        r"(\seta:(?P<eta>{eta}))?"
    ).format(sz=_SIZE_UNITS_REGEX, eta=_TIME_UNITS_REGEX)
)

_RE_CHUNK_HEADER = re.compile(r"\\chunk\s+\d+")

_RE_CHMOD_HEADER = re.compile(r"chmod\s(?P<name>.*)")

_RE_CHMOD = re.compile(_QUOTED_FILE_NAME_REGEX + r"\s\[\]")

_RE_MIRROR = re.compile(
    (
        r"\\mirror\s" + _QUOTED_FILE_NAME_REGEX + r"\s+"
        r"--\s+"
        r"(?P<szlocal>\d+\.?\d*\s?({sz})?)"  # size=0 has no units
        r"\/"
        r"(?P<szremote>\d+\.?\d*\s?({sz})?)\s+"  # size=0 has no units
        r"\((?P<pctlocal>\d+)%\)"
        r"(\s+(?P<speed>\d+\.?\d*\s?({sz}))\/s)?$"
    ).format(sz=_SIZE_UNITS_REGEX)
)

_RE_MIRROR_EMPTY = re.compile(r"\\mirror\s" + _QUOTED_FILE_NAME_REGEX + r"\s*$")

_RE_QUEUE_DONE = re.compile(_QUEUE_DONE_REGEX)

# Orphan progress lines lftp can emit outside a job context, e.g.:
#   "3.0K/s eta:3m [Receiving data]"
#   "10M/s eta:1h2m [Making data connection]"
_RE_ORPHAN_PROGRESS = re.compile(
    rf"^(?:\d+\.?\d*\s?({_SIZE_UNITS_REGEX}))\/s\s+"
    rf"eta:({_TIME_UNITS_REGEX})\s+"
    r"\[.*\]$"
)

# Partial progress fragments from line-wrap (seen on Unraid), e.g.:
#   "/s eta:25m [Receiving data]"  (tail of "347.3K/s eta:25m ...")
_RE_PARTIAL_PROGRESS = re.compile(
    r"^\/s\s+"
    rf"eta:({_TIME_UNITS_REGEX})\s+"
    r"\[.*\]$"
)

# Chunk line-wrap fragments: long filenames cause lftp chunk progress
# lines to wrap, producing a tail fragment like:
#   "tmos.7.1.DV.HDR.H.265-TheFarm.mkv' at 22283455338 (0%) 427.6K/s eta:28m [Receiving data]"
# These are the tail of a `filename' at <pos> (<pct>%) ... line where
# the leading backtick and start of the filename are on the previous line.
_RE_CHUNK_WRAP = re.compile(
    r"^(?:[^`\\].*)?'\s+at\s+\d+\s+"
    r"(?:\(\d+%\)\s+)?"
    rf"(?:(?:\d+\.?\d*\s?({_SIZE_UNITS_REGEX}))\/s\s+)?"
    rf"(?:eta:({_TIME_UNITS_REGEX})\s+)?"
    r"\s*\[.*\]$"
)


class LftpJobStatusParser:
    """
    Parses the output of lftp's "jobs -v" command into a LftpJobStatus
    """

    # Aliases to the module-level fragments (see above). Kept as class
    # attributes so existing references via the (mangled) ``__`` names keep
    # resolving unchanged.
    __SIZE_UNITS_REGEX = _SIZE_UNITS_REGEX
    __TIME_UNITS_REGEX = _TIME_UNITS_REGEX
    __QUOTED_FILE_NAME_REGEX = _QUOTED_FILE_NAME_REGEX
    __QUEUE_DONE_REGEX = _QUEUE_DONE_REGEX

    def __init__(self):
        self.logger = logging.getLogger("LftpJobStatusParser")

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("LftpJobStatusParser")

    @staticmethod
    def _size_to_bytes(size: str) -> int:
        """
        Parse the size string and return number of bytes
        :param size:
        :return:
        """
        if size == "0":
            return 0
        m = re.compile(rf"(?P<number>\d+\.?\d*)\s*(?P<units>{LftpJobStatusParser.__SIZE_UNITS_REGEX})?")
        result = m.search(size)
        if not result:
            raise ValueError(f"String '{size}' does not match the size pattern")
        number = float(result.group("number"))
        unit = (result.group("units") or "b")[0].lower()
        multipliers = {"b": 1, "k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
        if unit not in multipliers:
            raise ValueError(f"Unrecognized unit {unit} in size string '{size}'")
        return int(number * multipliers[unit])

    @staticmethod
    def _eta_to_seconds(eta: str) -> int:
        """
        Parse the time string and return number of seconds
        :param eta:
        :return:
        """
        m = re.compile(LftpJobStatusParser.__TIME_UNITS_REGEX)
        result = m.search(eta)
        if not result:
            raise ValueError(f"String '{eta}' does not match the eta pattern")
        # the [:-1] below remove the last character
        eta_d = int((result.group("eta_d") or "0d")[:-1])
        eta_h = int((result.group("eta_h") or "0h")[:-1])
        eta_m = int((result.group("eta_m") or "0m")[:-1])
        eta_s = int((result.group("eta_s") or "0s")[:-1])
        return eta_d * 24 * 3600 + eta_h * 3600 + eta_m * 60 + eta_s

    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        """
        Strip ANSI escape sequences from text.
        These can appear in lftp output when terminal features like
        bracketed paste mode are enabled (e.g., ^[[?2004l, ^[[?2004h).
        """
        # Match ANSI escape sequences: ESC [ ... <letter>
        # This covers CSI sequences including bracketed paste mode
        ansi_pattern = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
        return ansi_pattern.sub("", text)

    def parse(self, output: str) -> list[LftpJobStatus]:
        statuses: list[LftpJobStatus] = []
        # Strip ANSI escape codes that may be present in terminal output
        output = self._strip_ansi_codes(output)
        # Phase 1: Strip junk before the first 'jobs -v' command echo.
        # The pexpect buffer may contain lftp progress output before the echo.
        idx = output.find("jobs -v")
        if idx >= 0:
            output = output[idx + len("jobs -v") :]
        # Phase 2: Remove any remaining 'jobs -v' echoes before line splitting.
        # pexpect echoes the command back, and when lftp is writing status data
        # simultaneously, the echo can be interleaved mid-line, splitting
        # filenames across lines. Stripping before splitting reconstructs them.
        # The echo only ever appears at a line boundary, so anchor the removal
        # there: strip echo+newline pairs (rejoins a filename split across the
        # break) and standalone echo lines. This avoids deleting a literal
        # 'jobs -v' that is part of a real filename (e.g. 'My.jobs -v.Release').
        output = output.replace("jobs -v\n", "")
        output = re.sub(r"(?m)^[ \t]*jobs -v[ \t]*$", "", output)
        lines = [s.strip() for s in output.splitlines()]
        lines = list(filter(None, lines))  # remove blank lines
        # remove any remaining log line
        lines = filter(lambda s: not re.match(r"^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}.*\s->\s.*$", s), lines)
        lines = list(lines)
        try:
            statuses += self.__parse_queue(lines)
            statuses += self.__parse_jobs(lines)
        except ValueError as e:
            self.logger.error(f"LftpJobStateParser error: {e!s}")
            self.logger.error(f"Status:\n{output}")
            raise LftpJobStatusParserError("Error parsing lftp job status") from e
        return statuses

    @staticmethod
    def _is_orphan_progress_line(line: str) -> bool:
        """True if ``line`` is a known progress fragment lftp emits outside a
        job context (orphan progress, line-wrap partials, or wrapped chunk
        tails) that should be skipped rather than raised on."""
        return bool(_RE_ORPHAN_PROGRESS.match(line) or _RE_PARTIAL_PROGRESS.match(line) or _RE_CHUNK_WRAP.match(line))

    @staticmethod
    def _is_valid_first_line(line: str, prev_job: "LftpJobStatus | None") -> bool:
        """The first line of a job block must be a valid header; once a job is
        in context any line is permitted (the cascade decides what to do)."""
        return bool(
            prev_job or _RE_PGET_HEADER.match(line) or _RE_MIRROR_HEADER.match(line) or _RE_MIRROR_FL_HEADER.match(line)
        )

    @staticmethod
    def _build_chunk_transfer_state(
        result_at: "re.Match[str] | None",
        result_at2: "re.Match[str] | None",
        result_got: "re.Match[str] | None",
    ) -> "LftpJobStatus.TransferState":
        """Build a TransferState from whichever of the three chunk-data regex
        matches is present. Caller is responsible for the name-mismatch checks
        (which differ between the pget header and the filename chunk)."""
        if result_at:
            speed = None
            if result_at.group("speed"):
                speed = LftpJobStatusParser._size_to_bytes(result_at.group("speed"))
            eta = None
            if result_at.group("eta"):
                eta = LftpJobStatusParser._eta_to_seconds(result_at.group("eta"))
            return LftpJobStatus.TransferState(None, None, None, speed, eta)
        if result_at2:
            return LftpJobStatus.TransferState(None, None, None, None, None)
        # result_got (one of the three is guaranteed non-None by the caller)
        assert result_got is not None
        size_local = int(result_got.group("szlocal"))
        size_remote = int(result_got.group("szremote"))
        percent_local = int(result_got.group("pctlocal"))
        speed = None
        if result_got.group("speed"):
            speed = LftpJobStatusParser._size_to_bytes(result_got.group("speed"))
        eta = None
        if result_got.group("eta"):
            eta = LftpJobStatusParser._eta_to_seconds(result_got.group("eta"))
        return LftpJobStatus.TransferState(size_local, size_remote, percent_local, speed, eta)

    def _parse_pget_header_block(self, result: "re.Match[str]", lines: list[str]) -> LftpJobStatus:
        """Parse a pget header line (already matched) plus its mandatory 'sftp'
        line and optional data line into a RUNNING pget LftpJobStatus."""
        # Next line must be the sftp line
        if len(lines) < 1 or "sftp" not in lines[0]:
            raise ValueError(f"Missing the 'sftp' line for pget header '{result.string}'")
        lines.pop(0)  # pop the 'sftp' line

        # Data line may not exist
        result_at = None
        result_at2 = None
        result_got = None
        if lines:
            line = lines.pop(0)  # data line
            result_at = _RE_CHUNK_AT.search(line)
            result_at2 = _RE_CHUNK_AT2.search(line)
            result_got = _RE_CHUNK_GOT.search(line)

        id_ = int(result.group("id"))
        name = os.path.basename(os.path.normpath(result.group("remote")))
        flags = result.group("flags")
        status = LftpJobStatus(
            job_id=id_, job_type=LftpJobStatus.Type.PGET, state=LftpJobStatus.State.RUNNING, name=name, flags=flags
        )
        if result_at:
            if result.group("remote") != result_at.group("name"):
                raise ValueError(
                    "Mismatch between pget names '{}' vs '{}'".format(result.group("remote"), result_at.group("name"))
                )
        elif result_at2:
            if result.group("remote") != result_at2.group("name"):
                raise ValueError(
                    "Mismatch between pget names '{}' vs '{}'".format(result.group("remote"), result_at2.group("name"))
                )
        elif result_got:
            got_group_basename = os.path.basename(os.path.normpath(result_got.group("name")))
            if got_group_basename != name:
                raise ValueError(f"Mismatch: filename '{name}' but chunk data for '{got_group_basename}'")

        if result_at or result_at2 or result_got:
            transfer_state = LftpJobStatusParser._build_chunk_transfer_state(result_at, result_at2, result_got)
        else:
            # No data line at all
            transfer_state = LftpJobStatus.TransferState(None, None, None, None, None)

        status.total_transfer_state = transfer_state
        return status

    @staticmethod
    def _parse_mirror_header(result: "re.Match[str]") -> LftpJobStatus:
        """Parse a downloading mirror header line (already matched) into a
        RUNNING mirror LftpJobStatus with size/speed totals."""
        id_ = int(result.group("id"))
        name = os.path.basename(os.path.normpath(result.group("remote")))
        flags = result.group("flags")
        status = LftpJobStatus(
            job_id=id_, job_type=LftpJobStatus.Type.MIRROR, state=LftpJobStatus.State.RUNNING, name=name, flags=flags
        )
        size_local = LftpJobStatusParser._size_to_bytes(result.group("szlocal"))
        size_remote = LftpJobStatusParser._size_to_bytes(result.group("szremote"))
        percent_local = int(result.group("pctlocal"))
        speed = None
        if result.group("speed"):
            speed = LftpJobStatusParser._size_to_bytes(result.group("speed"))
        status.total_transfer_state = LftpJobStatus.TransferState(
            size_local,
            size_remote,
            percent_local,
            speed,
            None,  # eta
        )
        return status

    @staticmethod
    def _parse_mirror_fl_header(result: "re.Match[str]", lines: list[str]) -> LftpJobStatus:
        """Parse a connecting / receiving-file-list mirror header (already
        matched) into a RUNNING mirror LftpJobStatus, popping the optional
        'Getting file list'/'cd ' follow-up line."""
        # There may be a 'Connecting' or 'cd' line ahead, but not always
        if lines and (lines[0].startswith("Getting file list") or lines[0].startswith("cd ")):
            lines.pop(0)  # pop the connecting line
        id_ = int(result.group("id"))
        name = os.path.basename(os.path.normpath(result.group("remote")))
        flags = result.group("flags")
        return LftpJobStatus(
            job_id=id_, job_type=LftpJobStatus.Type.MIRROR, state=LftpJobStatus.State.RUNNING, name=name, flags=flags
        )

    def _parse_filename_chunk(
        self, result: "re.Match[str]", lines: list[str], prev_job: "LftpJobStatus | None"
    ) -> None:
        """Parse a '\\transfer `name'' line (already matched) plus its
        following chunk-data line, registering the active file transfer state
        on ``prev_job``."""
        name = result.group("name")
        if not lines:
            raise ValueError(f"Missing chunk data for filename '{name}'")
        line = lines.pop(0)
        result_at = _RE_CHUNK_AT.search(line)
        result_at2 = _RE_CHUNK_AT2.search(line)
        result_got = _RE_CHUNK_GOT.search(line)
        basename = os.path.basename(os.path.normpath(name))
        if result_at:
            # filename is full path, but chunk name is only normpath
            if result_at.group("name") != basename:
                raise ValueError(
                    "Mismatch: filename '{}' but chunk data for '{}'".format(name, result_at.group("name"))
                )
        elif result_at2:
            # filename is full path, but chunk name is only normpath
            if result_at2.group("name") != basename:
                raise ValueError(
                    "Mismatch: filename '{}' but chunk data for '{}'".format(name, result_at2.group("name"))
                )
        elif result_got:
            if result_got.group("name") != basename:
                raise ValueError(
                    "Mismatch: filename '{}' but chunk data for '{}'".format(name, result_got.group("name"))
                )
        else:
            raise ValueError(f"Missing chunk data for filename '{name}'")
        file_status = LftpJobStatusParser._build_chunk_transfer_state(result_at, result_at2, result_got)
        assert prev_job is not None
        prev_job.add_active_file_transfer_state(name, file_status)

    @staticmethod
    def _skip_mirror_noise(line: str, lines: list[str]) -> bool:
        """Match-and-ignore a '\\mirror' line. Returns True if handled.
        The downloading '\\mirror' line carries no extra follow-up; the empty
        '\\mirror' line may be followed by one ignorable line."""
        if _RE_MIRROR.search(line):
            return True
        result = _RE_MIRROR_EMPTY.search(line)
        if result:
            name = result.group("name")
            # One of these lines may follow, ignore it as well
            #    "Getting files list"
            #    "cd"
            #    "<name>: "
            #    "mkdir"
            if lines and (
                "Getting file list" in lines[0]
                or lines[0].startswith("cd ")
                or lines[0] == f"{name}:"
                or lines[0].startswith("mkdir ")
            ):
                lines.pop(0)
            return True
        return False

    @staticmethod
    def _skip_chunk_header(line: str, lines: list[str]) -> bool:
        """Match-and-ignore a '\\chunk' line plus its optional backtick data
        line. Returns True if handled."""
        if not _RE_CHUNK_HEADER.search(line):
            return False
        # Also need to ignore the next line (chunk data)
        if lines and lines[0].startswith("`"):
            lines.pop(0)
        return True

    @staticmethod
    def _skip_chmod_block(line: str, lines: list[str]) -> bool:
        """Match-and-ignore a 'chmod' line plus its mandatory 'file:' line and
        optional matching '`name' []' line. Returns True if handled."""
        result = _RE_CHMOD_HEADER.search(line)
        if not result:
            return False
        name = result.group("name")
        # Also ignore the next one or two lines
        if not lines or not lines[0].startswith("file:"):
            raise ValueError(f"Missing 'file:' line for chmod '{name}'")
        lines.pop(0)
        if lines:
            result_chmod = _RE_CHMOD.search(lines[0])
            if result_chmod:
                name_chmod = result_chmod.group("name")
                if name != name_chmod:
                    raise ValueError(f"Mismatch in names chmod '{name}'")
                lines.pop(0)
        return True

    def _skip_noise_line(self, line: str, lines: list[str], prev_job: "LftpJobStatus | None") -> bool:
        """Handle the tail of the dispatch cascade for a line that matched no
        header/data/ignore branch: the queue 'Done' line, in-job unrecognized
        fragments, and out-of-context orphan progress. Returns True if handled;
        raises ValueError for a truly unrecognized line outside any job."""
        # Search for the Done line, but it better be the last line
        if _RE_QUEUE_DONE.match(line):
            if lines:
                raise ValueError("There are more lines after the 'Done' line")
            return True

        # If we're inside a job context, skip any unrecognized line.
        # PTY line-wrapping can produce arbitrary fragments (filename tails,
        # partial speed/eta strings like "eta:4m [Receiving data]" or
        # "ta:4m [Receiving data]") that no fixed regex can anticipate.
        if prev_job is not None:
            self.logger.warning("Skipping unrecognized line inside job context: '%s'", line)
            return True

        # Outside a job context, check for known orphan progress lines
        if LftpJobStatusParser._is_orphan_progress_line(line):
            self.logger.warning("Skipping orphan lftp progress line: '%s'", line)
            return True

        # Truly unrecognized line outside any job — raise so the caller
        # can track consecutive errors and decide whether to propagate
        raise ValueError(f"Unable to parse line '{line}'")

    def _dispatch_job_line(self, line: str, lines: list[str], prev_job: "LftpJobStatus | None"):
        """Run the ordered dispatch cascade for a single popped line. Returns
        the LftpJobStatus to push (and adopt as the new ``prev_job``) when the
        line started a new job, or None when the line was data/noise that left
        ``prev_job`` unchanged. ORDER IS LOAD-BEARING."""
        # Search for pget header
        result = _RE_PGET_HEADER.search(line)
        if result:
            return self._parse_pget_header_block(result, lines)

        # Search for mirror header
        result = _RE_MIRROR_HEADER.search(line)
        if result:
            return LftpJobStatusParser._parse_mirror_header(result)

        # Search for mirror connecting header
        # Note: this must be after the more restrictive mirror header above
        result = _RE_MIRROR_FL_HEADER.search(line)
        if result:
            return LftpJobStatusParser._parse_mirror_fl_header(result, lines)

        # Search for filename
        result = _RE_FILENAME.search(line)
        if result:
            self._parse_filename_chunk(result, lines, prev_job)
            return None

        # Search for but ignore "\mirror" / "\chunk" / "chmod" lines
        if (
            LftpJobStatusParser._skip_mirror_noise(line, lines)
            or LftpJobStatusParser._skip_chunk_header(line, lines)
            or LftpJobStatusParser._skip_chmod_block(line, lines)
        ):
            return None

        # Done line / in-job skip / orphan skip / raise
        self._skip_noise_line(line, lines, prev_job)
        return None

    def __parse_jobs(self, lines: list[str]) -> list[LftpJobStatus]:
        jobs: list[LftpJobStatus] = []

        prev_job: LftpJobStatus | None = None
        while lines:
            line = lines.pop(0)

            # First line must be a valid job header.
            # Exception: skip known orphan progress lines that lftp emits
            # outside a job context (e.g. "3.0K/s eta:3m [Receiving data]").
            if not LftpJobStatusParser._is_valid_first_line(line, prev_job):
                if LftpJobStatusParser._is_orphan_progress_line(line):
                    self.logger.warning("Skipping orphan lftp progress line: '%s'", line)
                    continue
                raise ValueError(f"First line is not a matching header '{line}'")

            status = self._dispatch_job_line(line, lines, prev_job)
            if status is not None:
                jobs.append(status)
                prev_job = status
        return jobs

    @staticmethod
    def __parse_queue(lines: list[str]) -> list[LftpJobStatus]:  # noqa: C901 — complexity 19, lftp output parser
        queue: list[LftpJobStatus] = []

        queue_done_m = re.compile(LftpJobStatusParser.__QUEUE_DONE_REGEX)
        if len(lines) == 1:
            if not queue_done_m.match(lines[0]):
                # Single unrecognized line - might be empty output, skip gracefully
                return queue
            lines.pop(0)

        if lines:
            # Look for the header lines
            if len(lines) < 2:
                # Not enough lines for a valid queue header - return empty queue
                return queue
            header1_pattern = rf"^\[\d+\] queue \(sftp://.*@.*\)(?:\s+--\s+(?:\d+\.\d+|\d+)\s({LftpJobStatusParser.__SIZE_UNITS_REGEX})\/s)?$"
            header2_pattern = "^sftp://.*@.*$"
            line = lines.pop(0)
            if not re.match(header1_pattern, line):
                # First line doesn't match queue header - no active queue, return empty
                # Put the line back for __parse_jobs to handle
                lines.insert(0, line)
                return queue
            line = lines.pop(0)
            if not re.match(header2_pattern, line):
                # Second line doesn't match - malformed but not fatal, return empty queue
                lines.insert(0, line)
                return queue
            if not lines:
                raise ValueError("Missing queue status")

            # Look for 'Now executing' lines. Peek rather than unconditionally
            # pop: if neither status line is present (e.g. 'Commands queued:'
            # follows the header directly), the status line must be left in
            # place for the 'Commands queued:' check below.
            if lines and re.match("Queue is stopped.", lines[0]):
                # Nothing to do
                lines.pop(0)
            elif lines and re.match("Now executing:", lines[0]):
                lines.pop(0)
                # Remove any more lines associated with 'now executing'
                while lines and re.match(r"^-\[\d+\]", lines[0]):
                    lines.pop(0)

            # Look for the actual queue
            if lines and re.match("Commands queued:", lines[0]):
                lines.pop(0)
                if not lines:
                    raise ValueError("Missing queued commands")

                # Parse the queued commands
                queue_pget_pattern = (
                    r"^(?P<id>\d+)\.\s+"
                    r"pget\s+"
                    r"(?P<flags>.*?)\s+"
                    r"(?P<lq>[\'\"]|)(?P<remote>.+)(?P=lq)\s+"  # greedy on purpose
                    r"(?:-o\s+)"
                    r"(?P<rq>[\'\"]|)(?P<local>.+)(?P=rq)$"
                )  # greedy on purpose
                queue_pget_m = re.compile(queue_pget_pattern)
                queue_mirror_pattern = (
                    r"^(?P<id>\d+)\.\s+"
                    r"mirror\s+"
                    r"(?P<flags>.*?)\s+"
                    r"(?P<lq>[\'\"]|)(?P<remote>.+)(?P=lq)\s+"  # greedy on purpose
                    r"(?P<rq>[\'\"]|)(?P<local>.+)(?P=rq)$"
                )  # greedy on purpose
                queue_mirror_m = re.compile(queue_mirror_pattern)
                while lines:
                    line = lines[0]
                    if re.match(r"^\d+\.", line):
                        # header line
                        lines.pop(0)

                        result_pget = queue_pget_m.match(line)
                        result_mirror = queue_mirror_m.match(line)
                        if result_pget:
                            type_ = LftpJobStatus.Type.PGET
                            result = result_pget
                        elif result_mirror:
                            type_ = LftpJobStatus.Type.MIRROR
                            result = result_mirror
                        else:
                            raise ValueError(f"Failed to parse queue line: {line}")
                        id_ = int(result.group("id"))
                        name = os.path.basename(os.path.normpath(result.group("remote")))
                        flags = result.group("flags")
                        status = LftpJobStatus(
                            job_id=id_, job_type=type_, state=LftpJobStatus.State.QUEUED, name=name, flags=flags
                        )
                        queue.append(status)
                    elif re.match(r"^cd\s.*$", line):
                        # 'cd' line after pget, ignore
                        lines.pop(0)
                    else:
                        # no match, exit loop
                        break

            # Look for the done line
            if lines and queue_done_m.match(lines[0]):
                lines.pop(0)

        return queue
