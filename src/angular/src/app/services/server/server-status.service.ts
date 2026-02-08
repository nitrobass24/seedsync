import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { Localization } from '../../models/localization';
import { ServerStatus, ServerStatusJson, serverStatusFromJson } from '../../models/server-status';

@Injectable({ providedIn: 'root' })
export class ServerStatusService implements StreamEventHandler {
  private readonly streamDispatch = inject(StreamDispatchService);

  private readonly statusSubject = new BehaviorSubject<ServerStatus>({
    server: {
      up: false,
      errorMessage: Localization.Notification.STATUS_CONNECTION_WAITING,
    },
    controller: {
      latestLocalScanTime: null,
      latestRemoteScanTime: null,
      latestRemoteScanFailed: false,
      latestRemoteScanError: null,
    },
  });

  readonly status$: Observable<ServerStatus> = this.statusSubject.asObservable();

  constructor() {
    this.streamDispatch.registerHandler(this);
  }

  getEventNames(): string[] {
    return ['status'];
  }

  onEvent(_eventName: string, data: string): void {
    const statusJson: ServerStatusJson = JSON.parse(data);
    this.statusSubject.next(serverStatusFromJson(statusJson));
  }

  onConnected(): void {
    // nothing to do
  }

  onDisconnected(): void {
    this.statusSubject.next({
      server: {
        up: false,
        errorMessage: Localization.Error.SERVER_DISCONNECTED,
      },
      controller: {
        latestLocalScanTime: null,
        latestRemoteScanTime: null,
        latestRemoteScanFailed: false,
        latestRemoteScanError: null,
      },
    });
  }
}
