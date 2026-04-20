import { Injectable, Injector, inject } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { StreamDispatchService } from '../base/stream-dispatch.service';
import { Config } from '../../models/config';

/** Value a config field may take (matches OptionComponent's value shape). */
export type ConfigValue = string | number | boolean | null;

/** Sentinel value sent to the backend when the user clears a text field. */
export const EMPTY_VALUE_SENTINEL = '__empty__';

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
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.getConfig();
      } else {
        this.configSubject.next(null);
        this.syncStreamApiKey(null);
      }
    });
  }

  set(section: string, option: string, value: ConfigValue): Observable<WebReaction> {
    const valueStr = String(value ?? '');
    const currentConfig = this.configSubject.getValue();
    const configAsRecord = currentConfig as unknown as Record<string, Record<string, ConfigValue>> | null;
    if (!currentConfig || !(section in currentConfig) || !configAsRecord || !(option in configAsRecord[section])) {
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
            const sectionValues = (config as unknown as Record<string, Record<string, ConfigValue>>)[section];
            const newConfig = { ...config, [section]: { ...sectionValues, [option]: value } };
            this.configSubject.next(newConfig);
            // Propagate API key changes to the SSE stream immediately
            if (section === 'web' && option === 'api_key') {
              this.syncStreamApiKey(newConfig);
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
            this.syncStreamApiKey(null);
          }
        } else {
          this.logger.error('Failed to get config: %s', reaction.errorMessage);
          this.configSubject.next(null);
          this.syncStreamApiKey(null);
        }
      },
    });
  }

  private syncStreamApiKey(config: Config | null): void {
    const apiKey = config?.web?.api_key || null;
    // Use injector.get() to break circular dependency:
    // StreamDispatchService -> ConnectedService -> ConfigService
    const streamDispatch = this.injector.get(StreamDispatchService);
    streamDispatch.setApiKey(apiKey);
  }
}
