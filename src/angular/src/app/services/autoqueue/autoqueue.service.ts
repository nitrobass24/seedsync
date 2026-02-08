import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { AutoQueuePattern, AutoQueuePatternJson } from '../../models/autoqueue-pattern';
import { Localization } from '../../models/localization';

@Injectable({ providedIn: 'root' })
export class AutoQueueService {
  private readonly AUTOQUEUE_GET_URL = '/server/autoqueue/get';
  private readonly AUTOQUEUE_ADD_URL = (pattern: string) => `/server/autoqueue/add/${pattern}`;
  private readonly AUTOQUEUE_REMOVE_URL = (pattern: string) => `/server/autoqueue/remove/${pattern}`;

  private readonly connectedService = inject(ConnectedService);
  private readonly restService = inject(RestService);
  private readonly logger = inject(LoggerService);

  private readonly patternsSubject = new BehaviorSubject<AutoQueuePattern[]>([]);

  readonly patterns$: Observable<AutoQueuePattern[]> = this.patternsSubject.asObservable();

  constructor() {
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.getPatterns();
      } else {
        this.patternsSubject.next([]);
      }
    });
  }

  add(pattern: string): Observable<WebReaction> {
    this.logger.debug('add pattern %O', pattern);

    if (pattern == null || pattern.trim().length === 0) {
      return of({
        success: false,
        data: null,
        errorMessage: Localization.Notification.AUTOQUEUE_PATTERN_EMPTY,
      });
    }

    const currentPatterns = this.patternsSubject.getValue();
    const index = currentPatterns.findIndex((pat) => pat.pattern === pattern);
    if (index >= 0) {
      return of({
        success: false,
        data: null,
        errorMessage: `Pattern '${pattern}' already exists.`,
      });
    }

    // Double-encode the value
    const patternEncoded = encodeURIComponent(encodeURIComponent(pattern));
    const url = this.AUTOQUEUE_ADD_URL(patternEncoded);
    const obs = this.restService.sendRequest(url);
    obs.subscribe({
      next: (reaction) => {
        if (reaction.success) {
          const patterns = this.patternsSubject.getValue();
          this.patternsSubject.next([...patterns, { pattern }]);
        }
      },
    });
    return obs;
  }

  remove(pattern: string): Observable<WebReaction> {
    this.logger.debug('remove pattern %O', pattern);

    const currentPatterns = this.patternsSubject.getValue();
    const index = currentPatterns.findIndex((pat) => pat.pattern === pattern);
    if (index < 0) {
      return of({
        success: false,
        data: null,
        errorMessage: `Pattern '${pattern}' not found.`,
      });
    }

    // Double-encode the value
    const patternEncoded = encodeURIComponent(encodeURIComponent(pattern));
    const url = this.AUTOQUEUE_REMOVE_URL(patternEncoded);
    const obs = this.restService.sendRequest(url);
    obs.subscribe({
      next: (reaction) => {
        if (reaction.success) {
          const patterns = this.patternsSubject.getValue();
          const finalIndex = patterns.findIndex((pat) => pat.pattern === pattern);
          if (finalIndex >= 0) {
            this.patternsSubject.next([
              ...patterns.slice(0, finalIndex),
              ...patterns.slice(finalIndex + 1),
            ]);
          }
        }
      },
    });
    return obs;
  }

  private getPatterns(): void {
    this.logger.debug('Getting autoqueue patterns...');
    this.restService.sendRequest(this.AUTOQUEUE_GET_URL).subscribe({
      next: (reaction) => {
        if (reaction.success) {
          const parsed: AutoQueuePatternJson[] = JSON.parse(reaction.data!);
          const newPatterns: AutoQueuePattern[] = parsed.map((p) => ({ pattern: p.pattern }));
          this.patternsSubject.next(newPatterns);
        } else {
          this.patternsSubject.next([]);
        }
      },
    });
  }
}
