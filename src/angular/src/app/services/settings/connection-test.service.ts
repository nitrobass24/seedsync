import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

const TEST_CONNECTION_URL = '/server/config/test-connection';

@Injectable({ providedIn: 'root' })
export class ConnectionTestService {
  private readonly http = inject(HttpClient);

  testConnection(): Observable<TestResult> {
    return this.http.post(TEST_CONNECTION_URL, {}).pipe(
      map(() => ({ success: true, message: 'Connection successful' })),
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
