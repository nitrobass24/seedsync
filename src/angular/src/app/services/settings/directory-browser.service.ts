import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { failureFromHttpError } from '../utils/test-result';

export interface BrowseResult {
  readonly success: boolean;
  readonly path: string | null;
  readonly parent: string | null;
  readonly directories: string[];
  readonly errorMessage: string | null;
}

interface BrowseResponse {
  path: string;
  parent: string | null;
  directories: string[];
}

const LOCAL_URL = '/server/browse/local';
const REMOTE_URL = '/server/browse/remote';

@Injectable({ providedIn: 'root' })
export class DirectoryBrowserService {
  private readonly http = inject(HttpClient);

  browseLocal(path: string): Observable<BrowseResult> {
    return this.browse(LOCAL_URL, path);
  }

  browseRemote(path: string): Observable<BrowseResult> {
    return this.browse(REMOTE_URL, path);
  }

  private browse(url: string, path: string): Observable<BrowseResult> {
    const params = new HttpParams().set('path', path);
    return this.http.get<BrowseResponse>(url, { params }).pipe(
      map((body) => ({
        success: true,
        path: body.path,
        parent: body.parent,
        directories: body.directories,
        errorMessage: null,
      })),
      catchError((err: HttpErrorResponse) =>
        of({
          success: false,
          path: null,
          parent: null,
          directories: [],
          errorMessage: failureFromHttpError(err, 'Failed to browse directory').message,
        }),
      ),
    );
  }
}
