import { ViewFile } from './view-file';

/** The six per-file commands the backend exposes. */
export enum FileAction {
  QUEUE,
  STOP,
  EXTRACT,
  VALIDATE,
  DELETE_LOCAL,
  DELETE_REMOTE
}

export interface FileActionSpec {
  /** URL verb in `/server/command/<verb>/<file>` — a backend contract. */
  readonly urlSegment: string;
  /** Noun used in debug logs ("<noun> model file: ..."). */
  readonly logNoun: string;
  /** Capability flag gating the action for a view file. */
  readonly isAllowed: (file: ViewFile) => boolean;
  /** Max concurrent requests for the bulk variant. */
  readonly bulkConcurrency: number;
}

export const FILE_ACTIONS: Record<FileAction, FileActionSpec> = {
  [FileAction.QUEUE]: {
    urlSegment: 'queue',
    logNoun: 'Queue',
    isAllowed: (f) => f.isQueueable,
    bulkConcurrency: Infinity,
  },
  [FileAction.STOP]: {
    urlSegment: 'stop',
    logNoun: 'Stop',
    isAllowed: (f) => f.isStoppable,
    bulkConcurrency: Infinity,
  },
  [FileAction.EXTRACT]: {
    urlSegment: 'extract',
    logNoun: 'Extract',
    isAllowed: (f) => f.isExtractable && f.isArchive,
    bulkConcurrency: Infinity,
  },
  [FileAction.VALIDATE]: {
    urlSegment: 'validate',
    logNoun: 'Validate',
    isAllowed: (f) => f.isValidatable,
    bulkConcurrency: Infinity,
  },
  [FileAction.DELETE_LOCAL]: {
    urlSegment: 'delete_local',
    logNoun: 'Locally delete',
    isAllowed: (f) => f.isLocallyDeletable,
    bulkConcurrency: 4,
  },
  [FileAction.DELETE_REMOTE]: {
    urlSegment: 'delete_remote',
    logNoun: 'Remotely delete',
    isAllowed: (f) => f.isRemotelyDeletable,
    bulkConcurrency: 4,
  },
};
