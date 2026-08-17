import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Owns the multi-select "checked" state for view files: the set of checked file
 * keys, the last-checked anchor for shift-range selection, and the {@link checked$}
 * stream that consumers observe.
 *
 * This service is deliberately *input-driven*: every range-based operation takes
 * the current list of file keys (in display order) as an argument rather than
 * reaching back into {@link ViewFileService}. ViewFileService depends on this
 * service, never the reverse — that keeps the dependency acyclic
 * (`view-file-sort.service` already injects ViewFileService, so a back-reference
 * here would form a DI cycle).
 *
 * Keys are the composite `pairId:name` keys produced by `fileKey`/`viewFileKey`.
 */
@Injectable({ providedIn: 'root' })
export class ViewFileSelectionService {
  private readonly checkedSet = new Set<string>();
  private readonly checkedSubject = new BehaviorSubject<Set<string>>(new Set());
  private lastCheckedKey: string | null = null;

  readonly checked$: Observable<Set<string>> = this.checkedSubject.asObservable();

  /** Whether the given key is currently checked. */
  isChecked(key: string): boolean {
    return this.checkedSet.has(key);
  }

  /**
   * Toggle a single key's checked state and make it the shift-range anchor.
   * Emits the updated set on {@link checked$}.
   */
  toggle(key: string): void {
    if (this.checkedSet.has(key)) {
      this.checkedSet.delete(key);
    } else {
      this.checkedSet.add(key);
    }
    this.lastCheckedKey = key;
    this.emit();
  }

  /**
   * Check every key in the contiguous range between the last anchor and the
   * given key (inclusive) within {@param filteredKeys} (the display-order key
   * list). Falls back to a plain {@link toggle} when there is no prior anchor or
   * either endpoint is not present in the list. Updates the anchor to the given
   * key. Emits the updated set on {@link checked$}.
   */
  shiftRange(key: string, filteredKeys: readonly string[]): void {
    if (this.lastCheckedKey == null) {
      this.toggle(key);
      return;
    }
    const lastIdx = filteredKeys.indexOf(this.lastCheckedKey);
    const currIdx = filteredKeys.indexOf(key);
    if (lastIdx < 0 || currIdx < 0) {
      this.toggle(key);
      return;
    }
    const start = Math.min(lastIdx, currIdx);
    const end = Math.max(lastIdx, currIdx);
    for (let i = start; i <= end; i++) {
      this.checkedSet.add(filteredKeys[i]);
    }
    this.lastCheckedKey = key;
    this.emit();
  }

  /** Check every key in the given list. Emits the updated set on {@link checked$}. */
  checkAll(filteredKeys: readonly string[]): void {
    for (const key of filteredKeys) {
      this.checkedSet.add(key);
    }
    this.emit();
  }

  /** Clear all checked keys and the shift anchor. Emits the (empty) set. */
  uncheckAll(): void {
    this.checkedSet.clear();
    this.lastCheckedKey = null;
    this.emit();
  }

  /**
   * Drop every key in {@param removedKeys} from the checked set, re-emitting
   * {@link checked$} only when at least one key was actually present (matching
   * the original in-loop pruning guard). Does NOT touch the shift anchor.
   *
   * @returns whether any checked key was removed (and thus checked$ re-emitted).
   */
  pruneRemoved(removedKeys: readonly string[]): boolean {
    let changed = false;
    for (const key of removedKeys) {
      if (this.checkedSet.delete(key)) {
        changed = true;
      }
    }
    if (changed) {
      this.emit();
    }
    return changed;
  }

  private emit(): void {
    this.checkedSubject.next(new Set(this.checkedSet));
  }
}
