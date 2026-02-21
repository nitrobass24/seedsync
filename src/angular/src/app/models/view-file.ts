/**
 * View file - represents the View Model.
 */
export interface ViewFile {
  name: string;
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
  isQueueable: boolean;
  isStoppable: boolean;
  /** Whether file can be queued for extraction (independent of isArchive). */
  isExtractable: boolean;
  isLocallyDeletable: boolean;
  isRemotelyDeletable: boolean;
  localCreatedTimestamp: Date | null;
  localModifiedTimestamp: Date | null;
  remoteCreatedTimestamp: Date | null;
  remoteModifiedTimestamp: Date | null;
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
}
