import { Injectable, InjectionToken, inject } from '@angular/core';
import { BehaviorSubject, Observable, of, from } from 'rxjs';
import { auditTime, mergeMap, toArray } from 'rxjs/operators';

import { LoggerService } from '../utils/logger.service';
import { ModelFileService } from './model-file.service';
import { PathPairsService } from '../settings/path-pairs.service';
import { WebReaction } from '../utils/rest.service';
import { ModelFile } from '../../models/model-file';
import { ViewFile } from '../../models/view-file';
import { fileKey } from './file-key';
import { mapState, deriveCapabilities } from './view-file-capabilities';
import { ViewFileSelectionService } from './view-file-selection.service';

/**
 * Coalescing window (ms) for batching incremental SSE model-file emissions before
 * rebuilding the view. The backend controller loop emits one SSE event per changed
 * file every ~0.5s; without coalescing, N concurrently-downloading files trigger N
 * full view rebuilds + 2N subject emissions per cycle (issue #521).
 *
 * Defaults to 0 (synchronous pass-through) so unit tests — which read the view
 * synchronously right after emitting — stay deterministic without extra setup.
 * Production overrides this in app.config.ts.
 */
export const VIEW_FILE_COALESCE_MS = new InjectionToken<number>('VIEW_FILE_COALESCE_MS', {
  providedIn: 'root',
  factory: () => 0,
});

function viewFileKey(vf: ViewFile): string {
  return fileKey(vf.pairId, vf.name);
}

export interface ViewFileFilterCriteria {
  meetsCriteria(viewFile: ViewFile): boolean;
}

export type ViewFileComparator = (a: ViewFile, b: ViewFile) => number;

@Injectable({ providedIn: 'root' })
export class ViewFileService {
  private readonly logger = inject(LoggerService);
  private readonly modelFileService = inject(ModelFileService);
  private readonly pathPairsService = inject(PathPairsService);
  private readonly coalesceMs = inject(VIEW_FILE_COALESCE_MS);
  private readonly selection = inject(ViewFileSelectionService);

  private pairNameMap = new Map<string, string>();
  private files: ViewFile[] = [];
  private readonly filesSubject = new BehaviorSubject<ViewFile[]>([]);
  private readonly filteredFilesSubject = new BehaviorSubject<ViewFile[]>([]);
  private indices = new Map<string, number>();

  private prevModelFiles = new Map<string, ModelFile>();

  private filterCriteria: ViewFileFilterCriteria | null = null;
  private sortComparator: ViewFileComparator | null = null;

  readonly files$: Observable<ViewFile[]> = this.filesSubject.asObservable();
  readonly filteredFiles$: Observable<ViewFile[]> = this.filteredFilesSubject.asObservable();
  readonly checked$ = this.selection.checked$;

  constructor() {
    this.pathPairsService.pairs$.subscribe((pairs) => {
      this.pairNameMap.clear();
      for (const pair of pairs) {
        this.pairNameMap.set(pair.id, pair.name);
      }
      // Rebuild pairName on existing view files immediately. Only re-spread rows
      // whose resolved pairName actually changed so unchanged rows keep identity.
      if (this.files.length > 0) {
        let changed = false;
        const nextFiles = this.files.map(f => {
          const pairName = f.pairId ? (this.pairNameMap.get(f.pairId) ?? null) : null;
          if (pairName === f.pairName) {
            return f;
          }
          changed = true;
          return { ...f, pairName };
        });
        if (changed) {
          // pairName changed for some rows; if the active sort keys on pairName
          // the order is now stale (pushViewFiles does not re-sort), so reapply
          // the comparator before pushing.
          if (this.sortComparator != null) {
            nextFiles.sort(this.sortComparator);
          }
          this.files = nextFiles;
          this.pushViewFiles();
        }
      }
    });

    // Coalesce the per-file SSE fan-out: the backend emits one model event per
    // changed file every ~0.5s, so N active files would otherwise drive N full
    // view rebuilds per tick. auditTime collapses a burst into a single rebuild
    // on the trailing edge (the last Map already reflects the cumulative state,
    // since each event is an idempotent set/delete on the shared key space).
    // coalesceMs === 0 (the unit-test default) keeps the pass-through synchronous.
    const modelFiles$ =
      this.coalesceMs > 0
        ? this.modelFileService.files$.pipe(auditTime(this.coalesceMs))
        : this.modelFileService.files$;

    modelFiles$.subscribe({
      next: (modelFiles) => {
        const t0 = performance.now();
        this.buildViewFromModelFiles(modelFiles);
        const t1 = performance.now();
        this.logger.debug('ViewFile creation took', (t1 - t0).toFixed(0), 'ms');
      },
    });
  }

  setSelected(file: ViewFile): void {
    const viewFiles = [...this.files];
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

  validate(file: ViewFile): Observable<WebReaction> {
    this.logger.debug('Validate view file: ' + file.name);
    return this.createAction(file, (f) => this.modelFileService.validate(f));
  }

  toggleCheck(file: ViewFile): void {
    this.selection.toggle(viewFileKey(file));
    this.updateCheckedState();
  }

  shiftCheck(file: ViewFile): void {
    const filteredKeys = this.filteredFilesSubject.getValue().map(viewFileKey);
    this.selection.shiftRange(viewFileKey(file), filteredKeys);
    this.updateCheckedState();
  }

  checkAll(): void {
    const filteredKeys = this.filteredFilesSubject.getValue().map(viewFileKey);
    this.selection.checkAll(filteredKeys);
    this.updateCheckedState();
  }

  uncheckAll(): void {
    this.selection.uncheckAll();
    this.updateCheckedState();
  }

  // Re-spread only the rows whose derived isChecked flips, preserving object
  // identity for unchanged rows so OnPush/ngOnChanges can skip them. isChecked
  // stays strictly derived from the selection service's checked set. The
  // checked$ emission itself is owned by ViewFileSelectionService — this method
  // only reconciles the diffing-owned `this.files` array and re-pushes the view.
  private updateCheckedState(): void {
    let changed = false;
    const nextFiles = this.files.map(f => {
      const isChecked = this.selection.isChecked(viewFileKey(f));
      if (isChecked === f.isChecked) {
        return f;
      }
      changed = true;
      return { ...f, isChecked };
    });
    if (changed) {
      this.files = nextFiles;
    }
    this.pushViewFiles();
  }

  bulkQueue(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isQueueable, f => this.queue(f));
  }

  bulkStop(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isStoppable, f => this.stop(f));
  }

  bulkDeleteLocal(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isLocallyDeletable, f => this.deleteLocal(f), 4);
  }

  bulkDeleteRemote(): Observable<WebReaction[]> {
    return this.bulkAction(f => f.isRemotelyDeletable, f => this.deleteRemote(f), 4);
  }

  private bulkAction(
    filter: (f: ViewFile) => boolean,
    action: (f: ViewFile) => Observable<WebReaction>,
    concurrency = Infinity
  ): Observable<WebReaction[]> {
    const checked = this.files.filter(f => this.selection.isChecked(viewFileKey(f)) && filter(f));
    if (checked.length === 0) {
      return of([]);
    }
    return from(checked).pipe(
      mergeMap(f => action(f), concurrency),
      toArray()
    );
  }

  setFilterCriteria(criteria: ViewFileFilterCriteria | null): void {
    this.filterCriteria = criteria;
    this.pushViewFiles();
  }

  setComparator(comparator: ViewFileComparator | null): void {
    this.sortComparator = comparator;

    this.logger.debug('Re-sorting view files');
    const newViewFiles = [...this.files];
    if (this.sortComparator != null) {
      newViewFiles.sort(this.sortComparator);
    }
    this.files = newViewFiles;
    this.indices.clear();
    newViewFiles.forEach((value, index) => { this.indices.set(viewFileKey(value), index); });

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
      const newViewFile = createViewFile(modelFiles.get(key)!, this.pairNameMap, oldViewFile.isSelected);
      newViewFiles[index] = { ...newViewFile, isChecked: this.selection.isChecked(key) };
      if (this.sortComparator != null && this.sortComparator(oldViewFile, newViewFile) !== 0) {
        reSort = true;
      }
    }

    // Do the adds (requires re-sort)
    for (const key of addedKeys) {
      reSort = true;
      const viewFile = createViewFile(modelFiles.get(key)!, this.pairNameMap);
      newViewFiles.push({ ...viewFile, isChecked: this.selection.isChecked(key) });
      this.indices.set(viewFileKey(viewFile), newViewFiles.length - 1);
    }

    // Do the removes (no re-sort required). Filter out every removed key in a
    // single O(n) pass instead of findIndex+splice per key (O(n*m)). filter is
    // stable, so the surviving order is identical to the splice-loop result.
    if (removedKeys.length > 0) {
      updateIndices = true;
      const removed = new Set(removedKeys);
      // Drop any checked entries for removed files; the selection service
      // re-emits checked$ iff at least one was actually present.
      this.selection.pruneRemoved(removedKeys);
      newViewFiles = newViewFiles.filter((v) => !removed.has(viewFileKey(v)));
    }

    if (reSort && this.sortComparator != null) {
      this.logger.debug('Re-sorting view files');
      updateIndices = true;
      newViewFiles.sort(this.sortComparator);
    }
    if (updateIndices) {
      this.indices.clear();
      newViewFiles.forEach((value, index) => { this.indices.set(viewFileKey(value), index); });
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
        action(modelFile).subscribe({
          next: (reaction) => {
            this.logger.debug('Received model reaction: %O', reaction);
            observer.next(reaction);
            observer.complete();
          },
          error: (err) => {
            this.logger.error('Action failed for file: ' + key, err);
            observer.next({ success: false, data: null, errorMessage: String(err?.message ?? err) });
            observer.complete();
          },
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

    // Skip re-emitting the filtered list when its membership/order is unchanged
    // (element-wise reference-identical to the last emission). The rendered DOM is
    // identical either way; this lets OnPush consumers skip a needless CD pass.
    const prevFiltered = this.filteredFilesSubject.getValue();
    if (filteredFiles !== prevFiltered && arraysReferenceEqual(filteredFiles, prevFiltered)) {
      return;
    }
    this.filteredFilesSubject.next(filteredFiles);
  }
}

function arraysReferenceEqual(a: readonly ViewFile[], b: readonly ViewFile[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) {
      return false;
    }
  }
  return true;
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

function createViewFile(modelFile: ModelFile, pairNameMap: Map<string, string>, isSelected = false): ViewFile {
  const localSize = modelFile.local_size ?? 0;
  const remoteSize = modelFile.remote_size ?? 0;
  let percentDownloaded: number;
  if (remoteSize > 0) {
    percentDownloaded = Math.trunc((100.0 * localSize) / remoteSize);
  } else {
    percentDownloaded = 100;
  }

  const status = mapState(modelFile.state, localSize, remoteSize);
  const capabilities = deriveCapabilities(
    status,
    localSize,
    remoteSize,
    modelFile.local_size,
    modelFile.remote_size,
  );

  return {
    name: modelFile.name,
    pairId: modelFile.pair_id,
    pairName: modelFile.pair_id ? (pairNameMap.get(modelFile.pair_id) ?? null) : null,
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
    ...capabilities,
    localCreatedTimestamp: modelFile.local_created_timestamp,
    localModifiedTimestamp: modelFile.local_modified_timestamp,
    remoteCreatedTimestamp: modelFile.remote_created_timestamp,
    remoteModifiedTimestamp: modelFile.remote_modified_timestamp,
  };
}
