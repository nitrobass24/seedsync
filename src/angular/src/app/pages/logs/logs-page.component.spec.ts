import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { Subject, of } from 'rxjs';

import { LogsPageComponent } from './logs-page.component';
import { LogService } from '../../services/logs/log.service';
import { DomService } from '../../services/utils/dom.service';
import { LogRecord, LogLevel } from '../../models/log-record';

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
 * the oldest) and the lists use a stable trackBy. These tests drive the live
 * subscription via a Subject-backed LogService mock.
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

  it('trackRecord returns a stable non-index key for the same record', () => {
    const record = makeRecord(7);
    const key = component.trackRecord(0, record);
    // Stable across calls and across positions.
    expect(component.trackRecord(99, record)).toBe(key);
    // Not the index, and derived from record identity.
    expect(key).not.toBe('0');
    expect(key).toContain('logger-7');
    expect(key).toContain('message 7');
    expect(key).toContain(String(record.time.getTime()));
  });

  it('trackHistory returns a stable non-index key for the same entry', () => {
    const entry = {
      timestamp: '2026-06-01 12:00:00',
      level: 'INFO',
      logger: 'hist-logger',
      process: 'p',
      thread: 't',
      message: 'history message',
    };
    const key = component.trackHistory(0, entry);
    expect(component.trackHistory(42, entry)).toBe(key);
    expect(key).not.toBe('0');
    expect(key).toContain('hist-logger');
    expect(key).toContain('history message');
    expect(key).toContain('2026-06-01 12:00:00');
  });
});
