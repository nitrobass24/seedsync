# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Model update logic: scan processing, diff application, and persist sync.

Owns the per-cycle model-update loop that was formerly Controller.__update_model.
Extracted from controller.py as part of the controller decomposition
(#394 Phase 3F).
"""

from __future__ import annotations

import logging
import os

from common import Context
from lftp import LftpError, LftpJobStatus
from model import Model, ModelDiff, ModelError, ModelFile

from .command_pipeline import CommandPipeline
from .controller_persist import ControllerPersist
from .exclude_patterns import filter_excluded_files
from .extract import ExtractCompletedResult, ExtractFailedResult, ExtractProcess, ExtractStatus, ExtractStatusResult
from .model_registry import ModelRegistry
from .pair_context import PairContext
from .persist_keys import persist_key, strip_persist_key
from .persist_sync import PersistSync
from .validate import (
    ValidateCompletedResult,
    ValidateFailedResult,
    ValidateProcess,
    ValidateRequest,
    ValidateStatusResult,
)
from .worker_supervisor import WorkerSupervisor


class ModelUpdater:
    """Runs the per-cycle model-update loop.

    All methods preserve the exact logic from their original Controller
    counterparts — this is a structural extraction, not a refactor.
    """

    # Bound the in-session staging->final move retry so a permanently-failing
    # move does not re-spawn on every cycle forever (#536).
    MAX_MOVE_RETRIES = 3

    def __init__(
        self,
        pair_contexts: list[PairContext],
        persist: ControllerPersist,
        pipeline: CommandPipeline,
        registry: ModelRegistry,
        extract_process: WorkerSupervisor[ExtractProcess],
        validate_process: WorkerSupervisor[ValidateProcess],
        context: Context,
        password: str | None,
        logger: logging.Logger,
        persist_sync: PersistSync | None = None,
    ):
        self._pair_contexts = pair_contexts
        self._persist = persist
        self._pipeline = pipeline
        self._registry = registry
        self._extract_process = extract_process
        self._validate_process = validate_process
        self._context = context
        self._password = password
        self._logger = logger
        # Share the same PersistSync instance with the CommandPipeline when one
        # is injected; otherwise build one over the same pair_contexts/persist so
        # standalone use (and unit tests) behaves identically.
        self._persist_sync = persist_sync or PersistSync(pair_contexts, persist)
        # In-memory per-file budget for the in-session staging->final move retry
        # (#536). Keyed by persist key; bounded by MAX_MOVE_RETRIES so a
        # permanently-failing move (e.g. a full disk) does not re-spawn forever.
        # Held in memory only, so a restart grants a fresh budget.
        self._move_retry_counts: dict[str, int] = {}

    def update(self) -> None:
        # Grab the latest extract results. Completed/failed go through the
        # supervisor (not .worker) so results buffered from a dead worker during
        # recreation are surfaced exactly once (#571); statuses are display-only
        # and read straight off the live worker.
        latest_extract_statuses = self._extract_process.worker.pop_latest_statuses()
        latest_extracted_results = self._extract_process.pop_completed()
        latest_failed_extractions = self._extract_process.pop_failed()

        # Grab the latest validate results (same #571 contract as extract).
        latest_validate_statuses = self._validate_process.worker.pop_latest_statuses()
        latest_validated_results = self._validate_process.pop_completed()
        latest_failed_validations = self._validate_process.pop_failed()

        # Process each pair context's scan results and LFTP status
        for pc in self._pair_contexts:
            self._update_pair_model_state(pc, latest_extract_statuses, latest_validate_statuses)

        self._process_extraction_completions(latest_extracted_results)

        new_model = self._build_aggregate_model()
        if new_model is not None:
            model_diff = self._registry.apply_diff(new_model)
            self._process_model_diffs(model_diff)

        self._prune_stale_persist()
        self._process_extraction_failures(latest_failed_extractions)
        self._process_validation_results(latest_validated_results, latest_failed_validations)
        self._retry_failed_moves()
        self._update_controller_status()

    def _process_extraction_completions(self, latest_extracted_results: list[ExtractCompletedResult]) -> None:
        """Process extraction completions once (shared across all pairs)."""
        if not latest_extracted_results:
            return
        for result in latest_extracted_results:
            owner_pc = self._pipeline.find_pair_by_id(result.pair_id)
            if owner_pc is None:
                self._logger.warning(
                    f"Ignoring extract completion for '{result.name}': pair '{result.pair_id}' no longer exists"
                )
                continue
            pkey = persist_key(result.pair_id, result.name)
            self._persist.extracted_file_names.add(pkey)
            if self._context.config.controller.use_staging and self._context.config.controller.staging_path:
                if pkey not in self._pipeline.pending_validation_keys:
                    self._pipeline.spawn_move_process(result.name, owner_pc)
        self.sync_persist_to_all_builders()

    def _build_aggregate_model(self) -> Model | None:
        """Build an aggregate new model from all pairs, or None if no changes."""
        any_pair_has_changes = any(pc.model_builder.has_changes() for pc in self._pair_contexts)
        if not any_pair_has_changes:
            return None

        new_model = Model()
        _dummy = logging.getLogger("dummy")
        _dummy.propagate = False
        new_model.set_base_logger(_dummy)  # silence logs for temp model

        # When multiple pairs share the same local directory, a file that
        # exists only locally (no remote counterpart) would appear in every
        # pair's model.  Deduplicate by scoping per normalized local path:
        #   1) adding all "managed" files first (have a remote, or non-DEFAULT state),
        #   2) then adding local-only files only if no other pair with the
        #      same local directory already claims a file with that name.
        seen_names_by_path: dict[str, set[str]] = {}
        deferred_local_only: list[tuple[ModelFile, str]] = []
        for pc in self._pair_contexts:
            norm_path = os.path.normpath(os.path.abspath(pc.local_path))
            if norm_path not in seen_names_by_path:
                seen_names_by_path[norm_path] = set()
            pair_model = pc.model_builder.build_model()
            for file in pair_model.get_all_files():
                is_local_only = file.remote_size is None and file.state == ModelFile.State.DEFAULT
                if is_local_only:
                    deferred_local_only.append((file, norm_path))
                else:
                    new_model.add_file(file)
                    seen_names_by_path[norm_path].add(file.name)

        for file, norm_path in deferred_local_only:
            if file.name not in seen_names_by_path[norm_path]:
                new_model.add_file(file)
                seen_names_by_path[norm_path].add(file.name)

        return new_model

    def _process_model_diffs(self, model_diff: list[ModelDiff]) -> None:
        """Process each diff: update persist state, auto-validate, staging moves, pending completion."""
        for diff in model_diff:
            diff_file = diff.new_file or diff.old_file
            assert diff_file is not None
            pc = self._pipeline.get_pair_context_for_file(diff_file)

            self._handle_requeued_file(diff)
            self._handle_downloaded_file(diff, pc)
            self._handle_pending_completion(diff, pc)

    def _handle_requeued_file(self, diff: ModelDiff) -> None:
        """Clear persist state when a file goes back to QUEUED/DOWNLOADING."""
        if diff.new_file is not None and diff.new_file.state in (
            ModelFile.State.QUEUED,
            ModelFile.State.DOWNLOADING,
        ):
            pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
            self._pipeline.moved_file_keys.discard(pkey)
            for names in self._persist.all_sets().values():
                names.discard(pkey)
            self._move_retry_counts.pop(pkey, None)
            self.sync_persist_to_all_builders()

    def _handle_downloaded_file(self, diff: ModelDiff, pc: PairContext | None) -> None:
        """Handle a newly downloaded file: persist, auto-validate, staging move."""
        is_newly_downloaded = (
            diff.change == ModelDiff.Change.ADDED
            and diff.new_file is not None
            and diff.new_file.state == ModelFile.State.DOWNLOADED
        ) or (
            diff.change == ModelDiff.Change.UPDATED
            and diff.new_file is not None
            and diff.new_file.state == ModelFile.State.DOWNLOADED
            and diff.old_file is not None
            and diff.old_file.state != ModelFile.State.DOWNLOADED
        )
        if not is_newly_downloaded:
            return

        assert diff.new_file is not None
        assert pc is not None
        pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
        self._persist.downloaded_file_names.add(pkey)
        self.sync_persist_to_all_builders()

        # Auto-validate if enabled
        will_auto_validate = (
            self._context.config.validate.enabled
            and self._context.config.validate.auto_validate
            and diff.new_file.remote_size is not None
        )
        if will_auto_validate:
            req = ValidateRequest(
                name=diff.new_file.name,
                is_dir=diff.new_file.is_dir,
                pair_id=pc.pair_id,
                local_path=pc.effective_local_path,
                remote_path=pc.remote_path,
                algorithm=self._context.config.validate.algorithm,  # type: ignore[arg-type]
                remote_address=self._context.config.lftp.remote_address,  # type: ignore[arg-type]
                remote_username=self._context.config.lftp.remote_username,  # type: ignore[arg-type]
                remote_password=self._password,
                remote_port=self._context.config.lftp.remote_port,  # type: ignore[arg-type]
            )
            self._validate_process.validate(req)
            self._pipeline.pending_validation_keys.add(persist_key(pc.pair_id, diff.new_file.name))
            self._logger.info(f"Auto-queued validation for '{diff.new_file.name}'")

        if self._context.config.controller.use_staging and self._context.config.controller.staging_path:
            will_auto_extract = self._context.config.autoqueue.auto_extract and diff.new_file.is_extractable
            if not will_auto_extract and not will_auto_validate:
                self._pipeline.spawn_move_process(diff.new_file.name, pc)

    def _handle_pending_completion(self, diff: ModelDiff, pc: PairContext | None) -> None:
        """Track pending_completion state for a diff."""
        if diff.new_file is None or pc is None or diff.new_file.name not in pc.pending_completion:
            return
        use_staging = self._context.config.controller.use_staging and self._context.config.controller.staging_path
        # A file with no local presence and DEFAULT state means
        # it was deleted locally (e.g. stopped download whose files
        # were removed). Nothing left to track.
        if diff.new_file.state == ModelFile.State.DEFAULT and diff.new_file.local_size is None:
            pc.pending_completion.discard(diff.new_file.name)
        elif use_staging:
            move_key = persist_key(diff.new_file.pair_id, diff.new_file.name)
            if move_key in self._pipeline.moved_file_keys or diff.new_file.state in (
                ModelFile.State.DELETED,
                ModelFile.State.EXTRACTED,
                ModelFile.State.EXTRACT_FAILED,
                ModelFile.State.VALIDATED,
                ModelFile.State.CORRUPT,
            ):
                pc.pending_completion.discard(diff.new_file.name)
        elif diff.new_file.state in (
            ModelFile.State.DOWNLOADED,
            ModelFile.State.EXTRACTED,
            ModelFile.State.EXTRACT_FAILED,
            ModelFile.State.VALIDATED,
            ModelFile.State.CORRUPT,
            ModelFile.State.DELETED,
        ):
            pc.pending_completion.discard(diff.new_file.name)

    def _prune_stale_persist(self) -> None:
        """Prune extracted files list and remove persist entries for absent files."""
        self._prune_extracted_files()
        self._prune_absent_persist_entries()

    def _prune_extracted_files(self) -> None:
        """Remove extracted-file entries for files that were deleted locally."""
        remove_extracted_keys: set[str] = set()
        for pkey in self._persist.extracted_file_names:
            for _pc in self._pair_contexts:
                bare_name = strip_persist_key(pkey, _pc.pair_id)
                if bare_name != pkey or _pc.pair_id is None:
                    try:
                        file = self._registry.get_file(bare_name, pair_id=_pc.pair_id)
                        if file.state == ModelFile.State.DELETED:
                            remove_extracted_keys.add(pkey)
                    except ModelError:
                        pass
        if remove_extracted_keys:
            self._logger.info(f"Removing from extracted list: {remove_extracted_keys}")
            self._persist.extracted_file_names.difference_update(remove_extracted_keys)
            self.sync_persist_to_all_builders()

    def _prune_absent_persist_entries(self) -> None:
        """Remove persist entries for files absent from all sources."""
        all_scans_received = all(_pc.remote_scan_received and _pc.local_scan_received for _pc in self._pair_contexts)
        if not all_scans_received:
            return
        model_keys: set[str] = set()
        for f in self._registry.get_all_files():
            model_keys.add(persist_key(f.pair_id, f.name))
        absent_keys: set[str] = set()
        for pkey in self._persist.downloaded_file_names:
            if pkey not in model_keys and pkey not in self._pipeline.moved_file_keys:
                absent_keys.add(pkey)
        if absent_keys:
            self._logger.info(f"Persist cleanup (both absent): {absent_keys}")
            for names in self._persist.all_sets().values():
                names.difference_update(absent_keys)
            for key in absent_keys:
                self._move_retry_counts.pop(key, None)
            self.sync_persist_to_all_builders()

    def _process_extraction_failures(self, latest_failed_extractions: list[ExtractFailedResult]) -> None:
        """Process extraction failures -- mark as failed immediately."""
        for result in latest_failed_extractions:
            self._logger.error(f"Extraction failed for '{result.name}'")
            fail_key = persist_key(result.pair_id, result.name)
            self._persist.extract_failed_file_names.add(fail_key)
            self.sync_persist_to_all_builders()

    def _process_validation_results(
        self,
        latest_validated_results: list[ValidateCompletedResult],
        latest_failed_validations: list[ValidateFailedResult],
    ) -> None:
        """Process validation completions and failures."""
        # Process validation completions -- mark as validated
        for result in latest_validated_results:
            self._logger.info(f"Validation passed for '{result.name}'")
            pkey = persist_key(result.pair_id, result.name)
            self._pipeline.pending_validation_keys.discard(pkey)
            self._persist.validated_file_names.add(pkey)
            self._persist.corrupt_file_names.discard(pkey)
            self.sync_persist_to_all_builders()
            # If staging is active, spawn the move process now that validation finished
            self._pipeline.spawn_deferred_move(result.pair_id, result.name)

        # Process validation failures
        for result in latest_failed_validations:
            self._logger.error(f"Validation failed for '{result.name}': {result.error_message}")
            pkey = persist_key(result.pair_id, result.name)
            self._pipeline.pending_validation_keys.discard(pkey)
            if result.is_checksum_mismatch:
                # Checksum mismatch -- mark as corrupt
                self._persist.corrupt_file_names.add(pkey)
                self._persist.validated_file_names.discard(pkey)
                self.sync_persist_to_all_builders()
            else:
                # Non-mismatch failure (SSH error, etc.) -- don't mark corrupt,
                # just log so the user can retry
                self._logger.warning(
                    f"Validation error for '{result.name}' (not marking corrupt): {result.error_message}"
                )
            # Spawn deferred move regardless of failure type -- validation is done
            self._pipeline.spawn_deferred_move(result.pair_id, result.name)

    def _retry_failed_moves(self) -> None:
        """Re-spawn staging->final moves that previously failed, within the session.

        A failed move leaves the file DOWNLOADED-in-staging with its moved key
        discarded (no completed move), so a bare force_scan produces no new
        DOWNLOADED transition and the move would otherwise only retry on restart.
        Each cycle we re-spawn the move for any file still in
        move_failed_file_names that is not already moving, bounded by a per-file
        budget so a permanently-failing move does not re-spawn forever (#536).
        """
        cfg = self._context.config.controller
        if not (cfg.use_staging and cfg.staging_path):
            return
        if not self._persist.move_failed_file_names:
            return
        for fail_key in list(self._persist.move_failed_file_names):
            # Skip files whose move is already in flight (its key is re-added to
            # moved_file_keys by spawn_move_process); we only retry idle ones.
            if fail_key in self._pipeline.moved_file_keys:
                continue
            if self._move_retry_counts.get(fail_key, 0) >= self.MAX_MOVE_RETRIES:
                continue
            self._respawn_failed_move(fail_key)

    def _respawn_failed_move(self, fail_key: str) -> None:
        """Resolve the owning pair for a failed-move key and re-spawn its move."""
        for pc in self._pair_contexts:
            bare_name = strip_persist_key(fail_key, pc.pair_id)
            # strip_persist_key returns the key unchanged when the prefix doesn't
            # match; for the default pair (pair_id None) it always matches, so
            # only treat it as this pair's file when the key is actually scoped to
            # this pair (changed) or this is the default pair.
            if bare_name == fail_key and pc.pair_id is not None:
                continue
            if self._pipeline.spawn_move_process(bare_name, pc):
                self._move_retry_counts[fail_key] = self._move_retry_counts.get(fail_key, 0) + 1
                self._logger.info(
                    f"Retrying failed move for '{bare_name}' (attempt {self._move_retry_counts[fail_key]})"
                )
            elif fail_key in self._persist.move_failed_file_names:
                # Nothing left to move in staging (the move already completed in a
                # prior session, or the staging copy vanished): no real MoveProcess
                # will ever complete to clear this, so resolve it now instead of
                # leaving the file stuck in MOVE_FAILED forever (#536 follow-up).
                self._persist.move_failed_file_names.discard(fail_key)
                self.sync_persist_to_all_builders()
                self._logger.info(f"Cleared MOVE_FAILED for '{bare_name}': nothing to move in staging")
            return

    def _update_controller_status(self) -> None:
        """Update the controller status (use most recent across all pairs).

        Note: remote scans set failed/error fields; local scans don't surface errors.
        """
        for pc in self._pair_contexts:
            if pc.latest_remote_scan is not None:
                current = self._context.status.controller.latest_remote_scan_time
                if current is None or pc.latest_remote_scan.timestamp > current:
                    self._context.status.controller.latest_remote_scan_time = pc.latest_remote_scan.timestamp
                    self._context.status.controller.latest_remote_scan_failed = pc.latest_remote_scan.failed
                    self._context.status.controller.latest_remote_scan_error = pc.latest_remote_scan.error_message
            if pc.latest_local_scan is not None:
                current = self._context.status.controller.latest_local_scan_time
                if current is None or pc.latest_local_scan.timestamp > current:
                    self._context.status.controller.latest_local_scan_time = pc.latest_local_scan.timestamp

    def _update_pair_model_state(
        self,
        pc: PairContext,
        latest_extract_statuses: ExtractStatusResult | None,
        latest_validate_statuses: ValidateStatusResult | None,
    ) -> None:
        """
        Update a single pair context's scan results, LFTP status, and model builder state.
        """
        latest_remote_scan = pc.remote_scan_process.pop_latest_result()
        latest_local_scan = pc.local_scan_process.pop_latest_result()
        latest_active_scan = pc.active_scan_process.pop_latest_result()

        pc.latest_remote_scan = latest_remote_scan
        pc.latest_local_scan = latest_local_scan

        lftp_statuses = None
        try:
            lftp_statuses = pc.lftp.status()
        except LftpError as e:
            self._logger.warning(f"Caught lftp error (pair {pc.name}): {e!s}")

        if latest_remote_scan is not None:
            pc.remote_scan_received = True
        if latest_local_scan is not None:
            pc.local_scan_received = True

        self._detect_lftp_completions(pc, lftp_statuses)

        if latest_extract_statuses is not None:
            # Only include extract statuses for files that belong to this pair
            pc.active_extracting_file_names = [
                s.name
                for s in latest_extract_statuses.statuses
                if s.pair_id == pc.pair_id
                and s.state == ExtractStatus.State.EXTRACTING
                and persist_key(pc.pair_id, s.name) in self._persist.downloaded_file_names
            ]

        active_files = pc.active_downloading_file_names + pc.active_extracting_file_names
        active_files += list(pc.pending_completion)
        pc.active_scanner.set_active_files(active_files)

        pc.model_builder.set_auto_delete_remote(bool(self._context.config.autoqueue.auto_delete_remote))

        if latest_remote_scan is not None:
            remote_files = filter_excluded_files(
                latest_remote_scan.files, self._context.config.general.exclude_patterns
            )
            pc.model_builder.set_remote_files(remote_files)
        if latest_local_scan is not None:
            pc.model_builder.set_local_files(latest_local_scan.files)
        if latest_active_scan is not None:
            pc.model_builder.set_active_files(latest_active_scan.files)
        if lftp_statuses is not None:
            pc.model_builder.set_lftp_statuses(lftp_statuses)
        if latest_extract_statuses is not None:
            pair_statuses = [s for s in latest_extract_statuses.statuses if s.pair_id == pc.pair_id]
            pc.model_builder.set_extract_statuses(pair_statuses)
        if latest_validate_statuses is not None:
            pair_validate_statuses = [s for s in latest_validate_statuses.statuses if s.pair_id == pc.pair_id]
            pc.model_builder.set_validate_statuses(pair_validate_statuses)

    def _detect_lftp_completions(self, pc: PairContext, lftp_statuses: list[LftpJobStatus] | None) -> None:
        """Detect LFTP download completions and update persist/pending state."""
        if lftp_statuses is not None:
            current_downloading = {s.name for s in lftp_statuses if s.state == LftpJobStatus.State.RUNNING}
            just_completed = pc.prev_downloading_file_names - current_downloading
            if just_completed:
                for name in just_completed:
                    self._logger.info(f"Download completed (LFTP job finished): {name}")
                self._persist.downloaded_file_names.update(persist_key(pc.pair_id, n) for n in just_completed)
                self.sync_persist_to_all_builders()
                pc.pending_completion.update(just_completed)
                pc.local_scan_process.force_scan()

            pc.active_downloading_file_names = list(current_downloading)
            pc.prev_downloading_file_names = current_downloading

    def sync_persist_to_all_builders(self):
        """Push current persist state to all pair model builders, filtered by pair_id."""
        self._persist_sync.sync()
