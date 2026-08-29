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
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { Observable } from 'rxjs';
import { CdkVirtualScrollViewport, CdkFixedSizeVirtualScroll, CdkVirtualForOf } from '@angular/cdk/scrolling';

import { ViewFileService } from '../../services/files/view-file.service';
import { WebReaction } from '../../services/utils/rest.service';
import { ViewFile } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { LoggerService } from '../../services/utils/logger.service';
import { NotificationService } from '../../services/utils/notification.service';
import { NotificationLevel, createNotification } from '../../models/notification';
import { fileKey } from '../../services/files/file-key';
import { FileAction } from '../../models/file-action';
import { FileComponent, FileActionEvent } from './file.component';
import { BulkActionBarComponent } from './bulk-action-bar.component';

const MOBILE_FILE_LIST_QUERY = '(max-width: 600px)';

@Component({
  selector: 'app-file-list',
  standalone: true,
  imports: [AsyncPipe, NgTemplateOutlet, FileComponent, BulkActionBarComponent, CdkVirtualScrollViewport, CdkFixedSizeVirtualScroll, CdkVirtualForOf],
  templateUrl: './file-list.component.html',
  styleUrls: ['./file-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileListComponent implements AfterViewInit, OnDestroy {
  @ViewChild(CdkVirtualScrollViewport) viewport?: CdkVirtualScrollViewport;

  private readonly logger = inject(LoggerService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);
  private readonly notifService = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly elRef = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly zone = inject(NgZone);

  private resizeObserver: ResizeObserver | null = null;
  private pendingFrame: number | null = null;
  private mobileMediaQuery: MediaQueryList | null = null;

  readonly useNativeScrolling = signal(false);

  files: Observable<ViewFile[]> = this.viewFileService.filteredFiles$;
  options: Observable<ViewFileOptions> = this.viewFileOptionsService.options$;
  checked$ = this.viewFileService.checked$;
  identify = FileListComponent.identify;

  constructor() {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;

    this.mobileMediaQuery = window.matchMedia(MOBILE_FILE_LIST_QUERY);
    this.useNativeScrolling.set(this.mobileMediaQuery.matches);
    this.mobileMediaQuery.addEventListener('change', this.onMobileMediaChange);
  }

  static identify(_index: number, item: ViewFile): string {
    return fileKey(item.pairId, item.name);
  }

  ngAfterViewInit(): void {
    this.installChromeHeightObserver();
  }

  ngOnDestroy(): void {
    this.mobileMediaQuery?.removeEventListener('change', this.onMobileMediaChange);
    this.mobileMediaQuery = null;
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

    this.zone.runOutsideAngular(() => {
      const update = (): void => {
        this.pendingFrame = null;
        const viewportEl = this.elRef.nativeElement.querySelector<HTMLElement>('.file-viewport');
        if (!viewportEl) return;
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

  private readonly onMobileMediaChange = (event: MediaQueryListEvent): void => {
    this.useNativeScrolling.set(event.matches);
  };

  onSelect(file: ViewFile): void {
    if (file.isSelected) {
      this.viewFileService.unsetSelected();
    } else {
      this.viewFileService.setSelected(file);
    }
  }

  onAction(event: FileActionEvent): void {
    this.viewFileService.command(event.action, event.file).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (data) => this.handleActionResponse(data, event),
      error: (err) => this.handleActionError(err, event),
    });
  }

  private handleActionResponse(reaction: WebReaction, event: FileActionEvent): void {
    if (reaction.success) {
      this.logger.info(reaction.data);
    } else {
      this.failAction(reaction.errorMessage ?? 'Action failed', event);
    }
  }

  private handleActionError(err: unknown, event: FileActionEvent): void {
    this.failAction('Action failed', event);
    this.logger.error('Action failed:', err);
  }

  // A backend rejection leaves the file model unchanged, so the child's
  // ngOnChanges can't recover the row. Surface the error and clear the child's
  // activeAction so the buttons re-enable and the spinner stops without a reload.
  private failAction(text: string, event: FileActionEvent): void {
    this.notifService.show(createNotification(NotificationLevel.DANGER, text, true));
    event.clearActiveAction();
    this.logger.error(text);
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

  onBulkAction(action: FileAction): void {
    this.handleBulkResponse(this.viewFileService.bulkCommand(action));
  }

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
          this.notifService.show(createNotification(
            NotificationLevel.DANGER,
            `${failures} of ${reactions.length} items failed`,
            true,
          ));
        }
      },
      error: (err) => this.logger.error('Bulk action failed:', err),
    });
  }
}
