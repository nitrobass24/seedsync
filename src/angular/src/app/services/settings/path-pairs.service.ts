import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { map, catchError, tap } from 'rxjs/operators';

import { PathPair } from '../../models/path-pair';
import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';

@Injectable({ providedIn: 'root' })
export class PathPairsService {
  private static readonly BASE_URL = '/server/pathpairs';

  private readonly http = inject(HttpClient);
  private readonly connectedService = inject(ConnectedService);
  private readonly logger = inject(LoggerService);

  private readonly pairsSubject = new BehaviorSubject<PathPair[]>([]);
  readonly pairs$: Observable<PathPair[]> = this.pairsSubject.asObservable();

  constructor() {
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.refresh();
      } else {
        this.pairsSubject.next([]);
      }
    });
  }

  refresh(): void {
    this.http.get<PathPair[]>(PathPairsService.BASE_URL).pipe(
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to load path pairs: %O', err);
        return of([]);
      }),
    ).subscribe((pairs) => this.pairsSubject.next(pairs));
  }

  create(pair: Omit<PathPair, 'id'>): Observable<PathPair | null> {
    return this.http.post<PathPair>(PathPairsService.BASE_URL, pair).pipe(
      tap((created) => {
        this.pairsSubject.next([...this.pairsSubject.getValue(), created]);
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to create path pair: %O', err);
        return of(null);
      }),
    );
  }

  update(pair: PathPair): Observable<PathPair | null> {
    return this.http.put<PathPair>(`${PathPairsService.BASE_URL}/${pair.id}`, pair).pipe(
      tap((updated) => {
        const pairs = this.pairsSubject.getValue().map(
          (p) => p.id === updated.id ? updated : p,
        );
        this.pairsSubject.next(pairs);
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to update path pair: %O', err);
        return of(null);
      }),
    );
  }

  remove(pairId: string): Observable<boolean> {
    return this.http.delete(`${PathPairsService.BASE_URL}/${pairId}`, { responseType: 'text' }).pipe(
      map(() => {
        const pairs = this.pairsSubject.getValue().filter((p) => p.id !== pairId);
        this.pairsSubject.next(pairs);
        return true;
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to delete path pair: %O', err);
        return of(false);
      }),
    );
  }
}
