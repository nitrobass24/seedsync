import { Injectable, InjectionToken, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { auditTime } from 'rxjs/operators';

import { LoggerService } from '../utils/logger.service';
import { ModelFileService } from './model-file.service';
import { PathPairsService } from '../settings/path-pairs.service';
import { WebReaction } from '../utils/rest.service';
import { ModelFile, ModelFileState } from '../../models/model-file';
import { ViewFile } from '../../models/view-file';
import { FileAction } from '../../models/file-action';
import { viewFileKey } from './file-key';
import { resolveNestedModelFile } from './model-file-tree';
import { mapState, deriveCapabilities, LOCAL_ACTION_STATUSES } from './view-file-capabilities';
import { ViewFileSelectionService } from './view-file-selection.service';
import { ViewFileCommandService } from './view-file-command.service';

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

export type ViewFileFilterCriteria = (viewFile: ViewFile) => boolean;

export type ViewFileComparator = (a: ViewFile, b: ViewFile) => number;

@Injectable({ providedIn: 'root' })
export class ViewFileService {
  private readonly logger = inject(LoggerService);
  private readonly modelFileService = inject(ModelFileService);
  private readonly pathPairsService = inject(PathPairsService);
  private readonly coalesceMs = inject(VIEW_FILE_COALESCE_MS);
  private readonly selection = inject(ViewFileSelectionService);
  private readonly commands = inject(ViewFileCommandService);

  private pairNameMap = new Map<string, string>();
  private files: ViewFile[] = [];
  private readonly filesSubject = new BehaviorSubject<ViewFile[]>([]);
  private readonly filteredFilesSubject = new BehaviorSubject<ViewFile[]>([]);
  private indices = new Map<string, number>();

  private prevModelFiles = new Map<string, ModelFile>();

  // Resolve a view-file key to its backing ModelFile from the diffing-owned
  // snapshot. Threaded into ViewFileCommandService so command dispatch keeps the
  // exact resolution semantics this service has always used (`prevModelFiles`).
  // `prevModelFiles` is keyed by top-level name; a key that doesn't match
  // directly is walked into the matching top-level entry's nested children
  // (see resolveNestedModelFile) so nested rows resolve too.
  private readonly resolveModelFile = (key: string): ModelFile | undefined =>
    this.prevModelFiles.get(key) ?? resolveNestedModelFile(this.prevModelFiles, key);

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

  // Selection can land on a nested row (any depth), not just a top-level one,
  // so it can't use `indices` (built only from the top-level array) or a
  // flat findIndex. These walk the whole forest, re-spreading only the
  // ancestors of a changed node so OnPush sees the update.
  private findSelectable(nodes: readonly ViewFile[], key: string): ViewFile | undefined {
    for (const node of nodes) {
      if (viewFileKey(node) === key) return node;
      const found = this.findSelectable(node.children, key);
      if (found) return found;
    }
    return undefined;
  }

  private clearSelectionInTree(node: ViewFile): ViewFile {
    if (node.isSelected) {
      return { ...node, isSelected: false };
    }
    if (node.children.length === 0) {
      return node;
    }
    let changed = false;
    const children = node.children.map((child) => {
      const updated = this.clearSelectionInTree(child);
      if (updated !== child) changed = true;
      return updated;
    });
    return changed ? { ...node, children } : node;
  }

  setSelected(file: ViewFile): void {
    const key = viewFileKey(file);
    if (this.findSelectable(this.files, key)?.isSelected) {
      return;
    }

    let targetFound = false;
    const select = (node: ViewFile): ViewFile => {
      if (viewFileKey(node) === key) {
        targetFound = true;
        return { ...node, isSelected: true };
      }
      if (node.children.length === 0) {
        return node;
      }
      let changed = false;
      const children = node.children.map((child) => {
        const updated = select(child);
        if (updated !== child) changed = true;
        return updated;
      });
      return changed ? { ...node, children } : node;
    };

    const cleared = this.files.map((f) => this.clearSelectionInTree(f));
    this.files = cleared.map(select);
    if (!targetFound) {
      this.logger.error("Can't find file to select: " + key);
    }
    this.pushViewFiles();
  }

  unsetSelected(): void {
    const cleared = this.files.map((f) => this.clearSelectionInTree(f));
    if (cleared.some((f, i) => f !== this.files[i])) {
      this.files = cleared;
      this.pushViewFiles();
    }
  }

  // Thin facade over ViewFileCommandService — kept so existing consumers (and
  // the existing spec) target a single service. Command dispatch lives in
  // ViewFileCommandService (issue #541); this service threads in the
  // diffing-owned ModelFile resolver.
  command(action: FileAction, file: ViewFile): Observable<WebReaction> {
    return this.commands.command(action, file, this.resolveModelFile);
  }

  cleanupLocal(file: ViewFile): Observable<WebReaction> {
    return this.commands.cleanupLocal(file, this.resolveModelFile);
  }

  toggleCheck(file: ViewFile): void {
    this.selection.toggle(viewFileKey(file));
    this.updateCheckedState();
  }

  // `visibleKeys`, when given, is the caller's current flattened display-order
  // key list (top-level + expanded nested rows) so a shift-click range spans
  // exactly what's on screen, including nested rows. Falls back to the
  // top-level-only filtered list for callers that don't track a flattened view.
  shiftCheck(file: ViewFile, visibleKeys?: readonly string[]): void {
    const filteredKeys = visibleKeys ?? this.filteredFilesSubject.getValue().map(viewFileKey);
    this.selection.shiftRange(viewFileKey(file), filteredKeys);
    this.updateCheckedState();
  }

  // Checks every row in the filtered top-level forest AND all of their nested
  // descendants (any depth, whether or not currently expanded) - "select all"
  // means all, not just what's currently visible.
  checkAll(): void {
    const keys = collectAllKeys(this.filteredFilesSubject.getValue());
    this.selection.checkAll(keys);
    this.updateCheckedState();
  }

  uncheckAll(): void {
    this.selection.uncheckAll();
    this.updateCheckedState();
  }

  // Re-spread only the nodes (at any depth) whose derived isChecked/
  // isIndeterminate flips, preserving object identity for unchanged rows so
  // OnPush/ngOnChanges can skip them. Both flags stay strictly derived from
  // the selection service's checked set. The checked$ emission itself is
  // owned by ViewFileSelectionService — this method only reconciles the
  // diffing-owned `this.files` tree and re-pushes the view.
  private updateCheckedState(): void {
    let changed = false;
    const nextFiles = this.files.map(f => {
      const updated = this.reconcileCheckedTree(f);
      if (updated !== f) changed = true;
      return updated;
    });
    if (changed) {
      this.files = nextFiles;
    }
    this.pushViewFiles();
  }

  // Recomputes isChecked (own key, from the selection set) and isIndeterminate
  // bottom-up over the whole subtree. Checked state isn't cascaded between a
  // folder and its children - each row's own checkbox toggles only its own
  // key, preserving the pre-existing top-level behavior where checking a
  // folder selects that folder itself as one bulk-actionable unit. On top of
  // that, isIndeterminate is a display-only aggregate: true when this folder
  // isn't itself checked but at least one descendant, at any depth, is
  // checked or indeterminate - the "something inside is selected" signal.
  // Gated on !isChecked so a folder that IS itself checked shows a plain
  // checkmark rather than double-encoding both states at once.
  private reconcileCheckedTree(node: ViewFile): ViewFile {
    let childrenChanged = false;
    let anyChildActive = false;
    const children = node.children.map(child => {
      const updated = this.reconcileCheckedTree(child);
      if (updated !== child) childrenChanged = true;
      if (updated.isChecked || updated.isIndeterminate) anyChildActive = true;
      return updated;
    });
    const isChecked = this.selection.isChecked(viewFileKey(node));
    const isIndeterminate = !isChecked && node.children.length > 0 && anyChildActive;
    if (!childrenChanged && isChecked === node.isChecked && isIndeterminate === node.isIndeterminate) {
      return node;
    }
    return { ...node, children, isChecked, isIndeterminate };
  }

  // createViewFile always rebuilds a node's children fresh from raw backend
  // order (it isn't sort-aware), so every freshly created/updated node needs
  // its subtree re-sorted here - top-level order alone (the pre-existing
  // reSort/newViewFiles.sort() pass below) doesn't touch nested arrays.
  // Scoped to just this node's own subtree (not the whole forest) to keep
  // the common per-SSE-event cost proportional to what actually changed.
  private sortNewChildren(node: ViewFile): ViewFile {
    if (this.sortComparator == null || node.children.length === 0) {
      return node;
    }
    return { ...node, children: sortTree(node.children, this.sortComparator) };
  }

  // Thin facade over ViewFileCommandService — thread in the current display
  // list so the command service can apply its checked + capability filter.
  bulkCommand(action: FileAction): Observable<WebReaction[]> {
    return this.commands.bulk(action, this.files, this.resolveModelFile);
  }

  setFilterCriteria(criteria: ViewFileFilterCriteria | null): void {
    this.filterCriteria = criteria;
    this.pushViewFiles();
  }

  setComparator(comparator: ViewFileComparator | null): void {
    this.sortComparator = comparator;

    this.logger.debug('Re-sorting view files');
    const newViewFiles = this.sortComparator != null ? sortTree(this.files, this.sortComparator) : [...this.files];
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
      newViewFiles[index] = this.sortNewChildren(this.reconcileCheckedTree(newViewFile));
      if (this.sortComparator != null && this.sortComparator(oldViewFile, newViewFile) !== 0) {
        reSort = true;
      }
    }

    // Do the adds (requires re-sort)
    for (const key of addedKeys) {
      reSort = true;
      const viewFile = createViewFile(modelFiles.get(key)!, this.pairNameMap);
      newViewFiles.push(this.sortNewChildren(this.reconcileCheckedTree(viewFile)));
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

  private pushViewFiles(): void {
    this.filesSubject.next(this.files);

    let filteredFiles = this.files;
    if (this.filterCriteria != null) {
      filteredFiles = this.files.filter(this.filterCriteria);
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

// Every key in the given forest, at any depth - used by checkAll() so "select
// all" reaches nested descendants too, whether or not their parent is
// currently expanded in the flattened display list.
function collectAllKeys(files: readonly ViewFile[]): string[] {
  const keys: string[] = [];
  for (const file of files) {
    keys.push(viewFileKey(file));
    if (file.children.length > 0) {
      keys.push(...collectAllKeys(file.children));
    }
  }
  return keys;
}

// Recursively applies `comparator` at every level of the forest, not just
// the top-level array, so a nested folder's own children sort the same way
// (status/name/size, whichever comparator is active) as the top-level list.
// Preserves reference identity for nodes whose children didn't actually
// reorder, so unaffected rows keep their OnPush identity.
function sortTree(files: readonly ViewFile[], comparator: ViewFileComparator): ViewFile[] {
  const withSortedChildren = files.map((f) => {
    if (f.children.length === 0) {
      return f;
    }
    const sortedChildren = sortTree(f.children, comparator);
    return arraysReferenceEqual(sortedChildren, f.children) ? f : { ...f, children: sortedChildren };
  });
  return [...withSortedChildren].sort(comparator);
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
    a.is_extractable === b.is_extractable &&
    childrenEqual(a.children, b.children)
  );
}

/**
 * Recursively checks whether a folder contains any content that exists locally
 * but not remotely (i.e. content that "Cleanup Local" would remove).
 */
function hasLocalOnlyContent(modelFile: ModelFile): boolean {
  return modelFile.children.some((child) => {
    if (child.remote_size == null) {
      return true;
    }
    return child.is_dir && hasLocalOnlyContent(child);
  });
}

/**
 * Recursively checks whether a folder has any descendant (at any depth) that
 * is independently Queued or Downloading (a standalone nested job). Only
 * meaningful when the top-level folder's own state isn't itself active - see
 * createViewFile, where this is additionally gated on modelFile.state.
 */
function hasActiveDescendant(modelFile: ModelFile): boolean {
  return modelFile.children.some((child) => {
    if (child.state === ModelFileState.QUEUED || child.state === ModelFileState.DOWNLOADING) {
      return true;
    }
    return hasActiveDescendant(child);
  });
}

// A top-level ModelFile's equality must include its nested subtree: a nested
// child's state change (e.g. DOWNLOADING -> DOWNLOADED) doesn't touch any of
// the root's own fields, so without this the root would look unchanged and
// buildViewFromModelFiles would never rebuild its ViewFile - nested rows would
// display stale state. Matched by name rather than index/order since a
// Python set union (backend's _all_children_names) doesn't guarantee a stable
// iteration order across rebuilds.
function childrenEqual(a: readonly ModelFile[], b: readonly ModelFile[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  const byName = new Map(b.map((c) => [c.name, c]));
  return a.every((childA) => {
    const childB = byName.get(childA.name);
    return childB !== undefined && modelFilesEqual(childA, childB);
  });
}

function createViewFile(
  modelFile: ModelFile,
  pairNameMap: Map<string, string>,
  isSelected = false,
  isTopLevel = true,
  ancestorActive = false,
): ViewFile {
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
  const isCleanupLocalable =
    LOCAL_ACTION_STATUSES.includes(status) &&
    modelFile.is_dir &&
    modelFile.remote_size !== null &&
    hasLocalOnlyContent(modelFile);

  // Applies at any depth - a folder anywhere in the stack (top-level or
  // nested) shows this whenever something independently active exists
  // beneath it, so e.g. downloading "NestedTest/Extras/bonus.bin" flags both
  // "NestedTest" and "Extras". Never true simultaneously with the folder's
  // own state being active - see CommandPipeline._find_queue_conflict, which
  // blocks a new independent nested job while any ancestor (at any depth) is
  // already Queued/Downloading. The state guard here is defense-in-depth for
  // that invariant.
  const hasDownloadingDescendant =
    modelFile.is_dir &&
    modelFile.state !== ModelFileState.QUEUED &&
    modelFile.state !== ModelFileState.DOWNLOADING &&
    hasActiveDescendant(modelFile);
  if (hasDownloadingDescendant) {
    capabilities.isStoppable = true; // enables "Stop Nested Downloads"
  }

  // Nested EXTRACT/VALIDATE are out of scope for this feature (they interact
  // with the staging/move pipeline, which never had to account for nested
  // paths) - the backend rejects them unconditionally, so don't offer them.
  if (!isTopLevel) {
    capabilities.isExtractable = false;
    capabilities.isValidatable = false;
    capabilities.validateTooltip = null;
  }

  // An ancestor's own job is consuming this file's transfer already; queuing
  // or stopping it individually doesn't apply. Without this, a child whose
  // state was set to Queued/Downloading purely by participating in the
  // parent's mirror job (ModelBuilder._determine_child_state) would show as
  // individually stoppable, and clicking Stop would hit the backend's
  // "no independent job to stop" failure instead of being disabled up front.
  if (ancestorActive) {
    capabilities.isQueueable = false;
    capabilities.isStoppable = false;
  }

  const childAncestorActive =
    ancestorActive || modelFile.state === ModelFileState.QUEUED || modelFile.state === ModelFileState.DOWNLOADING;
  const children = modelFile.children.map((child) =>
    createViewFile(child, pairNameMap, false, false, childAncestorActive));

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
    isIndeterminate: false,
    ...capabilities,
    isCleanupLocalable,
    hasDownloadingDescendant,
    localCreatedTimestamp: modelFile.local_created_timestamp,
    localModifiedTimestamp: modelFile.local_modified_timestamp,
    remoteCreatedTimestamp: modelFile.remote_created_timestamp,
    remoteModifiedTimestamp: modelFile.remote_modified_timestamp,
    children,
  };
}
