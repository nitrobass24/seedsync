import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';

import {
  ArrInstance,
  ArrInstanceCreate,
  ArrInstanceUpdate,
} from '../../models/arr-instance';
import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';

export interface TestConnectionResult {
  readonly success: boolean;
  readonly message: string;
}

const BASE_URL = '/server/integrations';

/**
 * Service for managing *arr (Sonarr/Radarr) instances and testing
 * connectivity to a stored instance.
 */
@Injectable({ providedIn: 'root' })
export class IntegrationsService {
  private readonly http = inject(HttpClient);
  private readonly connectedService = inject(ConnectedService);
  private readonly logger = inject(LoggerService);

  private readonly instancesSubject = new BehaviorSubject<ArrInstance[]>([]);
  readonly instances$: Observable<ArrInstance[]> = this.instancesSubject.asObservable();

  constructor() {
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.refresh();
      } else {
        this.instancesSubject.next([]);
      }
    });
  }

  refresh(): void {
    this.http.get<ArrInstance[]>(BASE_URL).pipe(
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to load integrations: %O', err);
        return of(null);
      }),
    ).subscribe((list) => {
      if (list !== null) {
        this.instancesSubject.next(list);
      }
    });
  }

  create(instance: ArrInstanceCreate): Observable<ArrInstance | null> {
    return this.http.post<ArrInstance>(BASE_URL, instance).pipe(
      tap((created) => {
        this.instancesSubject.next([...this.instancesSubject.getValue(), created]);
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to create integration: %O', err);
        if (err.status === 409) {
          throw err;
        }
        return of(null);
      }),
    );
  }

  update(id: string, patch: ArrInstanceUpdate): Observable<ArrInstance | null> {
    return this.http.put<ArrInstance>(`${BASE_URL}/${id}`, patch).pipe(
      tap((updated) => {
        const list = this.instancesSubject.getValue().map((i) => i.id === updated.id ? updated : i);
        this.instancesSubject.next(list);
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to update integration: %O', err);
        if (err.status === 409) {
          throw err;
        }
        return of(null);
      }),
    );
  }

  remove(id: string): Observable<boolean> {
    return this.http.delete(`${BASE_URL}/${id}`, { responseType: 'text' }).pipe(
      map(() => {
        const list = this.instancesSubject.getValue().filter((i) => i.id !== id);
        this.instancesSubject.next(list);
        return true;
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn('Failed to delete integration: %O', err);
        return of(false);
      }),
    );
  }

  test(id: string): Observable<TestConnectionResult> {
    return this.http.post<{ success?: boolean; version?: string; error?: string }>(
      `${BASE_URL}/${id}/test`,
      {},
    ).pipe(
      map((data) => ({
        success: true,
        message: `Connected${data.version ? ` (v${data.version})` : ''}`,
      })),
      catchError((err: HttpErrorResponse) => {
        let message: string;
        try {
          const body = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
          message = body?.error || 'Connection failed';
        } catch {
          message = 'Connection failed';
        }
        return of({ success: false, message });
      }),
    );
  }
}
