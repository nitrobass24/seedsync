import { Injectable, Injector, inject } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { StreamDispatchService } from '../base/stream-dispatch.service';
import { Config, REDACTED_SENTINEL } from '../../models/config';
import { StorageKeys } from '../../common/storage-keys';

/** Value a config field may take (matches OptionComponent's value shape). */
export type ConfigValue = string | number | boolean | null;

/** Config treated as a string-keyed record for dynamic section/option access. */
type ConfigRecord = Record<string, Record<string, ConfigValue>>;

/** Sentinel value sent to the backend when the user clears a text field. */
export const EMPTY_VALUE_SENTINEL = '__empty__';

// REDACTED_SENTINEL (imported from models/config) is the value the backend
// substitutes for web.api_key in /server/config/get responses. It must never be
// treated as a real key — pushing it to the stream would fail auth and could
// clobber a good persisted key.

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly CONFIG_GET_URL = '/server/config/get';
  private readonly CONFIG_SET_URL = (section: string, option: string, value: string) =>
    `/server/config/set/${section}/${option}/${value}`;

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
    // Rehydrate any persisted API key BEFORE the stream connects, so the
    // first connection on an auth-enabled instance carries the key. This is
    // the only client-side data that can re-authenticate after a reload —
    // /server/config/get redacts web.api_key, so it cannot supply the key.
    const persistedKey = this.readPersistedApiKey();
    if (persistedKey) {
      this.setStreamApiKey(persistedKey);
    }

    // Fetch config at init independent of the stream connection.
    // /server/config/get is auth-exempt, so config$ can populate for the UI
    // even before (and without) an authenticated stream connection. This
    // breaks the init-ordering deadlock where the config fetch was gated
    // behind a stream that could never connect without the key.
    this.getConfig();

    this.connectedService.connected$.subscribe((connected) => {
      // The connected$ subscription now only refreshes config on (re)connect;
      // bootstrap is handled above. On disconnect, leave any persisted key in
      // place so the next connect attempt can still authenticate.
      if (connected) {
        this.getConfig();
      }
    });
  }

  set(section: string, option: string, value: ConfigValue): Observable<WebReaction> {
    const valueStr = String(value ?? '');
    const currentConfig = this.configSubject.getValue();
    const configRecord = currentConfig as unknown as ConfigRecord;
    if (!currentConfig || !(section in currentConfig) || !(option in configRecord[section])) {
      return of({
        success: false,
        data: null,
        errorMessage: `Config has no option named ${section}.${option}`,
      });
    }

    // Double-encode the value, use sentinel for empty strings
    const valueEncoded =
      valueStr.length === 0 ? EMPTY_VALUE_SENTINEL : encodeURIComponent(encodeURIComponent(valueStr));
    const url = this.CONFIG_SET_URL(section, option, valueEncoded);
    const obs = this.restService.sendRequest(url);
    obs.subscribe({
      next: (reaction) => {
        if (reaction.success) {
          const config = this.configSubject.getValue();
          if (config) {
            const configRecord = config as unknown as ConfigRecord;
            const newConfig = { ...config, [section]: { ...configRecord[section], [option]: value } };
            this.configSubject.next(newConfig);
            // Propagate API key changes to the SSE stream immediately. This is
            // the only place the real (un-redacted) key is available, so it is
            // also where we persist it for recovery after a reload.
            if (section === 'web' && option === 'api_key') {
              const realKey = String(value ?? '') || null;
              this.writePersistedApiKey(realKey);
              this.setStreamApiKey(realKey);
            }
          }
        }
      },
    });
    return obs;
  }

  private getConfig(): void {
    this.logger.debug('Getting config...');
    this.restService.sendRequest(this.CONFIG_GET_URL).subscribe({
      next: (reaction) => {
        if (reaction.success) {
          try {
            const configJson: Config = JSON.parse(reaction.data!);
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

  private readPersistedApiKey(): string | null {
    try {
      return sessionStorage.getItem(StorageKeys.API_KEY);
    } catch {
      // sessionStorage may be unavailable (private browsing, test environments)
      return null;
    }
  }

  private writePersistedApiKey(apiKey: string | null): void {
    try {
      if (apiKey) {
        sessionStorage.setItem(StorageKeys.API_KEY, apiKey);
      } else {
        sessionStorage.removeItem(StorageKeys.API_KEY);
      }
    } catch {
      // sessionStorage may be unavailable (private browsing, test environments)
    }
  }
}
