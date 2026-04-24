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
from .extract import ExtractProcess, ExtractStatus, ExtractStatusResult
from .model_registry import ModelRegistry
from .pair_context import PairContext
from .persist_keys import KEY_SEP, persist_key, strip_persist_key
from .validate import ValidateProcess, ValidateRequest, ValidateStatusResult


class ModelUpdater:
    """Runs the per-cycle model-update loop.

    All methods preserve the exact logic from their original Controller
    counterparts — this is a structural extraction, not a refactor.
    """

    def __init__(
        self,
        pair_contexts: list[PairContext],
        persist: ControllerPersist,
        pipeline: CommandPipeline,
        registry: ModelRegistry,
        extract_process: ExtractProcess,
        validate_process: ValidateProcess,
        context: Context,
        password: str | None,
        logger: logging.Logger,
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

    def update(self):  # noqa: C901 — will be decomposed in #394
        # Grab the latest extract results (shared)
        latest_extract_statuses = self._extract_process.pop_latest_statuses()
        latest_extracted_results = self._extract_process.pop_completed()
        latest_failed_extractions = self._extract_process.pop_failed()

        # Grab the latest validate results (shared)
        latest_validate_statuses = self._validate_process.pop_latest_statuses()
        latest_validated_results = self._validate_process.pop_completed()
        latest_failed_validations = self._validate_process.pop_failed()

        # Process each pair context's scan results and LFTP status
        for pc in self._pair_contexts:
            self._update_pair_model_state(pc, latest_extract_statuses, latest_validate_statuses)

        # Process extraction completions once (shared across all pairs)
        if latest_extracted_results:
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

        # Build an aggregate new model from all pairs
        any_pair_has_changes = any(pc.model_builder.has_changes() for pc in self._pair_contexts)

        if any_pair_has_changes:
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

            model_diff = self._registry.apply_diff(new_model)

            for diff in model_diff:
                diff_file = diff.new_file or diff.old_file
                assert diff_file is not None
                pc = self._pipeline.get_pair_context_for_file(diff_file)

                if diff.new_file is not None and diff.new_file.state in (
                    ModelFile.State.QUEUED,
                    ModelFile.State.DOWNLOADING,
                ):
                    pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
                    self._pipeline.moved_file_keys.discard(pkey)
                    self._persist.downloaded_file_names.discard(pkey)
                    self._persist.extracted_file_names.discard(pkey)
                    self._persist.extract_failed_file_names.discard(pkey)
                    self._persist.validated_file_names.discard(pkey)
                    self._persist.corrupt_file_names.discard(pkey)
                    self.sync_persist_to_all_builders()

                downloaded = False
                if (
                    diff.change == ModelDiff.Change.ADDED
                    and diff.new_file is not None
                    and diff.new_file.state == ModelFile.State.DOWNLOADED
                ) or (
                    diff.change == ModelDiff.Change.UPDATED
                    and diff.new_file is not None
                    and diff.new_file.state == ModelFile.State.DOWNLOADED
                    and diff.old_file is not None
                    and diff.old_file.state != ModelFile.State.DOWNLOADED
                ):
                    downloaded = True
                if downloaded:
                    assert diff.new_file is not None
                    assert pc is not None
                    pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
                    self._persist.downloaded_file_names.add(pkey)
                    self.sync_persist_to_all_builders()

                    # Auto-validate if enabled
                    if (
                        self._context.config.validate.enabled
                        and self._context.config.validate.auto_validate
                        and diff.new_file.remote_size is not None
                    ):
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
                        will_auto_validate = (
                            self._context.config.validate.enabled
                            and self._context.config.validate.auto_validate
                            and diff.new_file.remote_size is not None
                        )
                        if not will_auto_extract and not will_auto_validate:
                            self._pipeline.spawn_move_process(diff.new_file.name, pc)

                if diff.new_file is not None and pc is not None and diff.new_file.name in pc.pending_completion:
                    use_staging = (
                        self._context.config.controller.use_staging and self._context.config.controller.staging_path
                    )
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
                    else:
                        if diff.new_file.state in (
                            ModelFile.State.DOWNLOADED,
                            ModelFile.State.EXTRACTED,
                            ModelFile.State.EXTRACT_FAILED,
                            ModelFile.State.VALIDATED,
                            ModelFile.State.CORRUPT,
                            ModelFile.State.DELETED,
                        ):
                            pc.pending_completion.discard(diff.new_file.name)

        # Prune the extracted files list of any files that were deleted locally
        remove_extracted_keys: set[str] = set()
        for pkey in self._persist.extracted_file_names:
            # Find the file in the model by checking each pair
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

        # Persist cleanup: remove entries for files absent from all sources
        all_scans_received = all(_pc.remote_scan_received and _pc.local_scan_received for _pc in self._pair_contexts)
        if all_scans_received:
            # Build a set of all composite keys present in the model
            model_keys: set[str] = set()
            for f in self._registry.get_all_files():
                model_keys.add(persist_key(f.pair_id, f.name))
            absent_keys: set[str] = set()
            for pkey in self._persist.downloaded_file_names:
                if pkey not in model_keys and pkey not in self._pipeline.moved_file_keys:
                    absent_keys.add(pkey)
            if absent_keys:
                self._logger.info(f"Persist cleanup (both absent): {absent_keys}")
                self._persist.downloaded_file_names.difference_update(absent_keys)
                self._persist.extracted_file_names.difference_update(absent_keys)
                self._persist.extract_failed_file_names.difference_update(absent_keys)
                self._persist.validated_file_names.difference_update(absent_keys)
                self._persist.corrupt_file_names.difference_update(absent_keys)
                self.sync_persist_to_all_builders()

        # Process extraction failures — mark as failed immediately
        for result in latest_failed_extractions:
            self._logger.error(f"Extraction failed for '{result.name}'")
            fail_key = persist_key(result.pair_id, result.name)
            self._persist.extract_failed_file_names.add(fail_key)
            self.sync_persist_to_all_builders()

        # Process validation completions — mark as validated
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
                # Checksum mismatch — mark as corrupt
                self._persist.corrupt_file_names.add(pkey)
                self._persist.validated_file_names.discard(pkey)
                self.sync_persist_to_all_builders()
            else:
                # Non-mismatch failure (SSH error, etc.) — don't mark corrupt,
                # just log so the user can retry
                self._logger.warning(
                    f"Validation error for '{result.name}' (not marking corrupt): {result.error_message}"
                )
            # Spawn deferred move regardless of failure type — validation is done
            self._pipeline.spawn_deferred_move(result.pair_id, result.name)

        # Update the controller status (use most recent across all pairs)
        for pc in self._pair_contexts:
            if pc._latest_remote_scan is not None:  # type: ignore[reportPrivateUsage]
                current = self._context.status.controller.latest_remote_scan_time
                if current is None or pc._latest_remote_scan.timestamp > current:  # type: ignore[reportPrivateUsage]
                    self._context.status.controller.latest_remote_scan_time = pc._latest_remote_scan.timestamp  # type: ignore[reportPrivateUsage]
                    self._context.status.controller.latest_remote_scan_failed = pc._latest_remote_scan.failed  # type: ignore[reportPrivateUsage]
                    self._context.status.controller.latest_remote_scan_error = pc._latest_remote_scan.error_message  # type: ignore[reportPrivateUsage]
            if pc._latest_local_scan is not None:  # type: ignore[reportPrivateUsage]
                current = self._context.status.controller.latest_local_scan_time
                if current is None or pc._latest_local_scan.timestamp > current:  # type: ignore[reportPrivateUsage]
                    self._context.status.controller.latest_local_scan_time = pc._latest_local_scan.timestamp  # type: ignore[reportPrivateUsage]

    def _update_pair_model_state(  # noqa: C901 — will be decomposed in #394
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

        pc._latest_remote_scan = latest_remote_scan  # type: ignore[reportPrivateUsage]
        pc._latest_local_scan = latest_local_scan  # type: ignore[reportPrivateUsage]

        lftp_statuses = None
        try:
            lftp_statuses = pc.lftp.status()
        except LftpError as e:
            self._logger.warning(f"Caught lftp error (pair {pc.name}): {e!s}")

        if latest_remote_scan is not None:
            pc.remote_scan_received = True
        if latest_local_scan is not None:
            pc.local_scan_received = True

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

    def sync_persist_to_all_builders(self):
        """Push current persist state to all pair model builders, filtered by pair_id."""
        namespaced_prefixes = tuple(
            f"{other_pc.pair_id}{sep}" for other_pc in self._pair_contexts if other_pc.pair_id for sep in (KEY_SEP, ":")
        )
        for pc in self._pair_contexts:
            pc.model_builder.set_downloaded_files(
                self._filter_keys_for_pair(self._persist.downloaded_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_extracted_files(
                self._filter_keys_for_pair(self._persist.extracted_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_extract_failed_files(
                self._filter_keys_for_pair(self._persist.extract_failed_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_validated_files(
                self._filter_keys_for_pair(self._persist.validated_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_corrupt_files(
                self._filter_keys_for_pair(self._persist.corrupt_file_names, pc.pair_id, namespaced_prefixes)
            )

    @staticmethod
    def _filter_keys_for_pair(keys: set[str], pair_id: str | None, namespaced_prefixes: tuple[str, ...]) -> set[str]:
        """Filter and strip persist keys that belong to a specific pair.

        For pairs with a pair_id, matches keys with the current separator or
        legacy colon prefix. For the default pair (pair_id=None), matches keys
        that don't start with any other pair's prefix.
        """
        result: set[str] = set()
        if pair_id:
            prefix = f"{pair_id}{KEY_SEP}"
            legacy_prefix = f"{pair_id}:"
            for key in keys:
                if key.startswith(prefix):
                    result.add(key[len(prefix) :])
                elif key.startswith(legacy_prefix):
                    result.add(key[len(legacy_prefix) :])
        else:
            for key in keys:
                if not key.startswith(namespaced_prefixes):
                    result.add(key)
        return result
