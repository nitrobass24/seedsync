import { Component, ChangeDetectionStrategy, ChangeDetectorRef, inject, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { EMPTY, Subscription } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { PathPairsService } from '../../services/settings/path-pairs.service';
import { PathPair } from '../../models/path-pair';

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
  private readonly cdr = inject(ChangeDetectorRef);
  readonly pairs$ = this.pathPairsService.pairs$;

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
  private subscriptions: Subscription[] = [];

  ngOnDestroy(): void {
    this.clearConfirmTimer();
    this.subscriptions.forEach((s) => {
      s.unsubscribe();
    });
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
    this.subscriptions.push(
      this.pathPairsService.create(this.addForm).pipe(
        catchError((err: HttpErrorResponse) => {
          if (err.status === 409) {
            this.errorMessage = 'A path pair with that name already exists.';
          }
          this.cdr.markForCheck();
          return EMPTY;
        }),
      ).subscribe((created) => {
        if (!created) {
          this.cdr.markForCheck();
          return;
        }
        this.adding = false;
        this.addForm = this.emptyForm();
        this.cdr.markForCheck();
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
    this.errorMessage = null;
  }

  onSaveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim()) return;
    this.errorMessage = null;
    this.subscriptions.push(
      this.pathPairsService.update({ id: this.editingId, ...this.editForm }).pipe(
        catchError((err: HttpErrorResponse) => {
          if (err.status === 409) {
            this.errorMessage = 'A path pair with that name already exists.';
          }
          this.cdr.markForCheck();
          return EMPTY;
        }),
      ).subscribe((updated) => {
        if (!updated) {
          this.cdr.markForCheck();
          return;
        }
        this.editingId = null;
        this.editForm = this.emptyForm();
        this.cdr.markForCheck();
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

  onToggleEnabled(pair: PathPair, enabled: boolean): void {
    this.subscriptions.push(
      this.pathPairsService.update({ ...pair, enabled }).subscribe(),
    );
  }

  onToggleAutoQueue(pair: PathPair, autoQueue: boolean): void {
    this.subscriptions.push(
      this.pathPairsService.update({ ...pair, auto_queue: autoQueue }).subscribe(),
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
