import { Injectable, NgZone, inject } from '@angular/core';

import { LoggerService } from '../utils/logger.service';

/**
 * Interface that services implement to receive SSE events
 * from the StreamDispatchService.
 */
export interface StreamEventHandler {
  /** Event names this handler is interested in. */
  getEventNames(): string[];

  /** Called when the SSE connection opens. */
  onConnected(): void;

  /** Called when the SSE connection drops. */
  onDisconnected(): void;

  /** Called when a subscribed event arrives. */
  onEvent(eventName: string, data: string): void;
}

@Injectable({ providedIn: 'root' })
export class StreamDispatchService {
  private readonly STREAM_URL = '/server/stream';
  private readonly RETRY_INTERVAL_MS = 3000;

  private readonly logger = inject(LoggerService);
  private readonly zone = inject(NgZone);

  private readonly eventNameToHandler = new Map<string, StreamEventHandler>();
  private readonly handlers: StreamEventHandler[] = [];

  registerHandler(handler: StreamEventHandler): void {
    for (const eventName of handler.getEventNames()) {
      this.eventNameToHandler.set(eventName, handler);
    }
    this.handlers.push(handler);
  }

  start(): void {
    this.connectStream();
  }

  private connectStream(): void {
    const eventSource = new EventSource(this.STREAM_URL);

    for (const eventName of Array.from(this.eventNameToHandler.keys())) {
      eventSource.addEventListener(eventName, (event: MessageEvent) => {
        this.zone.run(() => {
          this.eventNameToHandler.get(eventName)!.onEvent(eventName, event.data);
        });
      });
    }

    eventSource.onopen = () => {
      this.logger.info('Connected to server stream');
      for (const handler of this.handlers) {
        this.zone.run(() => handler.onConnected());
      }
    };

    eventSource.onerror = (err) => {
      this.logger.error('Error in stream: %O', err);
      eventSource.close();

      for (const handler of this.handlers) {
        this.zone.run(() => handler.onDisconnected());
      }

      setTimeout(() => this.connectStream(), this.RETRY_INTERVAL_MS);
    };
  }
}
