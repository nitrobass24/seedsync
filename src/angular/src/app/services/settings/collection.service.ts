import { inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, OperatorFunction, of } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';

/**
 * REST collection kept in a BehaviorSubject: refreshed on (re)connect, cleared
 * on disconnect, and mutated inside the returned pipeline via `tap` (the
 * CLAUDE.md mutating-service contract). Subclasses expose typed wrappers over
 * the protected CRUD helpers.
 */
export abstract class CollectionService<T extends { id: string }> {
  private readonly http = inject(HttpClient);
  private readonly connectedService = inject(ConnectedService);
  private readonly logger = inject(LoggerService);
  private readonly subject = new BehaviorSubject<T[]>([]);

  readonly items$: Observable<T[]> = this.subject.asObservable();

  /**
   * @param baseUrl collection endpoint; items live at `${baseUrl}/${id}`
   * @param label singular noun for log messages
   * @param clearOnRefreshError emit `[]` when a refresh fails (else keep the last good list)
   */
  protected constructor(
    private readonly baseUrl: string,
    private readonly label: string,
    private readonly clearOnRefreshError: boolean,
  ) {
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.refresh();
      } else {
        this.subject.next([]);
      }
    });
  }

  refresh(): void {
    this.http.get<T[]>(this.baseUrl).pipe(
      catchError((err: HttpErrorResponse) => {
        this.logger.warn(`Failed to load ${this.label}s: %O`, err);
        return of(this.clearOnRefreshError ? [] : null);
      }),
    ).subscribe((list) => {
      if (list !== null) {
        this.subject.next(list);
      }
    });
  }

  protected createItem(body: unknown): Observable<T | null> {
    return this.http.post<T>(this.baseUrl, body).pipe(
      tap((created) => this.subject.next([...this.subject.getValue(), created])),
      this.recover('create'),
    );
  }

  protected updateItem(id: string, body: unknown): Observable<T | null> {
    return this.http.put<T>(`${this.baseUrl}/${id}`, body).pipe(
      tap((updated) => {
        this.subject.next(this.subject.getValue().map((i) => i.id === updated.id ? updated : i));
      }),
      this.recover('update'),
    );
  }

  protected removeItem(id: string): Observable<boolean> {
    return this.http.delete(`${this.baseUrl}/${id}`, { responseType: 'text' }).pipe(
      map(() => {
        this.subject.next(this.subject.getValue().filter((i) => i.id !== id));
        return true;
      }),
      catchError((err: HttpErrorResponse) => {
        this.logger.warn(`Failed to delete ${this.label}: %O`, err);
        return of(false);
      }),
    );
  }

  /** Log and map to null, except 409 (conflict) which callers surface to the user. */
  private recover(verb: string): OperatorFunction<T, T | null> {
    return catchError((err: HttpErrorResponse): Observable<T | null> => {
      this.logger.warn(`Failed to ${verb} ${this.label}: %O`, err);
      if (err.status === 409) {
        throw err;
      }
      return of(null);
    });
  }
}
