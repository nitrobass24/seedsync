import { Component, ChangeDetectionStrategy, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe } from '@angular/common';
import { Observable } from 'rxjs';

import { ViewFileService } from '../../services/files/view-file.service';
import { WebReaction } from '../../services/utils/rest.service';
import { ViewFile } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { LoggerService } from '../../services/utils/logger.service';
import { FileComponent } from './file.component';
import { BulkActionBarComponent } from './bulk-action-bar.component';

@Component({
  selector: 'app-file-list',
  standalone: true,
  imports: [AsyncPipe, FileComponent, BulkActionBarComponent],
  templateUrl: './file-list.component.html',
  styleUrls: ['./file-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileListComponent {
  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);
  private readonly destroyRef = inject(DestroyRef);

  files: Observable<ViewFile[]> = this.viewFileService.filteredFiles$;
  options: Observable<ViewFileOptions> = this.viewFileOptionsService.options$;
  checked$ = this.viewFileService.checked$;
  identify = FileListComponent.identify;

  static identify(index: number, item: ViewFile): string {
    return `${item.pairId || ''}:${item.name}`;
  }

  onSelect(file: ViewFile): void {
    if (file.isSelected) {
      this.viewFileService.unsetSelected();
    } else {
      this.viewFileService.setSelected(file);
    }
  }

  onQueue(file: ViewFile): void {
    this.viewFileService.queue(file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(data => {
      this.logger.info(data);
    });
  }

  onStop(file: ViewFile): void {
    this.viewFileService.stop(file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(data => {
      this.logger.info(data);
    });
  }

  onExtract(file: ViewFile): void {
    this.viewFileService.extract(file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(data => {
      this.logger.info(data);
    });
  }

  onDeleteLocal(file: ViewFile): void {
    this.viewFileService.deleteLocal(file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(data => {
      this.logger.info(data);
    });
  }

  onDeleteRemote(file: ViewFile): void {
    this.viewFileService.deleteRemote(file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(data => {
      this.logger.info(data);
    });
  }

  onCheck(event: {file: ViewFile, shiftKey: boolean}): void {
    if (event.shiftKey) {
      this.viewFileService.shiftCheck(event.file);
    } else {
      this.viewFileService.toggleCheck(event.file);
    }
  }

  onCheckAll(): void {
    this.viewFileService.checkAll();
  }

  onUncheckAll(): void {
    this.viewFileService.uncheckAll();
  }

  onBulkQueue(): void { this.handleBulkResponse(this.viewFileService.bulkQueue()); }
  onBulkStop(): void { this.handleBulkResponse(this.viewFileService.bulkStop()); }
  onBulkDeleteLocal(): void { this.handleBulkResponse(this.viewFileService.bulkDeleteLocal()); }
  onBulkDeleteRemote(): void { this.handleBulkResponse(this.viewFileService.bulkDeleteRemote()); }

  private handleBulkResponse(action$: Observable<WebReaction[]>): void {
    action$.pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (reactions) => {
        let failures = 0;
        reactions.forEach(r => {
          if (r.success) {
            if (r.data) this.logger.info(r.data);
          } else {
            failures++;
            this.logger.error('Bulk item failed:', r.errorMessage || r.data);
          }
        });
        if (failures > 0) {
          this.logger.warn(`Bulk action: ${failures} of ${reactions.length} items failed`);
        }
      },
      error: (err) => this.logger.error('Bulk action failed:', err),
    });
  }
}
