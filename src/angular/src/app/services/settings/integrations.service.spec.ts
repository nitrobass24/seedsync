import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BehaviorSubject } from 'rxjs';

import { IntegrationsService, TestConnectionResult } from './integrations.service';
import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { ArrInstance } from '../../models/arr-instance';

function makeInstance(overrides: Partial<ArrInstance> = {}): ArrInstance {
  return {
    id: 'inst-1',
    name: 'Sonarr — TV',
    kind: 'sonarr',
    url: 'http://s',
    api_key: '********',
    enabled: true,
    ...overrides,
  };
}

describe('IntegrationsService', () => {
  let service: IntegrationsService;
  let httpMock: HttpTestingController;
  let connectedSubject: BehaviorSubject<boolean>;

  beforeEach(() => {
    connectedSubject = new BehaviorSubject<boolean>(false);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        IntegrationsService,
        { provide: ConnectedService, useValue: { connected$: connectedSubject.asObservable() } },
        {
          provide: LoggerService,
          useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
        },
      ],
    });
    service = TestBed.inject(IntegrationsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('starts with empty instances', () => {
    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot).toEqual([]);
  });

  it('refreshes instances on connect', () => {
    connectedSubject.next(true);
    const req = httpMock.expectOne('/server/integrations');
    expect(req.request.method).toBe('GET');
    req.flush([makeInstance()]);

    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot!.length).toBe(1);
    expect(snapshot![0].name).toBe('Sonarr — TV');
  });

  it('clears instances on disconnect', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/integrations').flush([makeInstance()]);
    connectedSubject.next(false);

    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot).toEqual([]);
  });

  it('falls back to empty list on refresh error', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/integrations').error(new ProgressEvent('error'));

    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot).toEqual([]);
  });

  it('appends a new instance on create()', () => {
    const created = makeInstance({ id: 'new', name: 'Sonarr — Anime' });
    let result: ArrInstance | null | undefined;
    service.create({
      name: 'Sonarr — Anime',
      kind: 'sonarr',
      url: 'http://s',
      api_key: 'k',
      enabled: true,
    }).subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations');
    expect(req.request.method).toBe('POST');
    req.flush(created);

    expect(result!.id).toBe('new');
    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot!.map((i) => i.id)).toEqual(['new']);
  });

  it('rethrows 409 from create() so the UI can surface it', () => {
    let result: ArrInstance | null | undefined;
    let errorStatus: number | undefined;
    service.create({
      name: 'dup',
      kind: 'sonarr',
      url: 'http://s',
      api_key: 'k',
      enabled: true,
    }).subscribe({
      next: (r) => (result = r),
      error: (err) => (errorStatus = err.status),
    });

    httpMock.expectOne('/server/integrations').flush('dup', { status: 409, statusText: 'Conflict' });
    expect(result).toBeUndefined();
    expect(errorStatus).toBe(409);
  });

  it('returns null on non-409 create errors and logs them', () => {
    let result: ArrInstance | null | undefined;
    service.create({
      name: 'X',
      kind: 'sonarr',
      url: 'http://s',
      api_key: 'k',
      enabled: true,
    }).subscribe((r) => (result = r));

    httpMock.expectOne('/server/integrations').flush('boom', { status: 500, statusText: 'err' });
    expect(result).toBeNull();
  });

  it('replaces instance on update()', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/integrations').flush([makeInstance()]);
    const updated = makeInstance({ name: 'renamed' });

    let result: ArrInstance | null | undefined;
    service.update('inst-1', { name: 'renamed' }).subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/inst-1');
    expect(req.request.method).toBe('PUT');
    req.flush(updated);

    expect(result!.name).toBe('renamed');
    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot![0].name).toBe('renamed');
  });

  it('removes instance on remove()', () => {
    connectedSubject.next(true);
    httpMock.expectOne('/server/integrations').flush([makeInstance()]);

    let success: boolean | undefined;
    service.remove('inst-1').subscribe((r) => (success = r));
    httpMock.expectOne('/server/integrations/inst-1').flush('', { status: 204, statusText: 'No Content' });

    expect(success).toBe(true);
    let snapshot: ArrInstance[] | undefined;
    service.instances$.subscribe((v) => (snapshot = v));
    expect(snapshot).toEqual([]);
  });

  it('returns false on remove() error', () => {
    let success: boolean | undefined;
    service.remove('inst-1').subscribe((r) => (success = r));
    httpMock.expectOne('/server/integrations/inst-1').flush('boom', { status: 500, statusText: 'err' });
    expect(success).toBe(false);
  });

  it('test() reports success message with version', () => {
    let result: TestConnectionResult | undefined;
    service.test('inst-1').subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/inst-1/test');
    expect(req.request.method).toBe('POST');
    req.flush({ success: true, version: '4.0.0.1' });

    expect(result!.success).toBe(true);
    expect(result!.message).toContain('4.0.0.1');
  });

  it('test() surfaces server-provided error message on failure', () => {
    let result: TestConnectionResult | undefined;
    service.test('inst-1').subscribe((r) => (result = r));

    httpMock.expectOne('/server/integrations/inst-1/test').flush(
      { error: 'Sonarr connection failed. Check server logs for details.' },
      { status: 502, statusText: 'Bad Gateway' },
    );

    expect(result!.success).toBe(false);
    expect(result!.message).toContain('connection failed');
  });

  it('test() falls back to generic message when error body is unparsable', () => {
    let result: TestConnectionResult | undefined;
    service.test('inst-1').subscribe((r) => (result = r));

    httpMock.expectOne('/server/integrations/inst-1/test').error(new ProgressEvent('error'));

    expect(result!.success).toBe(false);
    expect(result!.message).toContain('Connection failed');
  });
});
