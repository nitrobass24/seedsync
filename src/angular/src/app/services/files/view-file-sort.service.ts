import { Injectable, inject } from '@angular/core';

import { LoggerService } from '../utils/logger.service';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileComparator, ViewFileService } from './view-file.service';
import { ViewFileOptionsService } from './view-file-options.service';
import { SortMethod } from '../../models/view-file-options';

const StatusComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
  if (a.status !== b.status) {
    const statusPriorities: Record<string, number> = {
      [ViewFileStatus.EXTRACTING]: 0,
      [ViewFileStatus.DOWNLOADING]: 1,
      [ViewFileStatus.QUEUED]: 2,
      [ViewFileStatus.STOPPED]: 3,
      [ViewFileStatus.DEFAULT]: 4,
      [ViewFileStatus.DELETED]: 4, // intermix deleted and default
      [ViewFileStatus.DOWNLOADED]: 5,
      [ViewFileStatus.EXTRACTED]: 5, // intermix with downloaded
      [ViewFileStatus.EXTRACT_FAILED]: 5,
      [ViewFileStatus.VALIDATING]: 0, // show with active operations
      [ViewFileStatus.VALIDATED]: 5, // intermix with downloaded
      [ViewFileStatus.CORRUPT]: 3, // show prominently like stopped
    };
    if (statusPriorities[a.status] !== statusPriorities[b.status]) {
      return statusPriorities[a.status] - statusPriorities[b.status];
    }
  }
  // Within same status group, sort oldest first by remote timestamp
  const aTime = a.remoteCreatedTimestamp?.getTime() ?? 0;
  const bTime = b.remoteCreatedTimestamp?.getTime() ?? 0;
  if (aTime !== bTime) {
    return aTime - bTime;
  }
  return a.name.localeCompare(b.name);
};

const NameAscendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
  return a.name.localeCompare(b.name);
};

const NameDescendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
  return b.name.localeCompare(a.name);
};

/**
 * Get the effective size for sorting: use remoteSize, fall back to localSize.
 * Returns null if both are zero/unavailable.
 */
function getEffectiveSize(file: ViewFile): number | null {
  if (file.remoteSize > 0) return file.remoteSize;
  if (file.localSize > 0) return file.localSize;
  return null;
}

const SizeAscendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
  const aSize = getEffectiveSize(a);
  const bSize = getEffectiveSize(b);
  // Null sizes sort last
  if (aSize === null && bSize === null) return a.name.localeCompare(b.name);
  if (aSize === null) return 1;
  if (bSize === null) return -1;
  if (aSize !== bSize) return aSize - bSize;
  return a.name.localeCompare(b.name);
};

const SizeDescendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
  const aSize = getEffectiveSize(a);
  const bSize = getEffectiveSize(b);
  // Null sizes sort last
  if (aSize === null && bSize === null) return a.name.localeCompare(b.name);
  if (aSize === null) return 1;
  if (bSize === null) return -1;
  if (aSize !== bSize) return bSize - aSize;
  return a.name.localeCompare(b.name);
};

@Injectable({ providedIn: 'root' })
export class ViewFileSortService {
  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);

  private sortMethod: SortMethod | null = null;

  constructor() {
    this.viewFileOptionsService.options$.subscribe((options) => {
      if (this.sortMethod !== options.sortMethod) {
        this.sortMethod = options.sortMethod;
        if (this.sortMethod === SortMethod.STATUS) {
          this.viewFileService.setComparator(StatusComparator);
          this.logger.debug('Comparator set to: Status');
        } else if (this.sortMethod === SortMethod.NAME_DESC) {
          this.viewFileService.setComparator(NameDescendingComparator);
          this.logger.debug('Comparator set to: Name Desc');
        } else if (this.sortMethod === SortMethod.NAME_ASC) {
          this.viewFileService.setComparator(NameAscendingComparator);
          this.logger.debug('Comparator set to: Name Asc');
        } else if (this.sortMethod === SortMethod.SIZE_ASC) {
          this.viewFileService.setComparator(SizeAscendingComparator);
          this.logger.debug('Comparator set to: Size Asc');
        } else if (this.sortMethod === SortMethod.SIZE_DESC) {
          this.viewFileService.setComparator(SizeDescendingComparator);
          this.logger.debug('Comparator set to: Size Desc');
        } else {
          this.viewFileService.setComparator(null);
          this.logger.debug('Comparator set to: null');
        }
      }
    });
  }
}
