import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe, DecimalPipe } from '@angular/common';

import { StatsService } from '../../services/stats/stats.service';
import { ConfigService } from '../../services/settings/config.service';
import { StatsSummary, TransferRecord, SpeedSample, EMPTY_SUMMARY } from '../../models/stats';

type SortColumn = 'filename' | 'size_bytes' | 'duration_seconds' | 'completed_at' | 'status';
type SortDirection = 'asc' | 'desc';
import { FileSizePipe } from '../../common/file-size.pipe';

@Component({
  selector: 'app-stats-page',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FileSizePipe],
  templateUrl: './stats-page.component.html',
  styleUrls: ['./stats-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatsPageComponent implements OnInit, AfterViewInit {
  private readonly statsService = inject(StatsService);
  private readonly configService = inject(ConfigService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  statsEnabled = true;
  summary: StatsSummary = EMPTY_SUMMARY;
  transfers: TransferRecord[] = [];
  speedHistory: SpeedSample[] = [];
  selectedDays = 7;
  sortColumn: SortColumn = 'completed_at';
  sortDirection: SortDirection = 'desc';
  private chartReady = false;
  private dataLoaded = false;

  @ViewChild('speedCanvas') canvasRef!: ElementRef<HTMLCanvasElement>;

  ngOnInit(): void {
    this.configService.config$.pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((config) => {
      if (!config) return;
      this.statsEnabled = config.general.stats_enabled !== false;
      if (this.statsEnabled && !this.dataLoaded) {
        this.dataLoaded = true;
        this.loadData();
      }
      this.cdr.markForCheck();
    });
  }

  ngAfterViewInit(): void {
    this.chartReady = true;
    if (this.speedHistory.length > 0) {
      this.drawSpeedChart();
    }
  }

  onDaysChange(days: number): void {
    this.selectedDays = days;
    this.loadData();
  }

  onSort(column: SortColumn): void {
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column;
      this.sortDirection = 'asc';
    }
    this.sortTransfers();
  }

  sortAriaFor(column: SortColumn): 'ascending' | 'descending' | 'none' {
    if (this.sortColumn !== column) return 'none';
    return this.sortDirection === 'asc' ? 'ascending' : 'descending';
  }

  get successRate(): number {
    if (this.summary.total_count === 0) return 0;
    return Math.round((this.summary.success_count / this.summary.total_count) * 100);
  }

  private loadData(): void {
    this.statsService.getSummary(this.selectedDays).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((summary) => {
      this.summary = summary;
      this.cdr.markForCheck();
    });

    this.statsService.getTransfers().pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((transfers) => {
      this.transfers = transfers;
      this.sortTransfers();
      this.cdr.markForCheck();
    });

    this.statsService.getSpeedHistory().pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((history) => {
      this.speedHistory = history;
      this.cdr.markForCheck();
      if (this.chartReady) {
        this.drawSpeedChart();
      }
    });
  }

  private sortTransfers(): void {
    const dir = this.sortDirection === 'asc' ? 1 : -1;
    const col = this.sortColumn;
    this.transfers.sort((a, b) => {
      const av = a[col];
      const bv = b[col];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }

  private drawSpeedChart(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    if (this.speedHistory.length === 0) {
      ctx.fillStyle = 'var(--ss-text-muted, #6c757d)';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No speed data available', width / 2, height / 2);
      return;
    }

    const samples = this.speedHistory;
    const maxSpeed = Math.max(...samples.map((s) => s.bytes_per_sec), 1);

    const padding = { top: 20, right: 10, bottom: 30, left: 60 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Draw axes
    ctx.strokeStyle = 'var(--ss-border, #dee2e6)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    // Y-axis labels
    ctx.fillStyle = 'var(--ss-text-muted, #6c757d)';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const val = (maxSpeed / 4) * i;
      const y = padding.top + chartHeight - (i / 4) * chartHeight;
      ctx.fillText(this.formatSpeed(val), padding.left - 5, y + 4);
    }

    // Draw area chart
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight);
    gradient.addColorStop(0, 'rgba(13, 110, 253, 0.3)');
    gradient.addColorStop(1, 'rgba(13, 110, 253, 0.02)');

    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartHeight);

    for (let i = 0; i < samples.length; i++) {
      const x = padding.left + (i / Math.max(samples.length - 1, 1)) * chartWidth;
      const y = padding.top + chartHeight - (samples[i].bytes_per_sec / maxSpeed) * chartHeight;
      ctx.lineTo(x, y);
    }

    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    for (let i = 0; i < samples.length; i++) {
      const x = padding.left + (i / Math.max(samples.length - 1, 1)) * chartWidth;
      const y = padding.top + chartHeight - (samples[i].bytes_per_sec / maxSpeed) * chartHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = 'rgba(13, 110, 253, 0.8)';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  private formatSpeed(bytesPerSec: number): string {
    if (bytesPerSec >= 1073741824) return (bytesPerSec / 1073741824).toFixed(1) + ' GB/s';
    if (bytesPerSec >= 1048576) return (bytesPerSec / 1048576).toFixed(1) + ' MB/s';
    if (bytesPerSec >= 1024) return (bytesPerSec / 1024).toFixed(0) + ' KB/s';
    return bytesPerSec.toFixed(0) + ' B/s';
  }
}
