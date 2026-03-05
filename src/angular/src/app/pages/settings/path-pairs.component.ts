import { Component, ChangeDetectionStrategy, inject, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsyncPipe } from '@angular/common';
import { Subscription } from 'rxjs';

import { PathPairsService } from '../../services/settings/path-pairs.service';
import { PathPair } from '../../models/path-pair';

@Component({
  selector: 'app-path-pairs',
  standalone: true,
  imports: [FormsModule, AsyncPipe],
  templateUrl: './path-pairs.component.html',
  styleUrls: ['./path-pairs.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PathPairsComponent implements OnDestroy {
  private readonly pathPairsService = inject(PathPairsService);
  readonly pairs$ = this.pathPairsService.pairs$;

  // Inline editing state
  editingId: string | null = null;
  editForm: Omit<PathPair, 'id'> = this.emptyForm();

  // Add-new form state
  adding = false;
  addForm: Omit<PathPair, 'id'> = this.emptyForm();

  // Double-click delete confirmation
  confirmingDeleteId: string | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;
  private subscriptions: Subscription[] = [];

  ngOnDestroy(): void {
    this.clearConfirmTimer();
    this.subscriptions.forEach((s) => s.unsubscribe());
  }

  // --- Add ---

  onStartAdd(): void {
    this.cancelEdit();
    this.adding = true;
    this.addForm = this.emptyForm();
  }

  onCancelAdd(): void {
    this.adding = false;
    this.addForm = this.emptyForm();
  }

  onSaveAdd(): void {
    if (!this.addForm.name.trim()) return;
    this.subscriptions.push(
      this.pathPairsService.create(this.addForm).subscribe(() => {
        this.adding = false;
        this.addForm = this.emptyForm();
      }),
    );
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
    };
  }

  onCancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
  }

  onSaveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim()) return;
    this.subscriptions.push(
      this.pathPairsService.update({ id: this.editingId, ...this.editForm }).subscribe(() => {
        this.editingId = null;
        this.editForm = this.emptyForm();
      }),
    );
  }

  // --- Delete (double-click confirm) ---

  onDelete(pairId: string): void {
    if (this.confirmingDeleteId === pairId) {
      this.clearConfirmTimer();
      this.confirmingDeleteId = null;
      this.subscriptions.push(this.pathPairsService.remove(pairId).subscribe());
    } else {
      this.setConfirming(pairId);
    }
  }

  // --- Toggle fields ---

  onToggleEnabled(pair: PathPair): void {
    this.subscriptions.push(
      this.pathPairsService.update({ ...pair, enabled: !pair.enabled }).subscribe(),
    );
  }

  onToggleAutoQueue(pair: PathPair): void {
    this.subscriptions.push(
      this.pathPairsService.update({ ...pair, auto_queue: !pair.auto_queue }).subscribe(),
    );
  }

  // --- Helpers ---

  private cancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
    this.resetConfirmState();
  }

  private emptyForm(): Omit<PathPair, 'id'> {
    return { name: '', remote_path: '', local_path: '', enabled: true, auto_queue: false };
  }

  private setConfirming(pairId: string): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = pairId;
    this.confirmResetTimer = setTimeout(() => {
      this.confirmingDeleteId = null;
      this.confirmResetTimer = null;
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
