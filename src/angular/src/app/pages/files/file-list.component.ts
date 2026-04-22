import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe } from '@angular/common';
import { Observable } from 'rxjs';
import { CdkVirtualScrollViewport, CdkFixedSizeVirtualScroll, CdkVirtualForOf } from '@angular/cdk/scrolling';

import { ViewFileService } from '../../services/files/view-file.service';
import { WebReaction } from '../../services/utils/rest.service';
import { ViewFile } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { LoggerService } from '../../services/utils/logger.service';
import { fileKey } from '../../services/files/file-key';
import { FileComponent } from './file.component';
import { BulkActionBarComponent } from './bulk-action-bar.component';

@Component({
  selector: 'app-file-list',
  standalone: true,
  imports: [AsyncPipe, FileComponent, BulkActionBarComponent, CdkVirtualScrollViewport, CdkFixedSizeVirtualScroll, CdkVirtualForOf],
  templateUrl: './file-list.component.html',
  styleUrls: ['./file-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileListComponent implements AfterViewInit, OnDestroy {
  @ViewChild(CdkVirtualScrollViewport) viewport?: CdkVirtualScrollViewport;

  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly elRef = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly zone = inject(NgZone);

  private resizeObserver: ResizeObserver | null = null;
  private pendingFrame: number | null = null;

  files: Observable<ViewFile[]> = this.viewFileService.filteredFiles$;
  options: Observable<ViewFileOptions> = this.viewFileOptionsService.options$;
  checked$ = this.viewFileService.checked$;
  identify = FileListComponent.identify;

  static identify(_index: number, item: ViewFile): string {
    return fileKey(item.pairId, item.name);
  }

  ngAfterViewInit(): void {
    this.installChromeHeightObserver();
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    if (this.pendingFrame !== null) {
      cancelAnimationFrame(this.pendingFrame);
      this.pendingFrame = null;
    }
    document.documentElement.style.removeProperty('--file-list-chrome-height');
  }

  // The virtual-scroll viewport's height must equal
  //   100dvh − (sticky top header + file-options bar + column header + bulk-action-bar)
  // Hardcoding those heights breaks whenever a breakpoint shifts, a notification
  // banner appears, or the browser's own chrome changes between iOS Safari/Chrome
  // and Android Chrome/Firefox. Instead, measure the viewport's page-Y position
  // (everything stacked above it flows into that offset) and expose it to CSS.
  private installChromeHeightObserver(): void {
    if (typeof ResizeObserver === 'undefined') return;
    const viewportEl = this.viewport?.elementRef.nativeElement as HTMLElement | undefined;
    if (!viewportEl) return;

    this.zone.runOutsideAngular(() => {
      const update = (): void => {
        this.pendingFrame = null;
        const top = viewportEl.getBoundingClientRect().top + window.scrollY;
        const chrome = Math.max(0, Math.ceil(top));
        document.documentElement.style.setProperty(
          '--file-list-chrome-height', `${chrome}px`,
        );
        this.viewport?.checkViewportSize();
      };

      const schedule = (): void => {
        if (this.pendingFrame !== null) return;
        this.pendingFrame = requestAnimationFrame(update);
      };

      this.resizeObserver = new ResizeObserver(schedule);

      // Observe the elements whose size contributes to the chrome above the
      // list. The #file-list host covers the column header and bulk-action-bar
      // because they live inside it above .file-viewport.
      const targets: (Element | null)[] = [
        document.querySelector('#top-header'),
        document.querySelector('#file-options'),
        this.elRef.nativeElement,
      ];
      for (const t of targets) {
        if (t) this.resizeObserver!.observe(t);
      }

      schedule();
    });
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

  onValidate(file: ViewFile): void {
    this.viewFileService.validate(file).pipe(
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
