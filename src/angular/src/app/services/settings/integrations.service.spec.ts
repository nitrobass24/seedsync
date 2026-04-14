import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { IntegrationsService } from './integrations.service';

describe('IntegrationsService', () => {
  let service: IntegrationsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), IntegrationsService],
    });
    service = TestBed.inject(IntegrationsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should return success on Sonarr test', () => {
    let result: any;
    service.testSonarr().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/test/sonarr');
    expect(req.request.method).toBe('GET');
    req.flush({ success: true, version: '4.0.0.1' });

    expect(result.success).toBe(true);
    expect(result.message).toContain('4.0.0.1');
  });

  it('should return failure on Sonarr error', () => {
    let result: any;
    service.testSonarr().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/test/sonarr');
    req.flush({ error: 'Connection failed: refused' }, { status: 502, statusText: 'Bad Gateway' });

    expect(result.success).toBe(false);
    expect(result.message).toContain('Connection failed');
  });

  it('should return success on Radarr test', () => {
    let result: any;
    service.testRadarr().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/test/radarr');
    req.flush({ success: true, version: '5.2.0.1' });

    expect(result.success).toBe(true);
    expect(result.message).toContain('5.2.0.1');
  });

  it('should return failure on Radarr error', () => {
    let result: any;
    service.testRadarr().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/test/radarr');
    req.flush({ error: 'API key is not configured' }, { status: 400, statusText: 'Bad Request' });

    expect(result.success).toBe(false);
    expect(result.message).toContain('API key is not configured');
  });

  it('should handle non-JSON error gracefully', () => {
    let result: any;
    service.testSonarr().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/integrations/test/sonarr');
    req.error(new ProgressEvent('error'));

    expect(result.success).toBe(false);
    expect(result.message).toContain('Sonarr connection failed');
  });
});
