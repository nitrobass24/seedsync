import { ApplicationConfig, APP_INITIALIZER, inject, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, RouteReuseStrategy } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';

import { ROUTES } from './routes';
import { CachedReuseStrategy } from './common/cached-reuse-strategy';
import { StreamDispatchService } from './services/base/stream-dispatch.service';
import { ConnectedService } from './services/utils/connected.service';
import { ServerStatusService } from './services/server/server-status.service';
import { ModelFileService } from './services/files/model-file.service';
import { LogService } from './services/logs/log.service';

function initializeStreaming(): () => void {
  // Eagerly inject all SSE handler services so they register with StreamDispatchService.
  // Services register in their constructors, so just injecting them is enough.
  inject(ConnectedService);
  inject(ServerStatusService);
  inject(ModelFileService);
  inject(LogService);

  const streamDispatch = inject(StreamDispatchService);
  return () => streamDispatch.start();
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(ROUTES),
    provideHttpClient(),
    { provide: RouteReuseStrategy, useClass: CachedReuseStrategy },
    {
      provide: APP_INITIALIZER,
      useFactory: initializeStreaming,
      multi: true,
    },
  ]
};
