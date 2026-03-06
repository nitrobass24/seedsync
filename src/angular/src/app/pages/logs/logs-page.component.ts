import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  HostListener,
  OnInit,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

import { LogService, LogHistoryEntry } from '../../services/logs/log.service';
import { LogRecord, LogLevel } from '../../models/log-record';
import { DomService } from '../../services/utils/dom.service';

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

  private readonly elementRef = inject(ElementRef);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly logService = inject(LogService);
  private readonly domService = inject(DomService);

  readonly headerHeight$ = this.domService.headerHeight$;

  records: LogRecord[] = [];
  historyRecords: LogHistoryEntry[] = [];
  searchQuery = '';
  levelFilter = '';
  historyLoaded = false;

  showScrollToTopButton = false;
  showScrollToBottomButton = false;

  @ViewChild('logHead') logHead!: ElementRef<HTMLElement>;
  @ViewChild('logTail') logTail!: ElementRef<HTMLElement>;

  private pendingScrollToBottom = false;
  private logsSub!: Subscription;
  private historySub!: Subscription;
  private readonly searchChange$ = new Subject<void>();

  ngOnInit(): void {
    this.logsSub = this.logService.logs$.subscribe({
      next: (record) => {
        const shouldScroll =
          this.elementRef.nativeElement.offsetParent != null &&
          this.logTail &&
          LogsPageComponent.isElementInViewport(this.logTail.nativeElement);

        this.records = [...this.records, record];
        this.changeDetector.detectChanges();

        if (shouldScroll) {
          this.pendingScrollToBottom = true;
        }
        this.refreshScrollButtonVisibility();
      },
    });

    this.historySub = this.searchChange$.pipe(
      debounceTime(300),
      switchMap(() => this.logService.fetchHistory({
        search: this.searchQuery || undefined,
        level: this.levelFilter || undefined,
        limit: 500,
      }).pipe(
        catchError(() => of([] as LogHistoryEntry[]))
      )),
    ).subscribe((entries) => {
      this.historyRecords = entries;
      this.historyLoaded = true;
      this.changeDetector.detectChanges();
    });

    // Initial load
    this.searchChange$.next();
  }

  ngOnDestroy(): void {
    this.logsSub?.unsubscribe();
    this.historySub?.unsubscribe();
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
