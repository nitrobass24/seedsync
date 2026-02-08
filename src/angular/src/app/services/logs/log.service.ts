import { Injectable, inject } from '@angular/core';
import { Observable, ReplaySubject } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LogRecord, logRecordFromJson } from '../../models/log-record';

@Injectable({ providedIn: 'root' })
export class LogService implements StreamEventHandler {
  private readonly streamDispatch = inject(StreamDispatchService);

  private readonly logsSubject = new ReplaySubject<LogRecord>();

  readonly logs$: Observable<LogRecord> = this.logsSubject.asObservable();

  constructor() {
    this.streamDispatch.registerHandler(this);
  }

  getEventNames(): string[] {
    return ['log-record'];
  }

  onEvent(_eventName: string, data: string): void {
    this.logsSubject.next(logRecordFromJson(JSON.parse(data)));
  }

  onConnected(): void {
    // nothing to do
  }

  onDisconnected(): void {
    // nothing to do
  }
}
