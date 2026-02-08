import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';

@Injectable({ providedIn: 'root' })
export class ConnectedService implements StreamEventHandler {
  private readonly streamDispatch = inject(StreamDispatchService);
  private readonly connectedSubject = new BehaviorSubject<boolean>(false);

  constructor() {
    this.streamDispatch.registerHandler(this);
  }

  readonly connected$: Observable<boolean> =
    this.connectedSubject.asObservable();

  getEventNames(): string[] {
    return [];
  }

  onEvent(_eventName: string, _data: string): void {
    // No events to handle
  }

  onConnected(): void {
    if (!this.connectedSubject.getValue()) {
      this.connectedSubject.next(true);
    }
  }

  onDisconnected(): void {
    if (this.connectedSubject.getValue()) {
      this.connectedSubject.next(false);
    }
  }
}
