import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { LoggerService } from './logger.service';
import { StorageKeys } from '../../common/storage-keys';

export type Theme = 'light' | 'dark';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly logger = inject(LoggerService);

  private readonly themeSubject: BehaviorSubject<Theme>;

  readonly theme$: Observable<Theme>;

  constructor() {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(StorageKeys.THEME);
    } catch {
      // localStorage may be unavailable (private browsing, test environments)
    }

    let initial: Theme;
    if (stored === 'light' || stored === 'dark') {
      initial = stored;
    } else {
      try {
        initial = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      } catch {
        initial = 'light';
      }
    }

    this.themeSubject = new BehaviorSubject<Theme>(initial);
    this.theme$ = this.themeSubject.asObservable();
    this.applyTheme(initial);
  }

  toggle(): void {
    const next: Theme = this.themeSubject.getValue() === 'dark' ? 'light' : 'dark';
    this.themeSubject.next(next);
    try {
      localStorage.setItem(StorageKeys.THEME, next);
    } catch {
      // localStorage may be unavailable
    }
    this.applyTheme(next);
    this.logger.debug('Theme set to: ' + next);
  }

  private applyTheme(theme: Theme): void {
    document.documentElement.setAttribute('data-bs-theme', theme);
  }
}
