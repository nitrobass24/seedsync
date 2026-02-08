import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';

import { ConnectedService } from '../utils/connected.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { Config } from '../../models/config';

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly CONFIG_GET_URL = '/server/config/get';
  private readonly CONFIG_SET_URL = (section: string, option: string, value: string) =>
    `/server/config/set/${section}/${option}/${value}`;

  private readonly connectedService = inject(ConnectedService);
  private readonly restService = inject(RestService);
  private readonly logger = inject(LoggerService);

  private readonly configSubject = new BehaviorSubject<Config | null>(null);

  readonly config$: Observable<Config | null> = this.configSubject.asObservable();

  constructor() {
    this.connectedService.connected$.subscribe((connected) => {
      if (connected) {
        this.getConfig();
      } else {
        this.configSubject.next(null);
      }
    });
  }

  set(section: string, option: string, value: any): Observable<WebReaction> {
    const valueStr: string = value;
    const currentConfig = this.configSubject.getValue();
    if (!currentConfig || !(section in currentConfig) || !(option in (currentConfig as any)[section])) {
      return of({
        success: false,
        data: null,
        errorMessage: `Config has no option named ${section}.${option}`,
      });
    }

    // Double-encode the value, use sentinel for empty strings
    const valueEncoded =
      valueStr.length === 0 ? '__empty__' : encodeURIComponent(encodeURIComponent(valueStr));
    const url = this.CONFIG_SET_URL(section, option, valueEncoded);
    const obs = this.restService.sendRequest(url);
    obs.subscribe({
      next: (reaction) => {
        if (reaction.success) {
          const config = this.configSubject.getValue();
          if (config) {
            const newConfig = { ...config, [section]: { ...(config as any)[section], [option]: value } };
            this.configSubject.next(newConfig);
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
          const configJson: Config = JSON.parse(reaction.data!);
          this.configSubject.next(configJson);
        } else {
          this.configSubject.next(null);
        }
      },
    });
  }
}
