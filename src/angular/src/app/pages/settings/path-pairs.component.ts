import { Component, ChangeDetectionStrategy, ChangeDetectorRef, DestroyRef, inject, OnDestroy } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { EMPTY } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { PathPairsService } from '../../services/settings/path-pairs.service';
import { IntegrationsService } from '../../services/settings/integrations.service';
import { PathPair } from '../../models/path-pair';
import { ArrInstance } from '../../models/arr-instance';

@Component({
  selector: 'app-path-pairs',
  standalone: true,
  imports: [FormsModule, AsyncPipe, NgTemplateOutlet],
  templateUrl: './path-pairs.component.html',
  styleUrls: ['./path-pairs.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PathPairsComponent implements OnDestroy {
  private readonly pathPairsService = inject(PathPairsService);
  private readonly integrationsService = inject(IntegrationsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  readonly pairs$ = this.pathPairsService.pairs$;
  readonly instances$ = this.integrationsService.instances$;

  // Tracks which pair currently has the *arr-picker open. Empty when closed.
  arrPickerPairId: string | null = null;

  // Inline editing state
  editingId: string | null = null;
  editForm: Omit<PathPair, 'id'> = this.emptyForm();

  // Add-new form state
  adding = false;
  addForm: Omit<PathPair, 'id'> = this.emptyForm();

  // Error message
  errorMessage: string | null = null;

  // Double-click delete confirmation
  confirmingDeleteId: string | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnDestroy(): void {
    this.clearConfirmTimer();
  }

  // --- Add ---

  onStartAdd(): void {
    this.cancelEdit();
    this.adding = true;
    this.addForm = this.emptyForm();
    this.errorMessage = null;
  }

  onCancelAdd(): void {
    this.adding = false;
    this.addForm = this.emptyForm();
    this.errorMessage = null;
  }

  onSaveAdd(): void {
    if (!this.addForm.name.trim()) return;
    this.errorMessage = null;
    this.pathPairsService.create(this.addForm).pipe(
      catchError(() => {
        this.errorMessage = 'A path pair with that name already exists.';
        this.cdr.markForCheck();
        return EMPTY;
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((created) => {
      if (!created) {
        this.errorMessage = 'Failed to create path pair. Please try again.';
        this.cdr.markForCheck();
        return;
      }
      this.adding = false;
      this.addForm = this.emptyForm();
      this.cdr.markForCheck();
    });
  }

  // --- Edit ---

  onStartEdit(pair: PathPair): void {
    this.onCancelAdd();
    this.resetConfirmState();
    this.editingId = pair.id;
    this.editForm = {
      name: pair.name,
      remote_path: pair.remote_path,
      local_path: pair.local_path,
      enabled: pair.enabled,
      auto_queue: pair.auto_queue,
      arr_target_ids: [...pair.arr_target_ids],
    };
  }

  onCancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
    this.errorMessage = null;
  }

  onSaveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim()) return;
    this.errorMessage = null;
    this.pathPairsService.update({ id: this.editingId, ...this.editForm }).pipe(
      catchError(() => {
        this.errorMessage = 'A path pair with that name already exists.';
        this.cdr.markForCheck();
        return EMPTY;
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((updated) => {
      if (!updated) {
        this.errorMessage = 'Failed to update path pair. Please try again.';
        this.cdr.markForCheck();
        return;
      }
      this.editingId = null;
      this.editForm = this.emptyForm();
      this.cdr.markForCheck();
    });
  }

  // --- Delete (double-click confirm) ---

  onDelete(pairId: string): void {
    if (this.confirmingDeleteId === pairId) {
      this.clearConfirmTimer();
      this.pathPairsService.remove(pairId).pipe(
        takeUntilDestroyed(this.destroyRef),
      ).subscribe((success) => {
        if (success) {
          this.errorMessage = null;
          this.confirmingDeleteId = null;
        } else {
          this.errorMessage = 'Failed to delete path pair. Please try again.';
          this.confirmingDeleteId = null;
        }
        this.cdr.markForCheck();
      });
    } else {
      this.setConfirming(pairId);
    }
  }

  // --- Toggle fields ---

  onToggleEnabled(pair: PathPair, enabled: boolean): void {
    this.pathPairsService.update({ ...pair, enabled }).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe();
  }

  onToggleAutoQueue(pair: PathPair, autoQueue: boolean): void {
    this.pathPairsService.update({ ...pair, auto_queue: autoQueue }).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe();
  }

  // --- Arr targets ---

  attachedInstances(pair: PathPair, allInstances: ArrInstance[] | null): ArrInstance[] {
    if (!allInstances) return [];
    const byId = new Map(allInstances.map((i) => [i.id, i]));
    return pair.arr_target_ids
      .map((id) => byId.get(id))
      .filter((i): i is ArrInstance => i !== undefined);
  }

  availableInstances(pair: PathPair, allInstances: ArrInstance[] | null): ArrInstance[] {
    if (!allInstances) return [];
    return allInstances.filter((i) => !pair.arr_target_ids.includes(i.id));
  }

  togglePicker(pairId: string): void {
    this.arrPickerPairId = this.arrPickerPairId === pairId ? null : pairId;
  }

  onAttachInstance(pair: PathPair, instance: ArrInstance): void {
    if (pair.arr_target_ids.includes(instance.id)) return;
    const updated = { ...pair, arr_target_ids: [...pair.arr_target_ids, instance.id] };
    this.errorMessage = null;
    this.pathPairsService.update(updated).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (result) => {
        if (!result) {
          this.errorMessage = 'Failed to attach integration. Please try again.';
        } else {
          this.arrPickerPairId = null;
        }
        this.cdr.markForCheck();
      },
      error: () => {
        // 409 from the service is the only path that errors; treat any error
        // as a conflict-style failure and keep the picker open so the user can
        // retry.
        this.errorMessage = 'Failed to attach integration. Please try again.';
        this.cdr.markForCheck();
      },
    });
  }

  onDetachInstance(pair: PathPair, instanceId: string): void {
    const updated = {
      ...pair,
      arr_target_ids: pair.arr_target_ids.filter((id) => id !== instanceId),
    };
    this.errorMessage = null;
    this.pathPairsService.update(updated).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (result) => {
        if (!result) {
          this.errorMessage = 'Failed to detach integration. Please try again.';
        }
        this.cdr.markForCheck();
      },
      error: () => {
        this.errorMessage = 'Failed to detach integration. Please try again.';
        this.cdr.markForCheck();
      },
    });
  }

  // --- Helpers ---

  private cancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
    this.resetConfirmState();
  }

  private emptyForm(): Omit<PathPair, 'id'> {
    return {
      name: '',
      remote_path: '',
      local_path: '',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    };
  }

  private setConfirming(pairId: string): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = pairId;
    this.confirmResetTimer = setTimeout(() => {
      this.confirmingDeleteId = null;
      this.confirmResetTimer = null;
      this.cdr.markForCheck();
    }, 3000);
  }

  private resetConfirmState(): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = null;
  }

  private clearConfirmTimer(): void {
    if (this.confirmResetTimer !== null) {
      clearTimeout(this.confirmResetTimer);
      this.confirmResetTimer = null;
    }
  }
}
