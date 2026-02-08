import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError, shareReplay } from 'rxjs/operators';

import { LoggerService } from './logger.service';

export interface WebReaction {
  readonly success: boolean;
  readonly data: string | null;
  readonly errorMessage: string | null;
}

@Injectable({ providedIn: 'root' })
export class RestService {
  private readonly logger = inject(LoggerService);
  private readonly http = inject(HttpClient);

  sendRequest(url: string): Observable<WebReaction> {
    return this.http.get(url, { responseType: 'text' }).pipe(
      map((data) => {
        this.logger.debug('%s http response: %s', url, data);
        return { success: true, data, errorMessage: null } as WebReaction;
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.debug('%s error: %O', url, err);
        const errorMessage =
          err.error instanceof Event ? err.error.type : err.error;
        return of({ success: false, data: null, errorMessage } as WebReaction);
      }),
      shareReplay(1),
    );
  }
}
