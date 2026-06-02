import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { ConfigService } from '../settings/config.service';
import { StorageKeys } from '../../common/storage-keys';
import { REDACTED_SENTINEL } from '../../models/config';

// REDACTED_SENTINEL is the value the backend substitutes for web.api_key in the
// auth-exempt /server/config/get response, so the config snapshot can hold it
// before the real key is known — it must never be sent as a credential.

function readPersistedApiKey(): string | null {
  try {
    return sessionStorage.getItem(StorageKeys.API_KEY);
  } catch {
    // sessionStorage may be unavailable (private browsing, test environments)
    return null;
  }
}

export const apiKeyInterceptor: HttpInterceptorFn = (req, next) => {
  // Only attach the API key to internal backend /server/* requests
  const url = req.url;
  if (url !== '/server' && !url.startsWith('/server/')) {
    return next(req);
  }

  // Prefer the persisted real key: /server/config/get redacts web.api_key to
  // '********', so on an auth-enabled instance the config snapshot cannot
  // supply a usable credential after a reload. The persisted key (written by
  // ConfigService when the user saves it) is the only client-side source of
  // the real key, so REST requests can re-authenticate after a reload.
  const persistedKey = readPersistedApiKey();
  const configService = inject(ConfigService);
  const snapshotKey = configService.configSnapshot?.web?.api_key;

  // Never send the redacted sentinel as a credential.
  const apiKey = persistedKey || (snapshotKey === REDACTED_SENTINEL ? null : snapshotKey);

  if (apiKey) {
    const authReq = req.clone({
      setHeaders: { 'X-Api-Key': apiKey },
    });
    return next(authReq);
  }

  return next(req);
};
