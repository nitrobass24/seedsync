import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { ConnectionTestService, TestResult } from './connection-test.service';

describe('ConnectionTestService', () => {
  let service: ConnectionTestService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        ConnectionTestService,
      ],
    });
    service = TestBed.inject(ConnectionTestService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('testConnection() returns success on HTTP 200', () => {
    let result: TestResult | undefined;
    service.testConnection().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/config/test-connection');
    expect(req.request.method).toBe('POST');
    req.flush({ success: true });

    expect(result!.success).toBe(true);
    expect(result!.message).toBe('Connection successful');
  });

  it('testConnection() surfaces server-provided error message on failure', () => {
    let result: TestResult | undefined;
    service.testConnection().subscribe((r) => (result = r));

    httpMock.expectOne('/server/config/test-connection').flush(
      { error: 'Incorrect password' },
      { status: 502, statusText: 'Bad Gateway' },
    );

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Incorrect password');
  });

  it('testConnection() falls back to generic message when error body is unparsable', () => {
    let result: TestResult | undefined;
    service.testConnection().subscribe((r) => (result = r));

    httpMock.expectOne('/server/config/test-connection').error(new ProgressEvent('error'));

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Connection failed');
  });
});
