import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { ConfigService } from '../settings/config.service';

export const apiKeyInterceptor: HttpInterceptorFn = (req, next) => {
  const configService = inject(ConfigService);
  const config = configService.configSnapshot;
  const apiKey = config?.web?.api_key;

  if (apiKey) {
    const authReq = req.clone({
      setHeaders: { 'X-Api-Key': apiKey },
    });
    return next(authReq);
  }

  return next(req);
};
