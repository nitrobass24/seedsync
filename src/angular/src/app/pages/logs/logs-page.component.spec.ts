import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { Subject, of } from 'rxjs';

import { LogsPageComponent } from './logs-page.component';
import { LogService } from '../../services/logs/log.service';
import { DomService } from '../../services/utils/dom.service';

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
