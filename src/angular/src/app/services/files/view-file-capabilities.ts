import { ModelFileState } from '../../models/model-file';
import { ViewFileStatus } from '../../models/view-file';

/**
 * Pure status/capability state machine for view files.
 *
 * This is the single source of truth for:
 *  - mapping a backend {@link ModelFileState} to a {@link ViewFileStatus}, and
 *  - deriving the six action-capability flags + the validate tooltip from a
 *    status and the file's sizes.
 *
 * The allow-lists below are named constants so each set of eligible statuses
 * is declared exactly once (the deletion/extraction lists used to be duplicated
 * copy-paste arrays kept in sync by hand — issue #524 part 2).
 */

/** Statuses from which a file can be (re-)queued for download. */
export const QUEUEABLE_STATUSES: readonly ViewFileStatus[] = [
  ViewFileStatus.DEFAULT,
  ViewFileStatus.STOPPED,
  ViewFileStatus.DELETED,
];

/** Statuses from which an in-flight transfer can be stopped. */
export const STOPPABLE_STATUSES: readonly ViewFileStatus[] = [
  ViewFileStatus.QUEUED,
  ViewFileStatus.DOWNLOADING,
];

/**
 * Statuses that permit local-side actions (extraction and local deletion).
 * Both isExtractable and isLocallyDeletable gate on this verbatim list.
 */
export const LOCAL_ACTION_STATUSES: readonly ViewFileStatus[] = [
  ViewFileStatus.DEFAULT,
  ViewFileStatus.STOPPED,
  ViewFileStatus.DOWNLOADED,
  ViewFileStatus.EXTRACTED,
  ViewFileStatus.EXTRACT_FAILED,
  ViewFileStatus.VALIDATED,
  ViewFileStatus.CORRUPT,
];

/** Statuses from which the remote copy can be deleted. */
export const REMOTELY_DELETABLE_STATUSES: readonly ViewFileStatus[] = [
  ViewFileStatus.DEFAULT,
  ViewFileStatus.STOPPED,
  ViewFileStatus.DOWNLOADED,
  ViewFileStatus.EXTRACTED,
  ViewFileStatus.EXTRACT_FAILED,
  ViewFileStatus.VALIDATED,
  ViewFileStatus.CORRUPT,
  ViewFileStatus.DELETED,
];

/** Statuses from which a checksum validation can be requested. */
export const VALIDATABLE_STATUSES: readonly ViewFileStatus[] = [
  ViewFileStatus.DOWNLOADED,
  ViewFileStatus.EXTRACTED,
  ViewFileStatus.EXTRACT_FAILED,
  ViewFileStatus.VALIDATED,
  ViewFileStatus.CORRUPT,
];

export const VALIDATE_UNAVAILABLE_TOOLTIP = 'Remote file not available for checksum comparison';

/**
 * The six capability flags plus the validate tooltip derived for a view file.
 */
export interface ViewFileCapabilities {
  isQueueable: boolean;
  isStoppable: boolean;
  isExtractable: boolean;
  isLocallyDeletable: boolean;
  isRemotelyDeletable: boolean;
  isValidatable: boolean;
  validateTooltip: string | null;
}

/**
 * Map a backend model-file state to the view status.
 *
 * The only non-1:1 case is DEFAULT: a file in DEFAULT with both a local and a
 * remote size present is a partially-downloaded file that was stopped, so it
 * surfaces as STOPPED. Unknown states fall through to DEFAULT.
 *
 * @param state the backend model-file state
 * @param localSize coalesced (non-null) local size in bytes
 * @param remoteSize coalesced (non-null) remote size in bytes
 */
export function mapState(state: ModelFileState, localSize: number, remoteSize: number): ViewFileStatus {
  switch (state) {
    case ModelFileState.DEFAULT:
      return localSize > 0 && remoteSize > 0 ? ViewFileStatus.STOPPED : ViewFileStatus.DEFAULT;
    case ModelFileState.QUEUED:
      return ViewFileStatus.QUEUED;
    case ModelFileState.DOWNLOADING:
      return ViewFileStatus.DOWNLOADING;
    case ModelFileState.DOWNLOADED:
      return ViewFileStatus.DOWNLOADED;
    case ModelFileState.DELETED:
      return ViewFileStatus.DELETED;
    case ModelFileState.EXTRACTING:
      return ViewFileStatus.EXTRACTING;
    case ModelFileState.EXTRACTED:
      return ViewFileStatus.EXTRACTED;
    case ModelFileState.EXTRACT_FAILED:
      return ViewFileStatus.EXTRACT_FAILED;
    case ModelFileState.VALIDATING:
      return ViewFileStatus.VALIDATING;
    case ModelFileState.VALIDATED:
      return ViewFileStatus.VALIDATED;
    case ModelFileState.CORRUPT:
      return ViewFileStatus.CORRUPT;
    default:
      return ViewFileStatus.DEFAULT;
  }
}

/**
 * Derive the action-capability flags and validate tooltip for a view file.
 *
 * isValidatable and validateTooltip key off the RAW nullable sizes
 * (`modelFile.local_size`/`modelFile.remote_size`), not the coalesced numeric
 * sizes — a file can be validatable only when both sizes are actually known,
 * and the "remote not available" tooltip is shown specifically when the remote
 * size is null. The other flags gate on the coalesced numeric sizes.
 *
 * @param status the resolved view status
 * @param localSize coalesced (non-null) local size in bytes
 * @param remoteSize coalesced (non-null) remote size in bytes
 * @param localSizeRaw the raw, possibly-null local size from the model file
 * @param remoteSizeRaw the raw, possibly-null remote size from the model file
 */
export function deriveCapabilities(
  status: ViewFileStatus,
  localSize: number,
  remoteSize: number,
  localSizeRaw: number | null,
  remoteSizeRaw: number | null,
): ViewFileCapabilities {
  const isQueueable =
    (QUEUEABLE_STATUSES.includes(status) && remoteSize > 0) || status === ViewFileStatus.CORRUPT;
  const isStoppable = STOPPABLE_STATUSES.includes(status);
  const isExtractable = LOCAL_ACTION_STATUSES.includes(status) && localSize > 0;
  const isLocallyDeletable = LOCAL_ACTION_STATUSES.includes(status) && localSize > 0;
  const isRemotelyDeletable = REMOTELY_DELETABLE_STATUSES.includes(status) && remoteSize > 0;
  const isValidatable =
    VALIDATABLE_STATUSES.includes(status) && localSizeRaw != null && remoteSizeRaw != null;

  let validateTooltip: string | null = null;
  if (!isValidatable && VALIDATABLE_STATUSES.includes(status) && remoteSizeRaw == null) {
    validateTooltip = VALIDATE_UNAVAILABLE_TOOLTIP;
  }

  return {
    isQueueable,
    isStoppable,
    isExtractable,
    isLocallyDeletable,
    isRemotelyDeletable,
    isValidatable,
    validateTooltip,
  };
}
