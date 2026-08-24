import { Injectable, NgZone, inject } from '@angular/core';

import { LoggerService } from '../utils/logger.service';

/**
 * Interface that services implement to receive SSE events
 * from the StreamDispatchService. All members are optional so handlers
 * only implement the callbacks they care about.
 */
export interface StreamEventHandler {
  /** Event names this handler is interested in. */
  getEventNames?(): string[];

  /** Called when the SSE connection opens. */
  onConnected?(): void;

  /** Called when the SSE connection drops. */
  onDisconnected?(): void;

  /** Called when a subscribed event arrives. */
  onEvent?(eventName: string, data: string): void;
}

@Injectable({ providedIn: 'root' })
export class StreamDispatchService {
  private readonly STREAM_URL = '/server/stream';
  /** Base delay for the first reconnect attempt. */
  private readonly RETRY_BASE_MS = 1000;
  /** Upper bound on the exponential backoff delay. */
  private readonly RETRY_MAX_MS = 30000;
  /** Maximum random jitter added to each backoff delay. */
  private readonly RETRY_JITTER_MS = 1000;

  private readonly logger = inject(LoggerService);
  private readonly zone = inject(NgZone);

  private readonly eventNameToHandler = new Map<string, StreamEventHandler>();
  private readonly handlers: StreamEventHandler[] = [];

  registerHandler(handler: StreamEventHandler): void {
    for (const eventName of handler.getEventNames?.() ?? []) {
      this.eventNameToHandler.set(eventName, handler);
    }
    this.handlers.push(handler);
  }

  start(): void {
    this.connectStream();
  }

  private apiKey: string | null = null;
  private eventSource: EventSource | null = null;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private retryAttempt = 0;

  setApiKey(key: string | null): void {
    if (key === this.apiKey) {
      return;
    }
    this.apiKey = key;
    // Reconnect with the new key if we have an active connection or pending retry
    if (this.eventSource || this.retryTimeout) {
      // A key change should retry promptly, not wait out the current backoff.
      this.retryAttempt = 0;
      this.closeAndCancelRetry();
      this.connectStream();
    }
  }

  private closeAndCancelRetry(): void {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  private connectStream(): void {
    const url = this.apiKey
      ? `${this.STREAM_URL}?api_key=${encodeURIComponent(this.apiKey)}`
      : this.STREAM_URL;
    const eventSource = new EventSource(url);
    this.eventSource = eventSource;

    for (const eventName of Array.from(this.eventNameToHandler.keys())) {
      eventSource.addEventListener(eventName, (event: MessageEvent) => {
        this.zone.run(() => {
          this.eventNameToHandler.get(eventName)!.onEvent?.(eventName, event.data);
        });
      });
    }

    eventSource.onopen = () => {
      this.logger.info('Connected to server stream');
      // A successful connection resets the backoff so the next drop retries fast.
      this.retryAttempt = 0;
      for (const handler of this.handlers) {
        this.zone.run(() => handler.onConnected?.());
      }
    };

    eventSource.onerror = (err) => {
      // Guard: ignore if this EventSource is no longer the active one
      // (e.g., setApiKey already replaced it with a new connection)
      if (this.eventSource !== eventSource) {
        return;
      }

      this.logger.error('Error in stream: %O', err);
      this.closeAndCancelRetry();

      for (const handler of this.handlers) {
        this.zone.run(() => handler.onDisconnected?.());
      }

      const delay = this.nextRetryDelayMs();
      this.retryAttempt += 1;
      this.retryTimeout = setTimeout(() => {
        this.retryTimeout = null;
        this.connectStream();
      }, delay);
    };
  }

  /**
   * Capped exponential backoff with jitter. Prevents a tight reconnect loop
   * (e.g. when the server keeps returning 401 for a bad/missing API key) from
   * hammering the backend on a fixed cadence.
   */
  private nextRetryDelayMs(): number {
    const exponential = Math.min(this.RETRY_MAX_MS, this.RETRY_BASE_MS * 2 ** this.retryAttempt);
    const jitter = Math.random() * this.RETRY_JITTER_MS;
    return exponential + jitter;
  }
}
