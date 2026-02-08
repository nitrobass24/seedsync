import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, RouteReuseStrategy } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';

import { ROUTES } from './routes';
import { CachedReuseStrategy } from './common/cached-reuse-strategy';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(ROUTES),
    provideHttpClient(),
    { provide: RouteReuseStrategy, useClass: CachedReuseStrategy }
  ]
};
