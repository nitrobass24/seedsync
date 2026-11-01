/**
 * View file - represents the View Model.
 */
export interface ViewFile {
  name: string;
  pairId: string | null;
  pairName: string | null;
  isDir: boolean;
  localSize: number;
  remoteSize: number;
  percentDownloaded: number;
  status: ViewFileStatus;
  downloadingSpeed: number;
  eta: number;
  fullPath: string;
  isArchive: boolean;
  isSelected: boolean;
  isChecked: boolean;
  /** Whether some (but not all) of this folder's descendants (any depth) are checked. */
  isIndeterminate: boolean;
  isQueueable: boolean;
  isStoppable: boolean;
  /** Whether file can be queued for extraction (independent of isArchive). */
  isExtractable: boolean;
  isLocallyDeletable: boolean;
  isRemotelyDeletable: boolean;
  /** Whether folder has local-only content (exists locally but not remotely) that can be cleaned up. */
  isCleanupLocalable: boolean;
  /** Whether this folder (at any depth) has a descendant independently Queued/Downloading. */
  hasDownloadingDescendant: boolean;
  isValidatable: boolean;
  validateTooltip: string | null;
  localCreatedTimestamp: Date | null;
  localModifiedTimestamp: Date | null;
  remoteCreatedTimestamp: Date | null;
  remoteModifiedTimestamp: Date | null;
  /** Nested children, only populated/rendered when nested navigation is enabled. */
  children: ViewFile[];
}

export enum ViewFileStatus {
  DEFAULT      = 'default',
  QUEUED       = 'queued',
  DOWNLOADING  = 'downloading',
  DOWNLOADED   = 'downloaded',
  STOPPED      = 'stopped',
  DELETED      = 'deleted',
  EXTRACTING      = 'extracting',
  EXTRACTED       = 'extracted',
  EXTRACT_FAILED  = 'extract_failed',
  VALIDATING      = 'validating',
  VALIDATED       = 'validated',
  CORRUPT         = 'corrupt',
  MOVE_FAILED     = 'move_failed',
}
