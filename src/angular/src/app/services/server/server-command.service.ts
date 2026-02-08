import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { RestService, WebReaction } from '../utils/rest.service';

@Injectable({ providedIn: 'root' })
export class ServerCommandService {
  private readonly RESTART_URL = '/server/command/restart';

  private readonly restService = inject(RestService);

  restart(): Observable<WebReaction> {
    return this.restService.sendRequest(this.RESTART_URL);
  }
}
