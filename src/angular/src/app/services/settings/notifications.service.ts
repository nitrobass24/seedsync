import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

const BASE_URL = '/server/notifications/test';

@Injectable({ providedIn: 'root' })
export class NotificationsService {
  private readonly http = inject(HttpClient);

  testDiscord(): Observable<TestResult> {
    return this.http.post(`${BASE_URL}/discord`, {}).pipe(
      map(() => ({ success: true, message: 'Notification sent successfully' })),
      catchError((err: HttpErrorResponse) => {
        let message: string;
        try {
          const body = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
          message = body?.error || 'Notification failed';
        } catch {
          message = 'Notification failed';
        }
        return of({ success: false, message });
      }),
    );
  }

  testTelegram(): Observable<TestResult> {
    return this.http.post(`${BASE_URL}/telegram`, {}).pipe(
      map(() => ({ success: true, message: 'Notification sent successfully' })),
      catchError((err: HttpErrorResponse) => {
        let message: string;
        try {
          const body = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
          message = body?.error || 'Notification failed';
        } catch {
          message = 'Notification failed';
        }
        return of({ success: false, message });
      }),
    );
  }
}
