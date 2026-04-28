import { Component, ChangeDetectionStrategy, ChangeDetectorRef, DestroyRef, inject, OnDestroy } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { EMPTY } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { IntegrationsService, TestConnectionResult } from '../../services/settings/integrations.service';
import { ArrInstance, ArrInstanceCreate, ArrKind, ARR_KINDS } from '../../models/arr-instance';
import { REDACTED_SENTINEL } from '../../models/config';

interface InstanceForm {
  name: string;
  kind: ArrKind;
  url: string;
  api_key: string;
  enabled: boolean;
}

@Component({
  selector: 'app-integrations',
  standalone: true,
  imports: [FormsModule, AsyncPipe, NgTemplateOutlet],
  templateUrl: './integrations.component.html',
  styleUrls: ['./integrations.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IntegrationsComponent implements OnDestroy {
  private readonly integrationsService = inject(IntegrationsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  readonly instances$ = this.integrationsService.instances$;
  readonly kinds = ARR_KINDS;

  editingId: string | null = null;
  editForm: InstanceForm = this.emptyForm();

  adding = false;
  addForm: InstanceForm = this.emptyForm();

  errorMessage: string | null = null;

  // Per-instance test state
  testingId: string | null = null;
  testResults = new Map<string, TestConnectionResult>();

  // Double-click delete confirmation
  confirmingDeleteId: string | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnDestroy(): void {
    this.clearConfirmTimer();
  }

  // --- Add ---

  onStartAdd(kind: ArrKind): void {
    this.cancelEdit();
    this.adding = true;
    this.addForm = this.emptyForm(kind);
    this.errorMessage = null;
  }

  onCancelAdd(): void {
    this.adding = false;
    this.addForm = this.emptyForm();
    this.errorMessage = null;
  }

  onSaveAdd(): void {
    if (!this.addForm.name.trim()) {
      this.errorMessage = 'Name is required.';
      return;
    }
    this.errorMessage = null;
    const payload: ArrInstanceCreate = {
      name: this.addForm.name.trim(),
      kind: this.addForm.kind,
      url: this.addForm.url.trim(),
      api_key: this.addForm.api_key,
      enabled: this.addForm.enabled,
    };
    this.integrationsService.create(payload).pipe(
      catchError(() => {
        this.errorMessage = 'An integration with that name already exists.';
        this.cdr.markForCheck();
        return EMPTY;
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((created) => {
      if (!created) {
        this.errorMessage = 'Failed to create integration. Please try again.';
        this.cdr.markForCheck();
        return;
      }
      this.adding = false;
      this.addForm = this.emptyForm();
      this.cdr.markForCheck();
    });
  }

  // --- Edit ---

  onStartEdit(instance: ArrInstance): void {
    this.onCancelAdd();
    this.resetConfirmState();
    this.editingId = instance.id;
    this.editForm = {
      name: instance.name,
      kind: instance.kind,
      url: instance.url,
      api_key: instance.api_key, // already redacted by server when present
      enabled: instance.enabled,
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
    this.integrationsService.update(this.editingId, {
      name: this.editForm.name.trim(),
      kind: this.editForm.kind,
      url: this.editForm.url.trim(),
      api_key: this.editForm.api_key, // sentinel preserved if untouched
      enabled: this.editForm.enabled,
    }).pipe(
      catchError(() => {
        this.errorMessage = 'An integration with that name already exists.';
        this.cdr.markForCheck();
        return EMPTY;
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((updated) => {
      if (!updated) {
        this.errorMessage = 'Failed to update integration. Please try again.';
        this.cdr.markForCheck();
        return;
      }
      this.editingId = null;
      this.editForm = this.emptyForm();
      this.cdr.markForCheck();
    });
  }

  // --- Delete (double-click confirm) ---

  onDelete(id: string): void {
    if (this.confirmingDeleteId === id) {
      this.clearConfirmTimer();
      this.integrationsService.remove(id).pipe(
        takeUntilDestroyed(this.destroyRef),
      ).subscribe((success) => {
        if (success) {
          this.errorMessage = null;
          this.confirmingDeleteId = null;
          this.testResults.delete(id);
        } else {
          this.errorMessage = 'Failed to delete integration. Please try again.';
          this.confirmingDeleteId = null;
        }
        this.cdr.markForCheck();
      });
    } else {
      this.setConfirming(id);
    }
  }

  // --- Toggle enabled ---

  onToggleEnabled(instance: ArrInstance, enabled: boolean): void {
    this.integrationsService.update(instance.id, { enabled }).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe();
  }

  // --- Test connection ---

  onTest(id: string): void {
    this.testingId = id;
    this.testResults.delete(id);
    this.integrationsService.test(id).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((result) => {
      this.testResults.set(id, result);
      this.testingId = null;
      this.cdr.markForCheck();
    });
  }

  testResult(id: string): TestConnectionResult | undefined {
    return this.testResults.get(id);
  }

  isTesting(id: string): boolean {
    return this.testingId === id;
  }

  isApiKeyRedacted(value: string): boolean {
    return value === REDACTED_SENTINEL;
  }

  kindLabel(kind: ArrKind): string {
    return kind === 'sonarr' ? 'Sonarr' : 'Radarr';
  }

  // --- Helpers ---

  private cancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
    this.resetConfirmState();
  }

  private emptyForm(kind: ArrKind = 'sonarr'): InstanceForm {
    return { name: '', kind, url: '', api_key: '', enabled: true };
  }

  private setConfirming(id: string): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = id;
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
