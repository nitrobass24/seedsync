import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { of, BehaviorSubject } from 'rxjs';

import { StatsPageComponent } from './stats-page.component';
import { StatsService } from '../../services/stats/stats.service';
import { ConfigService } from '../../services/settings/config.service';
import { Config, DEFAULT_CONFIG } from '../../models/config';
import { EMPTY_SUMMARY } from '../../models/stats';

const mockSummary = {
  total_count: 10,
  success_count: 8,
  failed_count: 2,
  total_bytes: 1073741824,
  avg_speed_bps: 5242880,
};

const mockTransfers = [
  { id: 1, filename: 'movie.mkv', pair_id: null, size_bytes: 1024000, duration_seconds: 10.5, completed_at: 1700000000, status: 'success' as const },
  { id: 2, filename: 'show.mkv', pair_id: 'pair-1', size_bytes: null, duration_seconds: null, completed_at: 1700001000, status: 'failed' as const },
];

const mockSpeedHistory = [
  { bucket_epoch: 1700000000, bytes_per_sec: 5000000 },
  { bucket_epoch: 1700000060, bytes_per_sec: 3000000 },
];

function makeEnabledConfig(): Config {
  return { ...DEFAULT_CONFIG, general: { ...DEFAULT_CONFIG.general, stats_enabled: true } };
}

function makeDisabledConfig(): Config {
  return { ...DEFAULT_CONFIG, general: { ...DEFAULT_CONFIG.general, stats_enabled: false } };
}

describe('StatsPageComponent', () => {
  let mockStatsService: {
    getSummary: ReturnType<typeof vi.fn>;
    getTransfers: ReturnType<typeof vi.fn>;
    getSpeedHistory: ReturnType<typeof vi.fn>;
  };
  let configSubject: BehaviorSubject<Config | null>;

  beforeEach(() => {
    mockStatsService = {
      getSummary: vi.fn().mockReturnValue(of(mockSummary)),
      getTransfers: vi.fn().mockReturnValue(of(mockTransfers)),
      getSpeedHistory: vi.fn().mockReturnValue(of(mockSpeedHistory)),
    };

    configSubject = new BehaviorSubject<Config | null>(makeEnabledConfig());

    TestBed.configureTestingModule({
      imports: [StatsPageComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: StatsService, useValue: mockStatsService },
        { provide: ConfigService, useValue: { config$: configSubject.asObservable() } },
      ],
    });
  });

  it('should create the component', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should load data on init when enabled', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    expect(mockStatsService.getSummary).toHaveBeenCalledWith(7);
    expect(mockStatsService.getTransfers).toHaveBeenCalled();
    expect(mockStatsService.getSpeedHistory).toHaveBeenCalled();
  });

  it('should render summary cards with correct values', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    const cardValues = el.querySelectorAll('.card-value');
    expect(cardValues.length).toBe(6);
    expect(cardValues[0].textContent?.trim()).toBe('10');
    expect(cardValues[1].textContent?.trim()).toBe('8');
    expect(cardValues[2].textContent?.trim()).toBe('2');
  });

  it('should render transfer table rows', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    const rows = el.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);

    const firstRow = rows[0];
    expect(firstRow.querySelector('.filename-cell')?.textContent?.trim()).toBe('movie.mkv');
  });

  it('should show empty message when no transfers', () => {
    mockStatsService.getTransfers.mockReturnValue(of([]));

    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('No transfers recorded yet');
  });

  it('should compute success rate correctly', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.successRate).toBe(80);
  });

  it('should handle zero total count for success rate', () => {
    mockStatsService.getSummary.mockReturnValue(of(EMPTY_SUMMARY));

    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.successRate).toBe(0);
  });

  it('should reload data when days filter changes', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    fixture.componentInstance.onDaysChange(30);

    expect(mockStatsService.getSummary).toHaveBeenCalledWith(30);
  });

  it('should render status badges with correct classes', () => {
    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    const badges = el.querySelectorAll('.badge');
    expect(badges[0].classList.contains('bg-success')).toBe(true);
    expect(badges[1].classList.contains('bg-danger')).toBe(true);
  });

  it('should show disabled message when stats_enabled is false', () => {
    configSubject.next(makeDisabledConfig());

    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('.stats-disabled')).toBeTruthy();
    expect(el.textContent).toContain('disabled');
    expect(el.querySelectorAll('.card-value').length).toBe(0);
  });

  it('should not load data when disabled', () => {
    configSubject.next(makeDisabledConfig());

    const fixture = TestBed.createComponent(StatsPageComponent);
    fixture.detectChanges();

    expect(mockStatsService.getSummary).not.toHaveBeenCalled();
  });
});
