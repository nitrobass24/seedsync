import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LoggerService } from '../utils/logger.service';
import { Localization } from '../../models/localization';
import { ServerStatus, ServerStatusJson, serverStatusFromJson } from '../../models/server-status';

function disconnectedStatus(errorMessage: string): ServerStatus {
  return {
    server: { up: false, errorMessage },
    controller: {
      latestRemoteScanTime: null,
      latestRemoteScanFailed: false,
      latestRemoteScanError: null,
      noEnabledPairs: false,
    },
  };
}

@Injectable({ providedIn: 'root' })
export class ServerStatusService implements StreamEventHandler {
  private readonly streamDispatch = inject(StreamDispatchService);
  private readonly logger = inject(LoggerService);

  private readonly statusSubject = new BehaviorSubject<ServerStatus>(
    disconnectedStatus(Localization.Notification.STATUS_CONNECTION_WAITING),
  );

  readonly status$: Observable<ServerStatus> = this.statusSubject.asObservable();

  constructor() {
    this.streamDispatch.registerHandler(this);
  }

  getEventNames(): string[] {
    return ['status'];
  }

  onEvent(_eventName: string, data: string): void {
    // Guard the parse of server-controlled SSE payloads: a malformed/truncated
    // event must not throw inside the listener callback. Log and skip the bad
    // event, leaving the last-good status in place (mirrors ConfigService).
    try {
      const statusJson: ServerStatusJson = JSON.parse(data);
      this.statusSubject.next(serverStatusFromJson(statusJson));
    } catch (e) {
      this.logger.error('Failed to parse status event: %O', e);
    }
  }

  onDisconnected(): void {
    this.statusSubject.next(disconnectedStatus(Localization.Error.SERVER_DISCONNECTED));
  }
}
