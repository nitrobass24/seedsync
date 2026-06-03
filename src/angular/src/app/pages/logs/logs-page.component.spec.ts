import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';

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
      imports: [LogsPageComponent],
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
 * Covers #522: the live-log buffer was unbounded and re-rendered the full list
 * per incoming SSE record. The buffer is now capped (ring-buffer front-trim of
 * the oldest) and the lists use a stable, collision-free trackBy. These tests
 * drive the live subscription via a Subject-backed LogService mock.
 */
describe('LogsPageComponent live-log buffer cap (#522)', () => {
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

  beforeEach(() => {
    logs$ = new Subject<LogRecord>();
    TestBed.configureTestingModule({
      imports: [LogsPageComponent],
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
  });

  afterEach(() => {
    fixture.destroy();
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

    expect(component.records.length).toBe(LogsPageComponent.MAX_LIVE_RECORDS);
    // First 50 emitted records were front-trimmed away.
    expect(component.records[0].message).toBe('message 50');
    // Newest record is always retained.
    expect(component.records[component.records.length - 1]).toBe(last);
  });

  it('renders the latest record text after appending', () => {
    logs$.next(makeRecord(0));
    logs$.next(makeRecord(1));
    fixture.detectChanges();

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

  it('renders one row per record even for identical repeated log lines', () => {
    const a = makeRecord(0);
    const b = { ...a }; // identical content, distinct object
    const c = { ...a };
    logs$.next(a);
    logs$.next(b);
    logs$.next(c);
    fixture.detectChanges();

    // No duplicate-key collapse: a <p class="record"> per buffered record.
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('p.record');
    expect(rows.length).toBe(component.records.length);
    expect(component.records.length).toBe(3);
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
      imports: [LogsPageComponent],
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
