import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject, of } from 'rxjs';

import { AutoQueueService } from './autoqueue.service';
import { ConnectedService } from '../utils/connected.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { LoggerService } from '../utils/logger.service';
import { AutoQueuePattern } from '../../models/autoqueue-pattern';
import { Localization } from '../../models/localization';

function makeReaction(overrides: Partial<WebReaction> = {}): WebReaction {
  return { success: true, data: null, errorMessage: null, ...overrides };
}

describe('AutoQueueService', () => {
  let service: AutoQueueService;
  let connectedSubject: BehaviorSubject<boolean>;
  let mockRestService: { sendRequest: ReturnType<typeof vi.fn> };

  function snapshot(): AutoQueuePattern[] {
    let result: AutoQueuePattern[] = [];
    service.patterns$.subscribe(p => result = p);
    return result;
  }

  beforeEach(() => {
    connectedSubject = new BehaviorSubject<boolean>(false);
    mockRestService = { sendRequest: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        AutoQueueService,
        { provide: ConnectedService, useValue: { connected$: connectedSubject.asObservable() } },
        { provide: RestService, useValue: mockRestService },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });
    service = TestBed.inject(AutoQueueService);
  });

  // --- Connect / disconnect ---

  it('should fetch patterns when connected', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: JSON.stringify([{ pattern: '*.mkv' }]) })),
    );

    connectedSubject.next(true);

    expect(mockRestService.sendRequest).toHaveBeenCalledWith('/server/autoqueue/get');
    expect(snapshot()).toEqual([{ pattern: '*.mkv' }]);
  });

  it('should clear patterns when disconnected', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: JSON.stringify([{ pattern: '*.mkv' }]) })),
    );
    connectedSubject.next(true);
    expect(snapshot().length).toBe(1);

    connectedSubject.next(false);
    expect(snapshot()).toEqual([]);
  });

  // --- add() ---

  it('should reject empty pattern with error message', () => {
    let result: WebReaction | undefined;
    service.add('').subscribe(r => result = r);

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe(Localization.Notification.AUTOQUEUE_PATTERN_EMPTY);
  });

  it('should reject whitespace-only pattern', () => {
    let result: WebReaction | undefined;
    service.add('   ').subscribe(r => result = r);

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe(Localization.Notification.AUTOQUEUE_PATTERN_EMPTY);
  });

  it('should reject duplicate pattern locally', () => {
    // Pre-load a pattern
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: JSON.stringify([{ pattern: '*.mkv' }]) })),
    );
    connectedSubject.next(true);

    let result: WebReaction | undefined;
    service.add('*.mkv').subscribe(r => result = r);

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toContain('already exists');
  });

  it('should append pattern to local list on successful add', () => {
    // Start with empty connected state
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([]) })),
    );
    connectedSubject.next(true);
    expect(snapshot()).toEqual([]);

    // Add returns success
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true })),
    );

    service.add('*.mkv');
    expect(snapshot()).toEqual([{ pattern: '*.mkv' }]);
  });

  it('should send double-encoded URL for add', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([]) })),
    );
    connectedSubject.next(true);

    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true })),
    );

    service.add('my pattern');

    const encoded = encodeURIComponent(encodeURIComponent('my pattern'));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(`/server/autoqueue/add/${encoded}`);
  });

  it('should not update local state when server rejects add', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([]) })),
    );
    connectedSubject.next(true);

    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: false, errorMessage: 'Server error' })),
    );

    service.add('*.mkv');
    expect(snapshot()).toEqual([]);
  });

  it('should double-encode special characters in pattern', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([]) })),
    );
    connectedSubject.next(true);

    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true })),
    );

    service.add('test/path&name');

    const encoded = encodeURIComponent(encodeURIComponent('test/path&name'));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(`/server/autoqueue/add/${encoded}`);
  });

  // --- remove() ---

  it('should filter pattern from local list on successful remove', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([{ pattern: '*.mkv' }, { pattern: '*.avi' }]) })),
    );
    connectedSubject.next(true);
    expect(snapshot().length).toBe(2);

    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true })),
    );

    service.remove('*.mkv');
    expect(snapshot()).toEqual([{ pattern: '*.avi' }]);
  });

  it('should not update local state when server rejects remove', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([{ pattern: '*.mkv' }]) })),
    );
    connectedSubject.next(true);

    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: false, errorMessage: 'Server error' })),
    );

    service.remove('*.mkv');
    expect(snapshot()).toEqual([{ pattern: '*.mkv' }]);
  });

  it('should return error when removing a pattern that does not exist', () => {
    mockRestService.sendRequest.mockReturnValueOnce(
      of(makeReaction({ success: true, data: JSON.stringify([]) })),
    );
    connectedSubject.next(true);

    let result: WebReaction | undefined;
    service.remove('nonexistent').subscribe(r => result = r);

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toContain('not found');
  });

  // --- GET failure ---

  it('should set empty array when GET fails (graceful degradation)', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: false, errorMessage: 'Network error' })),
    );

    connectedSubject.next(true);
    expect(snapshot()).toEqual([]);
  });
});
