import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { StatsSummary, TransferRecord, SpeedSample, EMPTY_SUMMARY } from '../../models/stats';

@Injectable({ providedIn: 'root' })
export class StatsService {
  private readonly http = inject(HttpClient);

  getSummary(days: number = 7): Observable<StatsSummary> {
    const params = new HttpParams().set('days', days);
    return this.http.get<StatsSummary>('/server/stats/summary', { params }).pipe(
      catchError(() => of(EMPTY_SUMMARY)),
    );
  }

  getTransfers(limit: number = 50): Observable<TransferRecord[]> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<TransferRecord[]>('/server/stats/transfers', { params }).pipe(
      catchError(() => of([])),
    );
  }

  getSpeedHistory(hours: number = 24): Observable<SpeedSample[]> {
    const params = new HttpParams().set('hours', hours);
    return this.http.get<SpeedSample[]>('/server/stats/speed-history', { params }).pipe(
      catchError(() => of([])),
    );
  }
}
