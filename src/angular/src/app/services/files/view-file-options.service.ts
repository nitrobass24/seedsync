import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { LoggerService } from '../utils/logger.service';
import { ViewFileOptions, SortMethod } from '../../models/view-file-options';
import { ViewFileStatus } from '../../models/view-file';
import { StorageKeys } from '../../common/storage-keys';

@Injectable({ providedIn: 'root' })
export class ViewFileOptionsService {
  private readonly logger = inject(LoggerService);

  private readonly optionsSubject: BehaviorSubject<ViewFileOptions>;

  readonly options$: Observable<ViewFileOptions>;

  constructor() {
    const showDetails: boolean =
      JSON.parse(localStorage.getItem(StorageKeys.VIEW_OPTION_SHOW_DETAILS) ?? 'false') || false;
    const sortMethod: SortMethod =
      JSON.parse(localStorage.getItem(StorageKeys.VIEW_OPTION_SORT_METHOD) ?? 'null') ??
      SortMethod.STATUS;
    const pinFilter: boolean =
      JSON.parse(localStorage.getItem(StorageKeys.VIEW_OPTION_PIN) ?? 'false') || false;

    this.optionsSubject = new BehaviorSubject<ViewFileOptions>({
      showDetails,
      sortMethod,
      selectedStatusFilter: null,
      nameFilter: '',
      pinFilter,
    });
    this.options$ = this.optionsSubject.asObservable();
  }

  setShowDetails(show: boolean): void {
    const options = this.optionsSubject.getValue();
    if (options.showDetails !== show) {
      this.optionsSubject.next({ ...options, showDetails: show });
      localStorage.setItem(StorageKeys.VIEW_OPTION_SHOW_DETAILS, JSON.stringify(show));
      this.logger.debug('ViewOption showDetails set to: ' + show);
    }
  }

  setSortMethod(sortMethod: SortMethod): void {
    const options = this.optionsSubject.getValue();
    if (options.sortMethod !== sortMethod) {
      this.optionsSubject.next({ ...options, sortMethod });
      localStorage.setItem(StorageKeys.VIEW_OPTION_SORT_METHOD, JSON.stringify(sortMethod));
      this.logger.debug('ViewOption sortMethod set to: ' + sortMethod);
    }
  }

  setSelectedStatusFilter(status: ViewFileStatus | null): void {
    const options = this.optionsSubject.getValue();
    if (options.selectedStatusFilter !== status) {
      this.optionsSubject.next({ ...options, selectedStatusFilter: status });
      this.logger.debug('ViewOption selectedStatusFilter set to: ' + status);
    }
  }

  setNameFilter(name: string): void {
    const options = this.optionsSubject.getValue();
    if (options.nameFilter !== name) {
      this.optionsSubject.next({ ...options, nameFilter: name });
      this.logger.debug('ViewOption nameFilter set to: ' + name);
    }
  }

  setPinFilter(pinned: boolean): void {
    const options = this.optionsSubject.getValue();
    if (options.pinFilter !== pinned) {
      this.optionsSubject.next({ ...options, pinFilter: pinned });
      localStorage.setItem(StorageKeys.VIEW_OPTION_PIN, JSON.stringify(pinned));
      this.logger.debug('ViewOption pinFilter set to: ' + pinned);
    }
  }
}
