import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, of, forkJoin } from 'rxjs';

import { LoggerService } from '../utils/logger.service';
import { ModelFileService } from './model-file.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { ModelFile, ModelFileState } from '../../models/model-file';
import { ViewFile, ViewFileStatus } from '../../models/view-file';

function viewFileKey(vf: ViewFile): string {
  return vf.pairId ? `${vf.pairId}:${vf.name}` : vf.name;
}

function modelFileKey(mf: ModelFile): string {
  return mf.pair_id ? `${mf.pair_id}:${mf.name}` : mf.name;
}

export interface ViewFileFilterCriteria {
  meetsCriteria(viewFile: ViewFile): boolean;
}

export type ViewFileComparator = (a: ViewFile, b: ViewFile) => number;

@Injectable({ providedIn: 'root' })
export class ViewFileService {
  private readonly logger = inject(LoggerService);
  private readonly modelFileService = inject(ModelFileService);

  private files: ViewFile[] = [];
  private readonly filesSubject = new BehaviorSubject<ViewFile[]>([]);
  private readonly filteredFilesSubject = new BehaviorSubject<ViewFile[]>([]);
  private indices = new Map<string, number>();

  private prevModelFiles = new Map<string, ModelFile>();

  private filterCriteria: ViewFileFilterCriteria | null = null;
  private sortComparator: ViewFileComparator | null = null;

  private checkedSet = new Set<string>();
  private readonly checkedSubject = new BehaviorSubject<Set<string>>(new Set());
  private lastCheckedKey: string | null = null;

  readonly files$: Observable<ViewFile[]> = this.filesSubject.asObservable();
  readonly filteredFiles$: Observable<ViewFile[]> = this.filteredFilesSubject.asObservable();
  readonly checked$ = this.checkedSubject.asObservable();

  constructor() {
    this.modelFileService.files$.subscribe({
      next: (modelFiles) => {
        const t0 = performance.now();
        this.buildViewFromModelFiles(modelFiles);
        const t1 = performance.now();
        this.logger.debug('ViewFile creation took', (t1 - t0).toFixed(0), 'ms');
      },
    });
  }

  setSelected(file: ViewFile): void {
    let viewFiles = [...this.files];
    const unSelectIndex = viewFiles.findIndex((v) => v.isSelected);
    const key = viewFileKey(file);

    if (unSelectIndex >= 0) {
      if (viewFileKey(viewFiles[unSelectIndex]) === key) {
        return;
      }
      viewFiles[unSelectIndex] = { ...viewFiles[unSelectIndex], isSelected: false };
    }

    if (this.indices.has(key)) {
      const index = this.indices.get(key)!;
      viewFiles[index] = { ...viewFiles[index], isSelected: true };
    } else {
      this.logger.error("Can't find file to select: " + key);
    }

    this.files = viewFiles;
    this.pushViewFiles();
  }

  unsetSelected(): void {
    const viewFiles = [...this.files];
    const unSelectIndex = viewFiles.findIndex((v) => v.isSelected);

    if (unSelectIndex >= 0) {
      viewFiles[unSelectIndex] = { ...viewFiles[unSelectIndex], isSelected: false };
      this.files = viewFiles;
      this.pushViewFiles();
    }
  }

  queue(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Queue view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.queue(f));
  }

  stop(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Stop view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.stop(f));
  }

  extract(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Extract view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.extract(f));
  }

  deleteLocal(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Locally delete view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.deleteLocal(f));
  }

  deleteRemote(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Remotely delete view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.deleteRemote(f));
  }

  toggleCheck(file: ViewFile): void {
    const key = viewFileKey(file);
    if (this.checkedSet.has(key)) {
      this.checkedSet.delete(key);
    } else {
      this.checkedSet.add(key);
    }
    this.lastCheckedKey = key;
    this.updateCheckedState();
  }

  shiftCheck(file: ViewFile): void {
    if (this.lastCheckedKey == null) {
      this.toggleCheck(file);
      return;
    }
    const filtered = this.filteredFilesSubject.getValue();
    const lastIdx = filtered.findIndex(f => viewFileKey(f) === this.lastCheckedKey);
    const currIdx = filtered.findIndex(f => viewFileKey(f) === viewFileKey(file));
    if (lastIdx < 0 || currIdx < 0) {
      this.toggleCheck(file);
      return;
    }
    const start = Math.min(lastIdx, currIdx);
    const end = Math.max(lastIdx, currIdx);
    for (let i = start; i <= end; i++) {
      this.checkedSet.add(viewFileKey(filtered[i]));
    }
    this.lastCheckedKey = viewFileKey(file);
    this.updateCheckedState();
  }

  checkAll(): void {
    const filtered = this.filteredFilesSubject.getValue();
    for (const f of filtered) {
      this.checkedSet.add(viewFileKey(f));
    }
    this.updateCheckedState();
  }

  uncheckAll(): void {
    this.checkedSet.clear();
    this.lastCheckedKey = null;
    this.updateCheckedState();
  }

  private updateCheckedState(): void {
    this.files = this.files.map(f => ({
      ...f,
      isChecked: this.checkedSet.has(viewFileKey(f))
    }));
    this.checkedSubject.next(new Set(this.checkedSet));
    this.pushViewFiles();
  }

  bulkQueue(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isQueueable, f => this.queue(f));
  }

  bulkStop(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isStoppable, f => this.stop(f));
  }

  bulkDeleteLocal(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isLocallyDeletable, f => this.deleteLocal(f));
  }

  bulkDeleteRemote(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isRemotelyDeletable, f => this.deleteRemote(f));
  }

  private bulkAction(
    filter: (f: ViewFile) => boolean,
    action: (f: ViewFile) => Observable<WebReaction>
  ): Observable<WebReaction[]> {
    const checked = this.files.filter(f => this.checkedSet.has(viewFileKey(f)) && filter(f));
    if (checked.length === 0) {
      return of([]);
    }
    return forkJoin(checked.map(f => action(f)));
  }

  setFilterCriteria(criteria: ViewFileFilterCriteria | null): void {
    this.filterCriteria = criteria;
    this.pushViewFiles();
  }

  setComparator(comparator: ViewFileComparator | null): void {
    this.sortComparator = comparator;

    this.logger.debug('Re-sorting view files');
    let newViewFiles = [...this.files];
    if (this.sortComparator != null) {
      newViewFiles.sort(this.sortComparator);
    }
    this.files = newViewFiles;
    this.indices.clear();
    newViewFiles.forEach((value, index) => this.indices.set(viewFileKey(value), index));

    this.pushViewFiles();
  }

  private buildViewFromModelFiles(modelFiles: Map<string, ModelFile>): void {
    this.logger.debug('Received next model files');

    let newViewFiles = [...this.files];

    const addedKeys: string[] = [];
    const removedKeys: string[] = [];
    const updatedKeys: string[] = [];

    // Loop through old model to find deletions
    for (const key of this.prevModelFiles.keys()) {
      if (!modelFiles.has(key)) {
        removedKeys.push(key);
      }
    }

    // Loop through new model to find additions and updates
    for (const key of modelFiles.keys()) {
      if (!this.prevModelFiles.has(key)) {
        addedKeys.push(key);
      } else {
        const oldFile = this.prevModelFiles.get(key)!;
        const newFile = modelFiles.get(key)!;
        if (!modelFilesEqual(oldFile, newFile)) {
          updatedKeys.push(key);
        }
      }
    }

    let reSort = false;
    let updateIndices = false;

    // Do the updates first before indices change (re-sort may be required)
    for (const key of updatedKeys) {
      const index = this.indices.get(key)!;
      const oldViewFile = newViewFiles[index];
      const newViewFile = createViewFile(modelFiles.get(key)!, oldViewFile.isSelected);
      newViewFiles[index] = { ...newViewFile, isChecked: this.checkedSet.has(key) };
      if (this.sortComparator != null && this.sortComparator(oldViewFile, newViewFile) !== 0) {
        reSort = true;
      }
    }

    // Do the adds (requires re-sort)
    for (const key of addedKeys) {
      reSort = true;
      const viewFile = createViewFile(modelFiles.get(key)!);
      newViewFiles.push({ ...viewFile, isChecked: this.checkedSet.has(key) });
      this.indices.set(viewFileKey(viewFile), newViewFiles.length - 1);
    }

    // Do the removes (no re-sort required)
    let checkedChanged = false;
    for (const key of removedKeys) {
      updateIndices = true;
      if (this.checkedSet.delete(key)) {
        checkedChanged = true;
      }
      const index = newViewFiles.findIndex((v) => viewFileKey(v) === key);
      newViewFiles.splice(index, 1);
      this.indices.delete(key);
    }
    if (checkedChanged) {
      this.checkedSubject.next(new Set(this.checkedSet));
    }

    if (reSort && this.sortComparator != null) {
      this.logger.debug('Re-sorting view files');
      updateIndices = true;
      newViewFiles.sort(this.sortComparator);
    }
    if (updateIndices) {
      this.indices.clear();
      newViewFiles.forEach((value, index) => this.indices.set(viewFileKey(value), index));
    }

    this.files = newViewFiles;
    this.pushViewFiles();
    this.prevModelFiles = modelFiles;
    this.logger.debug('New view model: %O', this.files);
  }

  private createAction(
    file: ViewFile,
    action: (file: ModelFile) => Observable<WebReaction>,
  ): Observable<WebReaction> {
    return new Observable((observer) => {
      const key = viewFileKey(file);
      if (!this.prevModelFiles.has(key)) {
        this.logger.error('File to queue not found: ' + key);
        observer.next({ success: false, data: null, errorMessage: `File '${file.name}' not found` });
        observer.complete();
      } else {
        const modelFile = this.prevModelFiles.get(key)!;
        action(modelFile).subscribe((reaction) => {
          this.logger.debug('Received model reaction: %O', reaction);
          observer.next(reaction);
          observer.complete();
        });
      }
    });
  }

  private pushViewFiles(): void {
    this.filesSubject.next(this.files);

    let filteredFiles = this.files;
    if (this.filterCriteria != null) {
      filteredFiles = this.files.filter((f) => this.filterCriteria!.meetsCriteria(f));
    }
    this.filteredFilesSubject.next(filteredFiles);
  }
}

function modelFilesEqual(a: ModelFile, b: ModelFile): boolean {
  return (
    a.name === b.name &&
    a.pair_id === b.pair_id &&
    a.is_dir === b.is_dir &&
    a.local_size === b.local_size &&
    a.remote_size === b.remote_size &&
    a.state === b.state &&
    a.downloading_speed === b.downloading_speed &&
    a.eta === b.eta &&
    a.full_path === b.full_path &&
    a.is_extractable === b.is_extractable
  );
}

function createViewFile(modelFile: ModelFile, isSelected: boolean = false): ViewFile {
  const localSize = modelFile.local_size ?? 0;
  const remoteSize = modelFile.remote_size ?? 0;
  let percentDownloaded: number;
  if (remoteSize > 0) {
    percentDownloaded = Math.trunc((100.0 * localSize) / remoteSize);
  } else {
    percentDownloaded = 100;
  }

  let status: ViewFileStatus;
  switch (modelFile.state) {
    case ModelFileState.DEFAULT:
      if (localSize > 0 && remoteSize > 0) {
        status = ViewFileStatus.STOPPED;
      } else {
        status = ViewFileStatus.DEFAULT;
      }
      break;
    case ModelFileState.QUEUED:
      status = ViewFileStatus.QUEUED;
      break;
    case ModelFileState.DOWNLOADING:
      status = ViewFileStatus.DOWNLOADING;
      break;
    case ModelFileState.DOWNLOADED:
      status = ViewFileStatus.DOWNLOADED;
      break;
    case ModelFileState.DELETED:
      status = ViewFileStatus.DELETED;
      break;
    case ModelFileState.EXTRACTING:
      status = ViewFileStatus.EXTRACTING;
      break;
    case ModelFileState.EXTRACTED:
      status = ViewFileStatus.EXTRACTED;
      break;
    case ModelFileState.EXTRACT_FAILED:
      status = ViewFileStatus.EXTRACT_FAILED;
      break;
    default:
      status = ViewFileStatus.DEFAULT;
  }

  const isQueueable =
    [ViewFileStatus.DEFAULT, ViewFileStatus.STOPPED, ViewFileStatus.DELETED].includes(status) &&
    remoteSize > 0;
  const isStoppable = [ViewFileStatus.QUEUED, ViewFileStatus.DOWNLOADING].includes(status);
  const isExtractable =
    [
      ViewFileStatus.DEFAULT,
      ViewFileStatus.STOPPED,
      ViewFileStatus.DOWNLOADED,
      ViewFileStatus.EXTRACTED,
      ViewFileStatus.EXTRACT_FAILED,
    ].includes(status) && localSize > 0;
  const isLocallyDeletable =
    [
      ViewFileStatus.DEFAULT,
      ViewFileStatus.STOPPED,
      ViewFileStatus.DOWNLOADED,
      ViewFileStatus.EXTRACTED,
      ViewFileStatus.EXTRACT_FAILED,
    ].includes(status) && localSize > 0;
  const isRemotelyDeletable =
    [
      ViewFileStatus.DEFAULT,
      ViewFileStatus.STOPPED,
      ViewFileStatus.DOWNLOADED,
      ViewFileStatus.EXTRACTED,
      ViewFileStatus.EXTRACT_FAILED,
      ViewFileStatus.DELETED,
    ].includes(status) && remoteSize > 0;

  return {
    name: modelFile.name,
    pairId: modelFile.pair_id,
    isDir: modelFile.is_dir,
    localSize,
    remoteSize,
    percentDownloaded,
    status,
    downloadingSpeed: modelFile.downloading_speed,
    eta: modelFile.eta,
    fullPath: modelFile.full_path,
    isArchive: modelFile.is_extractable,
    isSelected,
    isChecked: false,
    isQueueable,
    isStoppable,
    isExtractable,
    isLocallyDeletable,
    isRemotelyDeletable,
    localCreatedTimestamp: modelFile.local_created_timestamp,
    localModifiedTimestamp: modelFile.local_modified_timestamp,
    remoteCreatedTimestamp: modelFile.remote_created_timestamp,
    remoteModifiedTimestamp: modelFile.remote_modified_timestamp,
  };
}
