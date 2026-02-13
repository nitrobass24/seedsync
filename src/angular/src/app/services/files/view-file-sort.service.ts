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
        } else {
          this.viewFileService.setComparator(null);
          this.logger.debug('Comparator set to: null');
        }
      }
    });
  }
}
