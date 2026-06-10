import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ChangeDetectorRef } from '@angular/core';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import { ScrollingModule, CdkVirtualScrollViewport } from '@angular/cdk/scrolling';

import { LogsPageComponent } from './logs-page.component';
import { LogService } from '../../services/logs/log.service';
import { DomService } from '../../services/utils/dom.service';
import { LoggerService } from '../../services/utils/logger.service';
import { LogRecord, LogLevel } from '../../models/log-record';

function loggerMock() {
  return { error: vi.fn(), debug: vi.fn(), info: vi.fn(), warn: vi.fn() };
}

/**
 * Covers #516: a log-history fetch failure must render a distinct "failed to
 * load" state, not be indistinguishable from an empty (successful) result.
 * The debounced search pipe is not exercised here (the failure flag is set by
 * its catchError); these tests verify the template renders each state.
 */
describe('LogsPageComponent history failure state (#516)', () => {
  let fixture: ComponentFixture<LogsPageComponent>;
  let component: LogsPageComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$: new Subject(), fetchHistory: vi.fn().mockReturnValue(of([])) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    vi.restoreAllMocks();
  });

  function renderedText(): string {
    return (fixture.nativeElement as HTMLElement).textContent ?? '';
  }

  it('renders a distinct failure message when the history fetch failed', () => {
    component.historyLoaded = true;
    component.historyLoadFailed = true;
    component.historyRecords = [];
    fixture.detectChanges();

    expect(renderedText()).toContain('Failed to load log history');
  });

  it('shows no failure message for an empty (successful) result', () => {
    component.historyLoaded = true;
    component.historyLoadFailed = false;
    component.historyRecords = [];
    fixture.detectChanges();

    expect(renderedText()).not.toContain('Failed to load log history');
  });
});

/**
 * Covers #522 + #539: the live-log buffer is capped (ring-buffer front-trim of
 * the oldest), uses a stable collision-free trackBy, AND batches incoming SSE
 * records into one change-detection pass per window before applying them. With
 * batching the records land in the buffer only after the auditTime window
 * elapses, so these tests use fake timers and advance past BATCH_WINDOW_MS.
 */
describe('LogsPageComponent live-log buffer + batching (#522, #539)', () => {
  let fixture: ComponentFixture<LogsPageComponent>;
  let component: LogsPageComponent;
  let logs$: Subject<LogRecord>;

  function makeRecord(i: number): LogRecord {
    return {
      time: new Date(1_700_000_000_000 + i * 1000),
      level: LogLevel.DEBUG,
      loggerName: `logger-${i}`,
      message: `message ${i}`,
      exceptionTraceback: null,
    };
  }

  // Flush the auditTime batch window so pendingRecords drain into `records`.
  function flushBatch(): void {
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);
    fixture.detectChanges();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    logs$ = new Subject<LogRecord>();
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$, fetchHistory: vi.fn().mockReturnValue(of([])) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    // ngOnInit subscribes to logs$ here.
    fixture.detectChanges();
    // Give the virtual-scroll viewport a stable height so it renders rows.
    const viewportEl = (fixture.nativeElement as HTMLElement)
      .querySelector('cdk-virtual-scroll-viewport') as HTMLElement | null;
    if (viewportEl) viewportEl.style.height = '400px';
    component.viewport?.checkViewportSize();
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function renderedText(): string {
    return (fixture.nativeElement as HTMLElement).textContent ?? '';
  }

  it('appends records in order while under the cap', () => {
    const r0 = makeRecord(0);
    const r1 = makeRecord(1);
    const r2 = makeRecord(2);
    logs$.next(r0);
    logs$.next(r1);
    logs$.next(r2);
    flushBatch();

    expect(component.records.length).toBe(3);
    expect(component.records).toEqual([r0, r1, r2]);
  });

  it('caps the buffer and drops the oldest, never the newest', () => {
    const total = LogsPageComponent.MAX_LIVE_RECORDS + 50;
    let last: LogRecord | undefined;
    for (let i = 0; i < total; i++) {
      last = makeRecord(i);
      logs$.next(last);
    }
    flushBatch();

    expect(component.records.length).toBe(LogsPageComponent.MAX_LIVE_RECORDS);
    // First 50 emitted records were front-trimmed away.
    expect(component.records[0].message).toBe('message 50');
    // Newest record is always retained.
    expect(component.records[component.records.length - 1]).toBe(last);
  });

  it('batches a burst into ONE change-detection pass per window (#539)', () => {
    // Spy on the component's own ChangeDetectorRef without touching the private
    // field directly (strict TS forbids `component['changeDetector']`).
    const cdr = (component as unknown as { changeDetector: ChangeDetectorRef })
      .changeDetector;
    const detectSpy = vi.spyOn(cdr, 'detectChanges');
    detectSpy.mockClear();

    // A flood of records within a single window.
    for (let i = 0; i < 10; i++) {
      logs$.next(makeRecord(i));
    }
    // Nothing applied yet — the records are buffered, not yet rendered.
    expect(component.records.length).toBe(0);
    expect(detectSpy).not.toHaveBeenCalled();

    // Advance only the batch window so the audit fires; flushPendingRecords runs
    // its OWN detectChanges synchronously here. We deliberately do NOT call
    // fixture.detectChanges() so the spy count reflects exactly the per-window
    // change detection.
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);

    // All ten landed, but detectChanges ran once for the whole window.
    expect(component.records.length).toBe(10);
    expect(detectSpy).toHaveBeenCalledTimes(1);
  });

  it('renders the latest record text after the window flushes', () => {
    logs$.next(makeRecord(0));
    logs$.next(makeRecord(1));
    flushBatch();

    const text = renderedText();
    expect(text).toContain('message 1');
    expect(text).toContain(LogLevel.DEBUG);
    expect(text).toContain('logger-1');
  });

  it('trackRecord is stable per record object and never collides for identical lines', () => {
    const record = makeRecord(7);
    const key = component.trackRecord(0, record);
    // Stable across calls and across positions (same object -> same key).
    expect(component.trackRecord(99, record)).toBe(key);

    // Two DISTINCT objects with IDENTICAL content must get DIFFERENT keys —
    // the regression that content-derived keys (time+logger+message) caused.
    const dupA = makeRecord(0);
    const dupB = { ...dupA };
    expect(dupA).toEqual(dupB);
    expect(component.trackRecord(0, dupA)).not.toBe(component.trackRecord(1, dupB));
  });

  it('trackHistory is stable per entry object and never collides for identical entries', () => {
    const entry = { timestamp: '2026-06-01 12:00:00', level: 'INFO', logger: 'h', process: 'p', thread: 't', message: 'm' };
    const key = component.trackHistory(0, entry);
    expect(component.trackHistory(42, entry)).toBe(key);

    const dup = { ...entry };
    expect(component.trackHistory(0, dup)).not.toBe(key);
  });
});

/**
 * Covers #539: the live log list is virtualized with the CDK fixed-size
 * viewport so the rendered DOM is bounded by the viewport height rather than
 * the 2000-record cap. These tests assert the virtual-scroll wiring and a
 * bounded rendered range without relying on positional selectors.
 */
describe('LogsPageComponent virtual scroll rendering (#539)', () => {
  let fixture: ComponentFixture<LogsPageComponent>;
  let component: LogsPageComponent;
  let logs$: Subject<LogRecord>;

  function makeRecord(i: number): LogRecord {
    return {
      time: new Date(1_700_000_000_000 + i * 1000),
      level: LogLevel.INFO,
      loggerName: `logger-${i}`,
      message: `message ${i}`,
      exceptionTraceback: null,
    };
  }

  beforeEach(() => {
    vi.useFakeTimers();
    logs$ = new Subject<LogRecord>();
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$, fetchHistory: vi.fn().mockReturnValue(of([])) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges(); // renders the viewport into the DOM
    // Bound the viewport height so the fixed-size scroll strategy renders only a
    // window of rows, not the full buffer.
    const host = fixture.nativeElement as HTMLElement;
    const viewportEl = host.querySelector('cdk-virtual-scroll-viewport') as HTMLElement | null;
    if (viewportEl) viewportEl.style.height = '200px';
    component.viewport?.checkViewportSize();
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders the live list inside a cdk-virtual-scroll-viewport with cdkVirtualFor', () => {
    const host = fixture.nativeElement as HTMLElement;
    const viewport = host.querySelector('cdk-virtual-scroll-viewport');
    expect(viewport).toBeTruthy();
    // The viewport reports its bound data length once records are present.
    logs$.next(makeRecord(0));
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);
    fixture.detectChanges();
    expect(component.viewport?.getDataLength()).toBe(component.records.length);
  });

  it('renders far fewer DOM rows than the buffered record count (bounded by viewport)', () => {
    // Fill well past what a 200px / 22px-row viewport can show.
    for (let i = 0; i < 500; i++) {
      logs$.next(makeRecord(i));
    }
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);
    fixture.detectChanges();
    component.viewport?.checkViewportSize();
    fixture.detectChanges();

    expect(component.records.length).toBe(500);
    const renderedRows = (fixture.nativeElement as HTMLElement).querySelectorAll('p.record');
    // DOM is bounded by the viewport (a small window + CDK buffer), not the cap.
    expect(renderedRows.length).toBeLessThan(component.records.length);
    expect(renderedRows.length).toBeLessThan(100);

    // The viewport's rendered range is likewise bounded.
    const range = component.viewport?.getRenderedRange();
    expect(range).toBeTruthy();
    if (range) {
      expect(range.end - range.start).toBeLessThan(component.records.length);
    }
  });
});

/**
 * Covers #539: incoming records auto-scroll the viewport to the bottom IFF the
 * user was already pinned to the bottom; if they have scrolled up, a new batch
 * must NOT yank them back down. The viewport is replaced with a stub so the
 * scroll/measure calls are deterministic in jsdom.
 */
describe('LogsPageComponent auto-scroll-to-bottom (#539)', () => {
  let fixture: ComponentFixture<LogsPageComponent>;
  let component: LogsPageComponent;
  let logs$: Subject<LogRecord>;

  interface ViewportStub {
    scrollToIndex: ReturnType<typeof vi.fn>;
    measureScrollOffset: ReturnType<typeof vi.fn>;
    getDataLength: ReturnType<typeof vi.fn>;
    getRenderedRange: ReturnType<typeof vi.fn>;
  }

  function makeRecord(i: number): LogRecord {
    return {
      time: new Date(1_700_000_000_000 + i * 1000),
      level: LogLevel.DEBUG,
      loggerName: `logger-${i}`,
      message: `message ${i}`,
      exceptionTraceback: null,
    };
  }

  function stubViewport(bottomOffset: number): ViewportStub {
    const stub: ViewportStub = {
      scrollToIndex: vi.fn(),
      measureScrollOffset: vi.fn((from?: string) => (from === 'bottom' ? bottomOffset : 0)),
      getDataLength: vi.fn(() => component.records.length),
      getRenderedRange: vi.fn(() => ({ start: 0, end: 0 })),
    };
    // Pin the stub as the ViewChild. flushPendingRecords() runs detectChanges()
    // before scrolling, which re-runs Angular's @ViewChild query and would
    // overwrite a plain assignment with the real viewport. A getter (with a
    // no-op setter that swallows Angular's write) keeps the stub in place
    // across change detection.
    Object.defineProperty(component, 'viewport', {
      configurable: true,
      get: () => stub as unknown as CdkVirtualScrollViewport,
      set: () => undefined,
    });
    return stub;
  }

  beforeEach(() => {
    vi.useFakeTimers();
    logs$ = new Subject<LogRecord>();
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$, fetchHistory: vi.fn().mockReturnValue(of([])) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('scrolls to the new last index when the viewport was at the bottom', () => {
    const stub = stubViewport(0); // bottomOffset 0 -> at bottom

    logs$.next(makeRecord(0));
    logs$.next(makeRecord(1));
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);

    expect(stub.scrollToIndex).toHaveBeenCalledTimes(1);
    expect(stub.scrollToIndex).toHaveBeenCalledWith(component.records.length - 1);
  });

  it('does NOT scroll when the user has scrolled up', () => {
    const stub = stubViewport(500); // far from the bottom -> user scrolled up

    logs$.next(makeRecord(0));
    logs$.next(makeRecord(1));
    vi.advanceTimersByTime(LogsPageComponent.BATCH_WINDOW_MS);

    expect(stub.scrollToIndex).not.toHaveBeenCalled();
  });

  it('scrollToBottom() jumps to the last record index', () => {
    const stub = stubViewport(500);
    component.records = [makeRecord(0), makeRecord(1), makeRecord(2)];

    component.scrollToBottom();

    expect(stub.scrollToIndex).toHaveBeenCalledWith(2, 'smooth');
  });

  it('scrollToTop() jumps to the first index', () => {
    const stub = stubViewport(500);

    component.scrollToTop();

    expect(stub.scrollToIndex).toHaveBeenCalledWith(0, 'smooth');
  });
});

/**
 * Covers #539: a record's exception traceback opens in a popover toggle so the
 * row stays a fixed height (required by the fixed-size virtual scroll), rather
 * than expanding inline.
 */
describe('LogsPageComponent traceback popover (#539)', () => {
  let component: LogsPageComponent;
  let fixture: ComponentFixture<LogsPageComponent>;

  function makeRecord(tb: string | null): LogRecord {
    return {
      time: new Date(1_700_000_000_000),
      level: LogLevel.ERROR,
      loggerName: 'logger',
      message: 'boom',
      exceptionTraceback: tb,
    };
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$: new Subject(), fetchHistory: vi.fn().mockReturnValue(of([])) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    vi.restoreAllMocks();
  });

  it('toggles the expanded traceback for a record and back off', () => {
    const rec = makeRecord('Traceback (most recent call last): ...');
    expect(component.expandedTraceback).toBeNull();

    component.toggleTraceback(rec);
    expect(component.expandedTraceback).toBe(rec);

    component.toggleTraceback(rec);
    expect(component.expandedTraceback).toBeNull();
  });

  it('switches the expansion to a different record', () => {
    const a = makeRecord('trace a');
    const b = makeRecord('trace b');

    component.toggleTraceback(a);
    expect(component.expandedTraceback).toBe(a);

    component.toggleTraceback(b);
    expect(component.expandedTraceback).toBe(b);
  });
});

/**
 * Exercises the real debounced search pipe so the test fails if catchError stops
 * setting the failure flag (not just the rendered template). Uses fake timers to
 * flush the 300ms debounce deterministically.
 */
describe('LogsPageComponent history fetch failure (real pipe, #516)', () => {
  let fixture: ComponentFixture<LogsPageComponent>;
  let component: LogsPageComponent;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      imports: [LogsPageComponent, ScrollingModule],
      providers: [
        {
          provide: LogService,
          useValue: { logs$: new Subject(), fetchHistory: vi.fn().mockReturnValue(throwError(() => new Error('boom'))) },
        },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
        { provide: LoggerService, useValue: loggerMock() },
      ],
    });
    fixture = TestBed.createComponent(LogsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges(); // ngOnInit -> initial searchChange$.next() schedules the debounce
  });

  afterEach(() => {
    fixture.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('flips into the failure state when fetchHistory errors', () => {
    vi.advanceTimersByTime(300); // flush debounce -> fetchHistory errors -> catchError
    fixture.detectChanges();

    expect(component.historyLoadFailed).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Failed to load log history');
  });
});
