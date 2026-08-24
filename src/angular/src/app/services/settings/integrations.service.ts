import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { ArrInstance, ArrInstanceCreate, ArrInstanceUpdate } from '../../models/arr-instance';
import { TestResult, failureFromHttpError } from '../utils/test-result';
import { CollectionService } from './collection.service';

export type TestConnectionResult = TestResult;

const BASE_URL = '/server/integrations';

/**
 * Service for managing *arr (Sonarr/Radarr) instances and testing
 * connectivity to a stored instance.
 */
@Injectable({ providedIn: 'root' })
export class IntegrationsService extends CollectionService<ArrInstance> {
  private readonly httpClient = inject(HttpClient);

  readonly instances$: Observable<ArrInstance[]> = this.items$;

  constructor() {
    super(BASE_URL, 'integration', false);
  }

  create(instance: ArrInstanceCreate): Observable<ArrInstance | null> {
    return this.createItem(instance);
  }

  update(id: string, patch: ArrInstanceUpdate): Observable<ArrInstance | null> {
    return this.updateItem(id, patch);
  }

  remove(id: string): Observable<boolean> {
    return this.removeItem(id);
  }

  test(id: string): Observable<TestConnectionResult> {
    return this.httpClient.post<{ success?: boolean; version?: string; error?: string }>(
      `${BASE_URL}/${id}/test`,
      {},
    ).pipe(
      map((data) => ({
        success: true,
        message: `Connected${data.version ? ` (v${data.version})` : ''}`,
      })),
      catchError((err: HttpErrorResponse) => of(failureFromHttpError(err, 'Connection failed'))),
    );
  }
}
