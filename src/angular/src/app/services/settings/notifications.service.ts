import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { TestResult, failureFromHttpError } from '../utils/test-result';

export type { TestResult };

export const NOTIFICATION_CHANNELS = ['discord', 'telegram'] as const;
export type NotificationChannel = (typeof NOTIFICATION_CHANNELS)[number];

const BASE_URL = '/server/notifications/test';

@Injectable({ providedIn: 'root' })
export class NotificationsService {
  private readonly http = inject(HttpClient);

  test(channel: NotificationChannel): Observable<TestResult> {
    return this.http.post(`${BASE_URL}/${channel}`, {}).pipe(
      map(() => ({ success: true, message: 'Notification sent successfully' })),
      catchError((err: HttpErrorResponse) => of(failureFromHttpError(err, 'Notification failed'))),
    );
  }
}
