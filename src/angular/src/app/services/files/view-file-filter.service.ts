import { Injectable, inject } from '@angular/core';

import { LoggerService } from '../utils/logger.service';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileFilterCriteria, ViewFileService } from './view-file.service';
import { ViewFileOptionsService } from './view-file-options.service';

class AndFilterCriteria implements ViewFileFilterCriteria {
  constructor(
    private a: ViewFileFilterCriteria,
    private b: ViewFileFilterCriteria,
  ) {}

  meetsCriteria(viewFile: ViewFile): boolean {
    return this.a.meetsCriteria(viewFile) && this.b.meetsCriteria(viewFile);
  }
}

class StatusFilterCriteria implements ViewFileFilterCriteria {
  constructor(readonly status: ViewFileStatus | null) {}

  meetsCriteria(viewFile: ViewFile): boolean {
    return this.status == null || this.status === viewFile.status;
  }
}

class NameFilterCriteria implements ViewFileFilterCriteria {
  private readonly queryCandidates: string[] = [];

  constructor(readonly name: string | null) {
    if (this.name != null) {
      const query = this.name.toLowerCase();
      this.queryCandidates = [
        query,
        // treat dots and spaces as the same
        query.replace(/\s/g, '.'),
        query.replace(/\./g, ' '),
      ];
    }
  }

  meetsCriteria(viewFile: ViewFile): boolean {
    if (this.name == null || this.name === '') {
      return true;
    }
    const search = viewFile.name.toLowerCase();
    return this.queryCandidates.some((candidate) => search.indexOf(candidate) >= 0);
  }
}

@Injectable({ providedIn: 'root' })
export class ViewFileFilterService {
  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);

  private statusFilter: StatusFilterCriteria | null = null;
  private nameFilter: NameFilterCriteria | null = null;

  constructor() {
    this.viewFileOptionsService.options$.subscribe((options) => {
      let updateFilterCriteria = false;

      if (this.statusFilter == null || this.statusFilter.status !== options.selectedStatusFilter) {
        updateFilterCriteria = true;
        this.statusFilter = new StatusFilterCriteria(options.selectedStatusFilter);
        this.logger.debug('Status filter set to: ' + options.selectedStatusFilter);
      }

      if (this.nameFilter == null || this.nameFilter.name !== options.nameFilter) {
        updateFilterCriteria = true;
        this.nameFilter = new NameFilterCriteria(options.nameFilter);
        this.logger.debug('Name filter set to: ' + options.nameFilter);
      }

      if (updateFilterCriteria) {
        this.viewFileService.setFilterCriteria(this.buildFilterCriteria());
      }
    });
  }

  private buildFilterCriteria(): ViewFileFilterCriteria | null {
    if (this.statusFilter != null && this.nameFilter != null) {
      return new AndFilterCriteria(this.statusFilter, this.nameFilter);
    } else if (this.statusFilter != null) {
      return this.statusFilter;
    } else if (this.nameFilter != null) {
      return this.nameFilter;
    } else {
      return null;
    }
  }
}
