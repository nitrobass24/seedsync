import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  OnInit,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

import { LogService, LogHistoryEntry } from '../../services/logs/log.service';
import { LogRecord, LogLevel } from '../../models/log-record';
import { DomService } from '../../services/utils/dom.service';
import { LoggerService } from '../../services/utils/logger.service';

@Component({
  selector: 'app-logs-page',
  standalone: true,
  imports: [DatePipe, FormsModule],
  templateUrl: './logs-page.component.html',
  styleUrls: ['./logs-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LogsPageComponent implements OnInit, OnDestroy, AfterViewChecked {
  readonly LogLevel = LogLevel;

  /**
   * Cap on the live-log buffer (#522). During DEBUG logging on an active sync
   * the SSE stream is unbounded; without a cap `records` grows forever, causing
   * unbounded memory, an O(n) array copy per event, and a DOM paragraph per
   * record. We keep a ring-buffer tail of the newest records and drop the
   * oldest on overflow. Full history remains server-queryable via fetchHistory,
   * so no log data is truly lost — only the live tail is bounded.
   */
  static readonly MAX_LIVE_RECORDS = 2000;

  private readonly elementRef = inject(ElementRef);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly logService = inject(LogService);
  private readonly domService = inject(DomService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly logger = inject(LoggerService);

  readonly headerHeight$ = this.domService.headerHeight$;

  records: LogRecord[] = [];
  historyRecords: LogHistoryEntry[] = [];
  searchQuery = '';
  levelFilter = '';
  historyLoaded = false;
  historyLoadFailed = false;

  showScrollToTopButton = false;
  showScrollToBottomButton = false;

  @ViewChild('logHead') logHead!: ElementRef<HTMLElement>;
  @ViewChild('logTail') logTail!: ElementRef<HTMLElement>;

  private pendingScrollToBottom = false;
  private readonly searchChange$ = new Subject<void>();

  // Per-object monotonic trackBy keys (#522) — unique even for identical log
  // lines, since each record/entry is a distinct object.
  private liveSeq = 0;
  private historySeq = 0;
  private readonly recordKey = new WeakMap<LogRecord, number>();
  private readonly historyKey = new WeakMap<LogHistoryEntry, number>();

  ngOnInit(): void {
    this.logService.logs$.pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (record) => {
        const shouldScroll =
          this.elementRef.nativeElement.offsetParent != null &&
          this.logTail &&
          LogsPageComponent.isElementInViewport(this.logTail.nativeElement);

        const next = [...this.records, record];
        // Front-trim the oldest on overflow so the newest record is never
        // dropped (#522). Below the cap this slice is a no-op.
        this.records = next.length > LogsPageComponent.MAX_LIVE_RECORDS
          ? next.slice(next.length - LogsPageComponent.MAX_LIVE_RECORDS)
          : next;
        this.changeDetector.detectChanges();

        if (shouldScroll) {
          this.pendingScrollToBottom = true;
        }
        this.refreshScrollButtonVisibility();
      },
    });

    this.searchChange$.pipe(
      debounceTime(300),
      switchMap(() => {
        // Reset the failure flag per search; catchError sets it on a real fetch
        // failure so the template can distinguish "failed to load" from "no
        // matching history" (both otherwise yield an empty list).
        this.historyLoadFailed = false;
        return this.logService.fetchHistory({
          search: this.searchQuery || undefined,
          level: this.levelFilter || undefined,
          limit: 500,
        }).pipe(
          catchError((err) => {
            this.logger.error('Failed to load log history: %O', err);
            this.historyLoadFailed = true;
            return of([] as LogHistoryEntry[]);
          })
        );
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((entries) => {
      this.historyRecords = entries;
      this.historyLoaded = true;
      this.changeDetector.detectChanges();
    });

    // Initial load
    this.searchChange$.next();
  }

  ngOnDestroy(): void {
    this.searchChange$.complete();
  }

  ngAfterViewChecked(): void {
    if (this.pendingScrollToBottom) {
      this.pendingScrollToBottom = false;
      this.scrollToBottom();
    }
    this.refreshScrollButtonVisibility();
  }

  scrollToTop(): void {
    window.scrollTo(0, 0);
  }

  scrollToBottom(): void {
    window.scrollTo(0, document.body.scrollHeight);
  }

  @HostListener('window:scroll')
  checkScroll(): void {
    this.refreshScrollButtonVisibility();
  }

  onSearchChange(): void {
    this.searchChange$.next();
  }

  onLevelChange(): void {
    this.searchChange$.next();
  }

  /**
   * Stable, collision-free trackBy for the live-log list (#522). A monotonic
   * sequence id is assigned per record *object* (via a WeakMap), so identical
   * repeated log lines (same logger+message in the same millisecond — common
   * under high-throughput DEBUG sync) still get distinct keys. Content-derived
   * keys would collide there and trip Angular's duplicate-key reconcile
   * (NG0955), dropping/mis-associating rows. Keying by object identity lets
   * Angular reuse DOM nodes when the buffer is front-trimmed.
   */
  trackRecord(_index: number, record: LogRecord): number {
    let key = this.recordKey.get(record);
    if (key === undefined) {
      key = this.liveSeq++;
      this.recordKey.set(record, key);
    }
    return key;
  }

  /** Stable, collision-free trackBy for the history list (#522); see trackRecord. */
  trackHistory(_index: number, entry: LogHistoryEntry): number {
    let key = this.historyKey.get(entry);
    if (key === undefined) {
      key = this.historySeq++;
      this.historyKey.set(entry, key);
    }
    return key;
  }

  private refreshScrollButtonVisibility(): void {
    if (!this.logHead || !this.logTail) return;
    this.showScrollToTopButton = !LogsPageComponent.isElementInViewport(
      this.logHead.nativeElement,
    );
    this.showScrollToBottomButton = !LogsPageComponent.isElementInViewport(
      this.logTail.nativeElement,
    );
  }

  private static isElementInViewport(el: HTMLElement): boolean {
    const rect = el.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }
}
