import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { ConfigService } from '../settings/config.service';
import { REDACTED_SENTINEL } from '../../models/config';

export const apiKeyInterceptor: HttpInterceptorFn = (req, next) => {
  // Only attach the API key to internal backend /server/* requests
  const url = req.url;
  if (url !== '/server' && !url.startsWith('/server/')) {
    return next(req);
  }

  const configService = inject(ConfigService);
  const snapshotKey = configService.configSnapshot?.web?.api_key;

  // /server/config/get redacts web.api_key to '********'; never send the
  // redacted sentinel as a credential. The real key is only present in the
  // snapshot during the session in which the user entered it in Settings.
  const apiKey = snapshotKey === REDACTED_SENTINEL ? null : snapshotKey;

  if (apiKey) {
    const authReq = req.clone({
      setHeaders: { 'X-Api-Key': apiKey },
    });
    return next(authReq);
  }

  return next(req);
};
