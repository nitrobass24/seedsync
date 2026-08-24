import { Injectable, Injector, inject } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { StreamDispatchService } from '../base/stream-dispatch.service';
import { Config, ConfigSection, ConfigValue, REDACTED_SENTINEL } from '../../models/config';


/**
 * Config viewed as a record of string-keyed sections, for dynamic
 * section/option access by runtime strings. Config carries a matching index
 * signature, so it is assignable to this with no cast.
 */
type ConfigRecord = Record<string, ConfigSection>;

/** Sentinel value sent to the backend when the user clears a text field. */
export const EMPTY_VALUE_SENTINEL = '__empty__';

// REDACTED_SENTINEL (imported from models/config) is the value the backend
// substitutes for web.api_key in /server/config/get responses. It must never be
// treated as a real key — pushing it to the stream would fail auth and could
// clobber a good persisted key.

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly CONFIG_GET_URL = '/server/config/get';

  private readonly connectedService = inject(ConnectedService);
  private readonly restService = inject(RestService);
  private readonly logger = inject(LoggerService);
  private readonly injector = inject(Injector);

  private readonly configSubject = new BehaviorSubject<Config | null>(null);

  readonly config$: Observable<Config | null> = this.configSubject.asObservable();

  get configSnapshot(): Config | null {
    return this.configSubject.getValue();
  }

  constructor() {
    // Fetch config at init independent of the stream connection.
    // /server/config/get is auth-exempt, so config$ can populate for the UI
    // even before (and without) an authenticated stream connection. This
    // breaks the init-ordering deadlock where the config fetch was gated
    // behind a stream that could never connect without the key. The key itself
    // is NOT persisted client-side; after a reload on an auth-enabled instance
    // the user re-enters it in Settings (which re-pushes it to the stream).
    this.getConfig();

    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.getConfig();
      }
    });
  }

  set(section: string, option: string, value: ConfigValue): Observable<WebReaction> {
    const valueStr = String(value ?? '');
    const currentConfig = this.configSubject.getValue();
    // Dynamic section/option access by runtime string: localize the record cast
    // here (the typed Config keeps its specific keys for static callers).
    const configRecord = currentConfig as unknown as ConfigRecord | null;
    if (!currentConfig || !configRecord || !(section in currentConfig) || !(option in configRecord[section])) {
      return of({
        success: false,
        data: null,
        errorMessage: `Config has no option named ${section}.${option}`,
      });
    }

    // Double-encode the value, use sentinel for empty strings
    const valueEncoded =
      valueStr.length === 0 ? EMPTY_VALUE_SENTINEL : encodeURIComponent(encodeURIComponent(valueStr));
    const url = `/server/config/set/${section}/${option}/${valueEncoded}`;
    // Update the subject inside the returned pipeline (tap) per the mutating-
    // service contract: the store updates exactly when the caller subscribes,
    // with no second internal subscribe. sendRequest already recovers HTTP
    // errors into a failure WebReaction, so no extra catchError is needed.
    return this.restService.sendRequest(url).pipe(
      tap((reaction) => {
        if (reaction.success) {
          const config = this.configSubject.getValue();
          if (config) {
            const updatedRecord = config as unknown as ConfigRecord;
            const newConfig = { ...config, [section]: { ...updatedRecord[section], [option]: value } };
            this.configSubject.next(newConfig);
            // Propagate API key changes to the SSE stream immediately. set() is
            // the only place the real (un-redacted) key is available client-side.
            if (section === 'web' && option === 'api_key') {
              const realKey = String(value ?? '') || null;
              this.setStreamApiKey(realKey);
            }
          }
        }
      }),
    );
  }

  private getConfig(): void {
    this.logger.debug('Getting config...');
    this.restService.sendRequest(this.CONFIG_GET_URL).subscribe({
      next: (reaction) => {
        if (reaction.success) {
          try {
            const configJson: Config = this.preserveRealApiKey(JSON.parse(reaction.data!));
            this.configSubject.next(configJson);
            this.syncStreamApiKey(configJson);
          } catch (e) {
            this.logger.error('Failed to parse config: %O', e);
            this.configSubject.next(null);
          }
        } else {
          this.logger.error('Failed to get config: %s', reaction.errorMessage);
          this.configSubject.next(null);
        }
      },
    });
  }

  /**
   * Push an API key from a fetched config to the stream, guarding against the
   * redacted sentinel. /server/config/get redacts web.api_key to '********',
   * which would fail auth and clobber a good persisted key, so a redacted
   * value is treated as "no change" and never overwrites the stream's key.
   */
  /**
   * /server/config/get redacts web.api_key to the sentinel *unconditionally*
   * (even when the stored value is empty). A refresh must not clobber whatever
   * the user-set snapshot holds — the apiKeyInterceptor reads it for REST auth,
   * so overwriting it with the sentinel would break authenticated REST calls
   * until the next set(). Preserve the existing value (including a cleared empty
   * key, which must not look like a phantom secret) whenever the snapshot's
   * value is not itself the sentinel.
   */
  private preserveRealApiKey(incoming: Config): Config {
    const currentWeb = this.configSubject.getValue()?.web;
    if (
      incoming.web?.api_key === REDACTED_SENTINEL &&
      currentWeb !== undefined &&
      currentWeb.api_key !== REDACTED_SENTINEL
    ) {
      return { ...incoming, web: { ...incoming.web, api_key: currentWeb.api_key } };
    }
    return incoming;
  }

  private syncStreamApiKey(config: Config | null): void {
    const apiKey = config?.web?.api_key || null;
    if (apiKey === REDACTED_SENTINEL) {
      return;
    }
    this.setStreamApiKey(apiKey);
  }

  private setStreamApiKey(apiKey: string | null): void {
    // Use injector.get() to break circular dependency:
    // StreamDispatchService -> ConnectedService -> ConfigService
    const streamDispatch = this.injector.get(StreamDispatchService);
    streamDispatch.setApiKey(apiKey);
  }
}
