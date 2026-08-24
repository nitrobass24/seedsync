import { Injectable, inject } from '@angular/core';

import { LoggerService } from '../utils/logger.service';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileFilterCriteria, ViewFileService } from './view-file.service';
import { ViewFileOptionsService } from './view-file-options.service';

function statusPredicate(status: ViewFileStatus | null): ViewFileFilterCriteria {
  return (f: ViewFile) => status == null || status === f.status;
}

function namePredicate(name: string | null): ViewFileFilterCriteria {
  if (!name) {
    return () => true;
  }
  const query = name.toLowerCase();
  // treat dots and spaces as the same
  const candidates = [query, query.replace(/\s/g, '.'), query.replace(/\./g, ' ')];
  return (f: ViewFile) => {
    const search = f.name.toLowerCase();
    return candidates.some((c) => search.includes(c));
  };
}

@Injectable({ providedIn: 'root' })
export class ViewFileFilterService {
  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);

  private status: ViewFileStatus | null | undefined;
  private name: string | null | undefined;

  constructor() {
    this.viewFileOptionsService.options$.subscribe((options) => {
      const statusChanged = this.status !== options.selectedStatusFilter;
      const nameChanged = this.name !== options.nameFilter;
      if (statusChanged) {
        this.status = options.selectedStatusFilter;
        this.logger.debug('Status filter set to: ' + this.status);
      }
      if (nameChanged) {
        this.name = options.nameFilter;
        this.logger.debug('Name filter set to: ' + this.name);
      }
      if (statusChanged || nameChanged) {
        const byStatus = statusPredicate(this.status ?? null);
        const byName = namePredicate(this.name ?? null);
        this.viewFileService.setFilterCriteria((f) => byStatus(f) && byName(f));
      }
    });
  }
}
