import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';

export interface TestConnectionResult {
  readonly success: boolean;
  readonly message: string;
}

@Injectable({ providedIn: 'root' })
export class IntegrationsService {
  private readonly http = inject(HttpClient);

  testSonarr(): Observable<TestConnectionResult> {
    return this._testConnection('/server/integrations/test/sonarr', 'Sonarr');
  }

  testRadarr(): Observable<TestConnectionResult> {
    return this._testConnection('/server/integrations/test/radarr', 'Radarr');
  }

  private _testConnection(url: string, service: string): Observable<TestConnectionResult> {
    return this.http.get<{ success?: boolean; version?: string; error?: string }>(url).pipe(
      map((data) => ({
        success: true,
        message: `${service} connected (v${data.version ?? 'unknown'})`,
      })),
      catchError((err: HttpErrorResponse) => {
        let message: string;
        try {
          const body = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
          message = body?.error || `${service} connection failed`;
        } catch {
          message = `${service} connection failed`;
        }
        return of({ success: false, message });
      }),
    );
  }
}
