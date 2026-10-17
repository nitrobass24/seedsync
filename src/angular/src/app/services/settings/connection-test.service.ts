import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { TestResult, errorBodyFromHttpError, failureFromHttpError } from '../utils/test-result';

export interface ConnectionTestResult extends TestResult {
  /** True when the failure was a bad-credential (wrong password/key) error,
   * as opposed to a network/host-level failure. Callers use this to stop
   * offering retries until the credentials actually change, since repeated
   * failed auth attempts risk tripping a fail2ban-style ban on the remote
   * server. */
  readonly credentialError?: boolean;
}

const TEST_CONNECTION_URL = '/server/config/test-connection';

@Injectable({ providedIn: 'root' })
export class ConnectionTestService {
  private readonly http = inject(HttpClient);

  testConnection(): Observable<ConnectionTestResult> {
    return this.http.post(TEST_CONNECTION_URL, {}).pipe(
      map(() => ({ success: true, message: 'Connection successful' })),
      catchError((err: HttpErrorResponse) =>
        of({
          ...failureFromHttpError(err, 'Connection failed'),
          credentialError: errorBodyFromHttpError(err)?.['credential_error'] === true,
        }),
      ),
    );
  }
}
