import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { StatsService } from './stats.service';
import { EMPTY_SUMMARY } from '../../models/stats';

describe('StatsService', () => {
  let service: StatsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), StatsService],
    });
    service = TestBed.inject(StatsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch summary with default days', () => {
    let result: any;
    service.getSummary().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/summary?days=7');
    expect(req.request.method).toBe('GET');
    req.flush({ total_count: 5, success_count: 4, failed_count: 1, total_bytes: 1024, avg_speed_bps: 500 });

    expect(result.total_count).toBe(5);
    expect(result.success_count).toBe(4);
  });

  it('should fetch summary with custom days', () => {
    let result: any;
    service.getSummary(30).subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/summary?days=30');
    req.flush({ total_count: 10, success_count: 9, failed_count: 1, total_bytes: 2048, avg_speed_bps: 600 });

    expect(result.total_count).toBe(10);
  });

  it('should return empty summary on error', () => {
    let result: any;
    service.getSummary().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/summary?days=7');
    req.error(new ProgressEvent('error'));

    expect(result).toEqual(EMPTY_SUMMARY);
  });

  it('should fetch transfers with default limit', () => {
    let result: any;
    service.getTransfers().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/transfers?limit=50');
    expect(req.request.method).toBe('GET');
    req.flush([{ id: 1, filename: 'test.mkv', status: 'success' }]);

    expect(result.length).toBe(1);
    expect(result[0].filename).toBe('test.mkv');
  });

  it('should return empty array on transfers error', () => {
    let result: any;
    service.getTransfers().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/transfers?limit=50');
    req.error(new ProgressEvent('error'));

    expect(result).toEqual([]);
  });

  it('should fetch speed history with default hours', () => {
    let result: any;
    service.getSpeedHistory().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/speed-history?hours=24');
    expect(req.request.method).toBe('GET');
    req.flush([{ bucket_epoch: 1700000000, bytes_per_sec: 5000 }]);

    expect(result.length).toBe(1);
    expect(result[0].bytes_per_sec).toBe(5000);
  });

  it('should return empty array on speed history error', () => {
    let result: any;
    service.getSpeedHistory().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/stats/speed-history?hours=24');
    req.error(new ProgressEvent('error'));

    expect(result).toEqual([]);
  });
});
