# Copyright 2017, Inderpreet Singh, All rights reserved.

import fnmatch
import json
from abc import ABC, abstractmethod
from collections.abc import Callable

from common import Constants, Context, Persist, PersistError, Serializable, overrides
from model import IModelListener, ModelFile

from .controller import Controller


class AutoQueuePattern(Serializable):
    # Keys
    __KEY_PATTERN = "pattern"

    def __init__(self, pattern: str):
        self.__pattern = pattern

    @property
    def pattern(self) -> str:
        return self.__pattern

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AutoQueuePattern):
            return NotImplemented
        return self.__pattern == other.__pattern

    def __hash__(self) -> int:
        return hash(self.__pattern)

    def to_str(self) -> str:
        dct: dict[str, str] = {}
        dct[AutoQueuePattern.__KEY_PATTERN] = self.__pattern
        return json.dumps(dct)

    @classmethod
    def from_str(cls, content: str) -> "AutoQueuePattern":
        dct: dict[str, str] = json.loads(content)
        return AutoQueuePattern(pattern=dct[AutoQueuePattern.__KEY_PATTERN])


# (filename, pair_id, matched_pattern)
_Candidate = tuple[str, str | None, AutoQueuePattern | None]


class IAutoQueuePersistListener(ABC):
    """Listener for receiving AutoQueuePersist events"""

    @abstractmethod
    def pattern_added(self, pattern: AutoQueuePattern):
        pass

    @abstractmethod
    def pattern_removed(self, pattern: AutoQueuePattern):
        pass


class AutoQueuePersist(Persist):
    """
    Persisting state for auto-queue
    """

    # Keys
    __KEY_PATTERNS = "patterns"

    def __init__(self):
        self.__patterns: list[AutoQueuePattern] = []
        self.__listeners: list[IAutoQueuePersistListener] = []

    @property
    def patterns(self) -> set[AutoQueuePattern]:
        return set(self.__patterns)

    def add_pattern(self, pattern: AutoQueuePattern):
        # Check values
        if not pattern.pattern.strip():
            raise ValueError("Cannot add blank pattern")

        if pattern not in self.__patterns:
            self.__patterns.append(pattern)
            for listener in self.__listeners:
                listener.pattern_added(pattern)

    def remove_pattern(self, pattern: AutoQueuePattern):
        if pattern in self.__patterns:
            self.__patterns.remove(pattern)
            for listener in self.__listeners:
                listener.pattern_removed(pattern)

    def add_listener(self, listener: IAutoQueuePersistListener):
        self.__listeners.append(listener)

    @classmethod
    @overrides(Persist)
    def from_str(cls: type["AutoQueuePersist"], content: str) -> "AutoQueuePersist":
        persist = cls()
        try:
            dct = json.loads(content)
            pattern_list = dct[AutoQueuePersist.__KEY_PATTERNS]
            for pattern in pattern_list:
                persist.add_pattern(AutoQueuePattern.from_str(pattern))
            return persist
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise PersistError("Error parsing AutoQueuePersist - {}: {}".format(type(e).__name__, str(e)))

    @overrides(Persist)
    def to_str(self) -> str:
        dct: dict[str, list[str]] = {}
        dct[AutoQueuePersist.__KEY_PATTERNS] = list(p.to_str() for p in self.__patterns)
        return json.dumps(dct, indent=Constants.JSON_PRETTY_PRINT_INDENT)


class AutoQueueModelListener(IModelListener):
    """Keeps track of added and modified files"""

    def __init__(self):
        self.new_files: list[ModelFile] = []
        self.modified_files: list[tuple[ModelFile, ModelFile]] = []

    @overrides(IModelListener)
    def file_added(self, file: ModelFile):
        self.new_files.append(file)

    @overrides(IModelListener)
    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        self.modified_files.append((old_file, new_file))

    @overrides(IModelListener)
    def file_removed(self, file: ModelFile):
        pass


class AutoQueuePersistListener(IAutoQueuePersistListener):
    """Keeps track of newly added patterns"""

    def __init__(self):
        self.new_patterns: set[AutoQueuePattern] = set()

    @overrides(IAutoQueuePersistListener)
    def pattern_added(self, pattern: AutoQueuePattern):
        self.new_patterns.add(pattern)

    @overrides(IAutoQueuePersistListener)
    def pattern_removed(self, pattern: AutoQueuePattern):
        if pattern in self.new_patterns:
            self.new_patterns.remove(pattern)


class AutoQueue:
    """
    Implements auto-queue functionality by sending commands to controller
    as matching files are discovered
    AutoQueue is in the same thread as Controller, so no synchronization is
    needed for now
    """

    def __init__(self, context: Context, persist: AutoQueuePersist, controller: Controller):
        self.logger = context.logger.getChild("AutoQueue")
        self.__persist = persist
        self.__controller = controller
        self.__model_listener = AutoQueueModelListener()
        self.__persist_listener = AutoQueuePersistListener()
        self.__patterns_only = context.config.autoqueue.patterns_only
        self.__auto_extract_enabled = context.config.autoqueue.auto_extract
        self.__auto_delete_remote_enabled = context.config.autoqueue.auto_delete_remote
        self.__delete_remote_retry_cycles: dict[tuple[str, str | None], int] = {}

        # Build per-pair auto_queue lookup.
        # When path pairs are active, per-pair auto_queue overrides the global setting.
        path_pairs_config = getattr(context, "path_pairs_config", None)
        enabled_pairs = [p for p in path_pairs_config.pairs if p.enabled] if path_pairs_config else []
        if enabled_pairs:
            self.__pair_auto_queue: dict[str, bool] = {p.id: p.auto_queue for p in enabled_pairs}
            self.__enabled = any(p.auto_queue for p in enabled_pairs)
        else:
            self.__pair_auto_queue = {}
            self.__enabled = context.config.autoqueue.enabled

        # Register listeners if ANY auto feature is active (auto-queue, auto-extract,
        # or auto-delete-remote). Previously, all features were gated behind __enabled,
        # meaning auto_delete_remote wouldn't fire when auto-queue was disabled.
        any_auto_feature = self.__enabled or self.__auto_extract_enabled or self.__auto_delete_remote_enabled
        if any_auto_feature:
            persist.add_listener(self.__persist_listener)

            initial_model_files = self.__controller.get_model_files_and_add_listener(self.__model_listener)
            # pass the initial model files through to our listener
            for file in initial_model_files:
                self.__model_listener.file_added(file)

            # Print the initial persist state
            self.logger.debug("Auto-Queue Patterns:")
            for pattern in self.__persist.patterns:
                self.logger.debug("    {}".format(pattern.pattern))

    def process(self):
        """
        Advance the auto queue state
        :return:
        """
        # Skip entirely if no auto features are active
        any_auto_feature = self.__enabled or self.__auto_extract_enabled or self.__auto_delete_remote_enabled
        if not any_auto_feature:
            return

        files_to_queue = self.__gather_queue_candidates() if self.__enabled else []
        files_to_extract = self.__gather_extract_candidates() if self.__auto_extract_enabled else []
        files_to_delete_remote = self.__gather_delete_remote_candidates() if self.__auto_delete_remote_enabled else []

        # Send commands (order matters: queue, extract, then delete remote)
        self.__send_commands(files_to_queue, Controller.Command.Action.QUEUE, "Auto queueing")
        self.__send_commands(files_to_extract, Controller.Command.Action.EXTRACT, "Auto extracting")
        self.__send_commands(files_to_delete_remote, Controller.Command.Action.DELETE_REMOTE, "Auto deleting remote")

        # Retry delete-remote for DELETED files where remote still exists
        if self.__auto_delete_remote_enabled:
            self.__retry_delete_remote(files_to_delete_remote)

        # Clear the processed files
        self.__model_listener.new_files.clear()
        self.__model_listener.modified_files.clear()
        # Clear the new patterns
        self.__persist_listener.new_patterns.clear()

    def __gather_queue_candidates(self) -> list[_Candidate]:
        candidates: list[ModelFile] = list(self.__model_listener.new_files)
        for old_file, new_file in self.__model_listener.modified_files:
            if old_file.remote_size != new_file.remote_size:
                candidates.append(new_file)
        return self.__filter_candidates(
            candidates=candidates,
            accept=lambda f: (
                f.remote_size is not None
                and f.state == ModelFile.State.DEFAULT
                and self._is_auto_queue_enabled_for_file(f)
            ),
        )

    def __gather_extract_candidates(self) -> list[_Candidate]:
        candidates: list[ModelFile] = list(self.__model_listener.new_files)
        # Candidate modified files that just became DOWNLOADED
        # But not files that went EXTRACTING -> DOWNLOADED (failed extraction)
        for old_file, new_file in self.__model_listener.modified_files:
            if (
                old_file.state != ModelFile.State.DOWNLOADED
                and old_file.state != ModelFile.State.EXTRACTING
                and new_file.state == ModelFile.State.DOWNLOADED
            ):
                candidates.append(new_file)
        return self.__filter_candidates(
            candidates=candidates,
            accept=lambda f: (
                f.state == ModelFile.State.DOWNLOADED
                and f.local_size is not None
                and f.local_size > 0
                and f.is_extractable
            ),
        )

    def __gather_delete_remote_candidates(self) -> list[_Candidate]:
        candidates: list[ModelFile] = list(self.__model_listener.new_files)
        for old_file, new_file in self.__model_listener.modified_files:
            if old_file.state != new_file.state and new_file.state in (
                ModelFile.State.DOWNLOADED,
                ModelFile.State.EXTRACTED,
            ):
                candidates.append(new_file)
        return self.__filter_candidates(
            candidates=candidates,
            accept=lambda f: (
                f.remote_size is not None
                and (
                    f.state == ModelFile.State.EXTRACTED
                    or (
                        f.state == ModelFile.State.DOWNLOADED
                        and (not self.__auto_extract_enabled or not f.is_extractable)
                    )
                )
            ),
        )

    def __send_commands(
        self,
        files: list[_Candidate],
        action: Controller.Command.Action,
        log_prefix: str,
    ) -> None:
        for filename, pair_id, pattern in files:
            self.logger.info(
                "{} '{}'".format(log_prefix, filename)
                + (" for pattern '{}'".format(pattern.pattern) if pattern else "")
            )
            command = Controller.Command(action, filename, pair_id=pair_id)
            self.__controller.queue_command(command)

    def __retry_delete_remote(self, files_to_delete_remote: list[_Candidate]) -> None:
        RETRY_INTERVAL = 20  # cycles between retries
        already_sent = {(name, pid) for name, pid, _ in files_to_delete_remote}
        model_files = self.__controller.get_model_files()
        new_retry_cycles: dict[tuple[str, str | None], int] = {}
        for file in model_files:
            if file.state == ModelFile.State.DELETED and file.remote_size is not None:
                retry_key = (file.name, file.pair_id)
                count = self.__delete_remote_retry_cycles.get(retry_key, RETRY_INTERVAL)
                if retry_key not in already_sent and count >= RETRY_INTERVAL:
                    command = Controller.Command(
                        Controller.Command.Action.DELETE_REMOTE, file.name, pair_id=file.pair_id
                    )
                    self.__controller.queue_command(command)
                    new_retry_cycles[retry_key] = 0
                else:
                    new_retry_cycles[retry_key] = count + 1
        self.__delete_remote_retry_cycles = new_retry_cycles

    def _is_auto_queue_enabled_for_file(self, file: ModelFile) -> bool:
        """Check if auto-queue is enabled for a specific file based on its pair_id.

        When per-pair overrides are active (__pair_auto_queue is non-empty),
        files with a None pair_id are treated as not auto-queued (the dict
        lookup returns False for None keys). This is intentional: files
        without a pair_id don't belong to any enabled pair.

        When no path pairs are active, returns True unconditionally — the
        caller (process()) already gates on the global __enabled flag.
        """
        if self.__pair_auto_queue:
            if file.pair_id is None:
                return False
            return self.__pair_auto_queue.get(file.pair_id, False)
        return True

    def __filter_candidates(self, candidates: list[ModelFile], accept: Callable[[ModelFile], bool]) -> list[_Candidate]:
        """
        Given a list of candidate files, filter out those that match the accept criteria
        Also takes into consideration new patterns that were added
        The accept criteria is applied to candidates AND all existing files in case of
        new patterns
        :param candidates:
        :param accept:
        :return: list of (filename, pair_id, pattern) tuples
        """
        # Files accepted and matched, (name, pair_id) -> pattern map
        # Composite key prevents a file from being accepted twice
        files_matched: dict[tuple[str, str | None], AutoQueuePattern | None] = {}

        # Step 1: run candidates through all the patterns if they are enabled
        #         otherwise accept all files
        for file in candidates:
            if self.__patterns_only:
                for pattern in self.__persist.patterns:
                    if accept(file) and self.__match(pattern, file):
                        files_matched[(file.name, file.pair_id)] = pattern
                        break
            elif accept(file):
                files_matched[(file.name, file.pair_id)] = None

        # Step 2: run new pattern through all the files
        if self.__persist_listener.new_patterns:
            model_files = self.__controller.get_model_files()
            for new_pattern in self.__persist_listener.new_patterns:
                for file in model_files:
                    if accept(file) and self.__match(new_pattern, file):
                        files_matched[(file.name, file.pair_id)] = new_pattern

        return [(name, pair_id, pattern) for (name, pair_id), pattern in files_matched.items()]

    @staticmethod
    def __match(pattern: AutoQueuePattern, file: ModelFile) -> bool:
        """
        Returns true is file matches the pattern
        :param pattern:
        :param file:
        :return:
        """
        # make the search case insensitive
        pattern_str = pattern.pattern.lower()
        filename = file.name.lower()
        # 1. pattern match
        # 2. wildcard match
        return pattern_str in filename or fnmatch.fnmatch(filename, pattern_str)
