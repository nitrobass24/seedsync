import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  OnInit,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  CdkFixedSizeVirtualScroll,
  CdkVirtualForOf,
  CdkVirtualScrollViewport,
} from '@angular/cdk/scrolling';
import { Subject } from 'rxjs';
import { auditTime, debounceTime, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

import { LogService, LogHistoryEntry } from '../../services/logs/log.service';
import { LogRecord, LogLevel } from '../../models/log-record';
import { DomService } from '../../services/utils/dom.service';
import { LoggerService } from '../../services/utils/logger.service';

@Component({
  selector: 'app-logs-page',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    CdkVirtualScrollViewport,
    CdkFixedSizeVirtualScroll,
    CdkVirtualForOf,
  ],
  templateUrl: './logs-page.component.html',
  styleUrls: ['./logs-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LogsPageComponent implements OnInit, OnDestroy, AfterViewInit {
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

  /**
   * Fixed row height (px) for the CDK virtual-scroll viewport (#539). The live
   * list is virtualized with `CdkFixedSizeVirtualScroll`, so every row MUST be
   * exactly this tall or the viewport's scroll math drifts (rows clip/overlap).
   * To keep rows uniform: the message is rendered single-line (truncated with
   * ellipsis, full text in `title`) and an exception traceback is shown in an
   * absolutely-positioned popover (see toggleTraceback) rather than expanding
   * the row inline. Keep this in sync with `p.record` height in the SCSS.
   */
  static readonly ROW_HEIGHT = 22;

  /**
   * Window (ms) over which incoming SSE records are batched before a single
   * change-detection pass (#539). Under high-throughput DEBUG sync the stream
   * emits many records per frame; running `detectChanges()` per record pegs the
   * main thread. `auditTime` coalesces a burst into one render. ~16ms ≈ one
   * frame at 60fps.
   */
  static readonly BATCH_WINDOW_MS = 16;

  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly logService = inject(LogService);
  private readonly domService = inject(DomService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly logger = inject(LoggerService);

  readonly headerHeight$ = this.domService.headerHeight$;

  // Template-accessible alias of the static fixed row height (Angular templates
  // cannot read static class members).
  readonly rowHeight = LogsPageComponent.ROW_HEIGHT;

  records: LogRecord[] = [];
  historyRecords: LogHistoryEntry[] = [];
  searchQuery = '';
  levelFilter = '';
  historyLoaded = false;
  historyLoadFailed = false;

  showScrollToTopButton = false;
  showScrollToBottomButton = false;

  /** Record whose traceback popover is currently open (object identity), or null. */
  expandedTraceback: LogRecord | null = null;

  @ViewChild(CdkVirtualScrollViewport) viewport?: CdkVirtualScrollViewport;

  // Records arriving since the last flushed change-detection window (#539). The
  // batch pipe drains this into `records` once per BATCH_WINDOW_MS.
  private pendingRecords: LogRecord[] = [];
  private readonly recordBatch$ = new Subject<void>();
  private readonly searchChange$ = new Subject<void>();


  ngOnInit(): void {
    this.logService.logs$.pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (record) => {
        // Buffer the record and signal the batch pipe; the actual list mutation
        // and change detection happen once per window (#539), not per record.
        this.pendingRecords.push(record);
        this.recordBatch$.next();
      },
    });

    // Batch incoming records: at most one change-detection pass per window even
    // under a flood of SSE events (#539). auditTime emits on the trailing edge,
    // so the first record schedules a flush and any records arriving within the
    // window ride along on that same flush.
    this.recordBatch$.pipe(
      auditTime(LogsPageComponent.BATCH_WINDOW_MS),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(() => this.flushPendingRecords());

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

  ngAfterViewInit(): void {
    // The viewport scroll position (not the window) now drives scroll-button
    // visibility (#539). Subscribe outside the SSE batch so manual user scrolls
    // also keep the buttons in sync.
    const viewport = this.viewport;
    if (!viewport) return;
    viewport.elementScrolled().pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(() => {
      this.refreshScrollButtonVisibility();
      this.changeDetector.markForCheck();
    });
    this.refreshScrollButtonVisibility();
    this.changeDetector.markForCheck();
  }

  ngOnDestroy(): void {
    this.recordBatch$.complete();
    this.searchChange$.complete();
  }

  scrollToTop(): void {
    this.viewport?.scrollToIndex(0, 'smooth');
  }

  scrollToBottom(): void {
    const lastIndex = Math.max(0, this.records.length - 1);
    this.viewport?.scrollToIndex(lastIndex, 'smooth');
  }

  onSearchChange(): void {
    this.searchChange$.next();
  }

  onLevelChange(): void {
    this.searchChange$.next();
  }

  /** Toggle the absolutely-positioned traceback popover for a record (#539). */
  toggleTraceback(record: LogRecord): void {
    this.expandedTraceback = this.expandedTraceback === record ? null : record;
    this.changeDetector.markForCheck();
  }

  /**
   * Track by object identity (#522): identical log lines are still distinct
   * objects, so identity never collides where a content-derived key would
   * (NG0955). Arrow field so `this`-less `*cdkVirtualFor` can call it (#539).
   */
  readonly trackRecord = (_index: number, record: LogRecord): LogRecord => record;

  /** Track history entries by object identity; see trackRecord. */
  trackHistory(_index: number, entry: LogHistoryEntry): LogHistoryEntry {
    return entry;
  }


  /**
   * Drain the pending SSE records into the live buffer in a single pass (#539).
   * Auto-scroll-to-bottom is preserved by sampling "was the viewport pinned to
   * the bottom?" BEFORE applying the batch, then re-pinning afterward only if it
   * was. OnPush: this runs inside an async (auditTime) callback, so we must
   * explicitly run change detection.
   */
  private flushPendingRecords(): void {
    if (this.pendingRecords.length === 0) return;

    const wasAtBottom = this.isViewportAtBottom();

    const next = [...this.records, ...this.pendingRecords];
    this.pendingRecords = [];
    // Front-trim the oldest on overflow so the newest record is never dropped
    // (#522). Below the cap this slice is a no-op.
    this.records = next.length > LogsPageComponent.MAX_LIVE_RECORDS
      ? next.slice(next.length - LogsPageComponent.MAX_LIVE_RECORDS)
      : next;

    // Synchronous CD so the viewport's data length is up to date before we ask
    // it to scroll to the new last index.
    this.changeDetector.detectChanges();

    if (wasAtBottom) {
      this.viewport?.scrollToIndex(Math.max(0, this.records.length - 1));
    }
    this.refreshScrollButtonVisibility();
  }

  /**
   * True when the viewport is scrolled to (or near) the bottom. Uses the CDK
   * viewport's own scroll metrics rather than window/getBoundingClientRect
   * (#539). A small slack absorbs sub-pixel rounding so auto-scroll stays
   * sticky once the user is at the tail.
   */
  private isViewportAtBottom(): boolean {
    const viewport = this.viewport;
    if (!viewport) return true; // no viewport yet -> default to pinned
    // measureScrollOffset('bottom') is the distance from the scrolled content's
    // bottom to the viewport's bottom edge; 0 means fully scrolled down.
    return viewport.measureScrollOffset('bottom') <= LogsPageComponent.ROW_HEIGHT;
  }

  private refreshScrollButtonVisibility(): void {
    const viewport = this.viewport;
    if (!viewport) {
      this.showScrollToTopButton = false;
      this.showScrollToBottomButton = false;
      return;
    }
    const hasOverflow = viewport.measureScrollOffset('top') +
      viewport.measureScrollOffset('bottom') > 0;
    this.showScrollToTopButton = hasOverflow && viewport.measureScrollOffset('top') > 0;
    this.showScrollToBottomButton =
      hasOverflow && viewport.measureScrollOffset('bottom') > 0;
  }
}
