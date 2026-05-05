import '@angular/compiler';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { BehaviorSubject } from 'rxjs';
import { take } from 'rxjs/operators';

import { PathPairsService } from './path-pairs.service';
import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { PathPair } from '../../models/path-pair';

function makePair(overrides: Partial<PathPair> = {}): PathPair {
  return {
    id: 'pair-1',
    name: 'Default',
    remote_path: '/remote',
    local_path: '/local',
    enabled: true,
    auto_queue: false,
    arr_target_ids: [],
    ...overrides,
  };
}

describe('PathPairsService', () => {
  let service: PathPairsService;
  let httpMock: HttpTestingController;
  let connectedSubject: BehaviorSubject<boolean>;

  function snapshot(): PathPair[] {
    // take(1) auto-completes the observable after the first emission, so
    // each snapshot() call doesn't accumulate a lingering subscription
    // on service.pairs$.
    let result: PathPair[] = [];
    service.pairs$.pipe(take(1)).subscribe(p => result = p);
    return result;
  }

  beforeEach(() => {
    connectedSubject = new BehaviorSubject<boolean>(false);

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        PathPairsService,
        { provide: ConnectedService, useValue: { connected$: connectedSubject.asObservable() } },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });

    service = TestBed.inject(PathPairsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  // --- Connect / disconnect ---

  it('should fetch pairs when connected', () => {
    connectedSubject.next(true);
    const req = httpMock.expectOne('/server/pathpairs');
    expect(req.request.method).toBe('GET');
    req.flush([makePair()]);

    expect(snapshot().length).toBe(1);
    expect(snapshot()[0].name).toBe('Default');
  });

  it('should clear pairs when disconnected', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/pathpairs').flush([makePair()]);
    expect(snapshot().length).toBe(1);

    connectedSubject.next(false);
    expect(snapshot()).toEqual([]);
  });

  // --- create() ---

  it('should send POST and append returned pair', () => {
    const created = makePair({ id: 'new-pair', name: 'New' });

    let result: PathPair | null | undefined;
    service.create({
      name: 'New',
      remote_path: '/r',
      local_path: '/l',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    }).subscribe(r => result = r);

    const req = httpMock.expectOne('/server/pathpairs');
    expect(req.request.method).toBe('POST');
    req.flush(created);

    expect(result!.id).toBe('new-pair');
    expect(snapshot().map(p => p.id)).toEqual(['new-pair']);
  });

  it('should rethrow 409 conflict from create()', () => {
    let result: PathPair | null | undefined;
    let errorStatus: number | undefined;
    service.create({
      name: 'dup',
      remote_path: '/r',
      local_path: '/l',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    }).subscribe({
      next: r => result = r,
      error: err => errorStatus = err.status,
    });

    httpMock.expectOne('/server/pathpairs').flush('conflict', { status: 409, statusText: 'Conflict' });
    expect(result).toBeUndefined();
    expect(errorStatus).toBe(409);
  });

  it('should return null on non-409 create errors', () => {
    let result: PathPair | null | undefined;
    service.create({
      name: 'X',
      remote_path: '/r',
      local_path: '/l',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    }).subscribe(r => result = r);

    httpMock.expectOne('/server/pathpairs').flush('error', { status: 500, statusText: 'Error' });
    expect(result).toBeNull();
  });

  // --- update() ---

  it('should send PUT and replace pair in list by ID', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/pathpairs').flush([makePair()]);

    const updated = makePair({ name: 'Renamed' });

    let result: PathPair | null | undefined;
    service.update(updated).subscribe(r => result = r);

    const req = httpMock.expectOne('/server/pathpairs/pair-1');
    expect(req.request.method).toBe('PUT');
    req.flush(updated);

    expect(result!.name).toBe('Renamed');
    expect(snapshot()[0].name).toBe('Renamed');
  });

  it('should rethrow 409 conflict from update()', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/pathpairs').flush([makePair()]);

    let errorStatus: number | undefined;
    service.update(makePair({ name: 'dup' })).subscribe({
      error: err => errorStatus = err.status,
    });

    httpMock.expectOne('/server/pathpairs/pair-1').flush('conflict', { status: 409, statusText: 'Conflict' });
    expect(errorStatus).toBe(409);
  });

  // --- remove() ---

  it('should send DELETE and filter pair out of list', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/pathpairs').flush([makePair()]);
    expect(snapshot().length).toBe(1);

    let success: boolean | undefined;
    service.remove('pair-1').subscribe(r => success = r);

    const req = httpMock.expectOne('/server/pathpairs/pair-1');
    expect(req.request.method).toBe('DELETE');
    req.flush('', { status: 204, statusText: 'No Content' });

    expect(success).toBe(true);
    expect(snapshot()).toEqual([]);
  });

  it('should return false on remove() error', () => {
    let success: boolean | undefined;
    service.remove('pair-1').subscribe(r => success = r);

    httpMock.expectOne('/server/pathpairs/pair-1').flush('error', { status: 500, statusText: 'Error' });
    expect(success).toBe(false);
  });

  // --- Failed refresh ---

  it('should clear pairs when refresh fails (catchError emits empty array)', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/pathpairs').flush([makePair()]);
    expect(snapshot().length).toBe(1);

    // Trigger another refresh that fails. The service's catchError(of([]))
    // turns the error into an empty list, which pairsSubject.next([]) emits
    // to subscribers — the previously cached list is dropped.
    service.refresh();
    httpMock.expectOne('/server/pathpairs').error(new ProgressEvent('error'));

    let result: PathPair[] = [];
    service.pairs$.subscribe(p => result = p);
    expect(result).toEqual([]);
  });
});
