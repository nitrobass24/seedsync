import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import {
  StreamDispatchService,
  StreamEventHandler,
} from "./stream-dispatch.service";
import { LoggerService } from "../utils/logger.service";

// --- Mock EventSource ---

type EventSourceListener = (event: MessageEvent) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  private listeners = new Map<string, EventSourceListener[]>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener): void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(listener);
  }

  close(): void {
    this.closed = true;
  }

  // Test helpers
  simulateOpen(): void {
    this.onopen?.(new Event("open"));
  }

  simulateError(): void {
    this.onerror?.(new Event("error"));
  }

  simulateEvent(name: string, data: string): void {
    const handlers = this.listeners.get(name) || [];
    for (const handler of handlers) {
      handler(new MessageEvent(name, { data }));
    }
  }
}

function latestEventSource(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

describe("StreamDispatchService", () => {
  let service: StreamDispatchService;
  let originalEventSource: typeof globalThis.EventSource;

  beforeEach(() => {
    MockEventSource.instances = [];
    originalEventSource = globalThis.EventSource;
    (globalThis as any).EventSource = MockEventSource;

    TestBed.configureTestingModule({
      providers: [
        StreamDispatchService,
        {
          provide: LoggerService,
          useValue: {
            debug: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
            warn: vi.fn(),
          },
        },
      ],
    });
    service = TestBed.inject(StreamDispatchService);
  });

  afterEach(() => {
    vi.useRealTimers();
    (globalThis as any).EventSource = originalEventSource;
  });

  function makeHandler(eventNames: string[] = []) {
    return {
      getEventNames: () => eventNames,
      onConnected: vi.fn() as unknown as (() => void) & ReturnType<typeof vi.fn>,
      onDisconnected: vi.fn() as unknown as (() => void) & ReturnType<typeof vi.fn>,
      onEvent: vi.fn() as unknown as ((eventName: string, data: string) => void) & ReturnType<typeof vi.fn>,
    };
  }

  // --- Registration ---

  it("should dispatch events to a registered handler", () => {
    const handler = makeHandler(["model-init"]);
    service.registerHandler(handler);

    service.start();
    latestEventSource().simulateEvent("model-init", '{"test": true}');

    expect(handler.onEvent).toHaveBeenCalledWith("model-init", '{"test": true}');
  });

  // --- Connection ---

  it("should create an EventSource when start is called", () => {
    service.start();
    expect(MockEventSource.instances.length).toBe(1);
    expect(latestEventSource().url).toBe("/server/stream");
  });

  it("should notify all handlers on open", () => {
    const handler1 = makeHandler();
    const handler2 = makeHandler();
    service.registerHandler(handler1);
    service.registerHandler(handler2);

    service.start();
    latestEventSource().simulateOpen();

    expect(handler1.onConnected).toHaveBeenCalled();
    expect(handler2.onConnected).toHaveBeenCalled();
  });

  // --- Event dispatch ---

  it("should dispatch events to the correct handler", () => {
    const handler = makeHandler(["model-init", "model-updated"]);
    service.registerHandler(handler);

    service.start();
    latestEventSource().simulateEvent("model-init", '["file1"]');

    expect(handler.onEvent).toHaveBeenCalledWith("model-init", '["file1"]');
  });

  it("should not dispatch events for unregistered event names", () => {
    const handler = makeHandler(["model-init"]);
    service.registerHandler(handler);

    service.start();
    latestEventSource().simulateEvent("unknown-event", "data");

    expect(handler.onEvent).not.toHaveBeenCalled();
  });

  it("should dispatch different events to different handlers", () => {
    const handler1 = makeHandler(["model-init"]);
    const handler2 = makeHandler(["log-init"]);
    service.registerHandler(handler1);
    service.registerHandler(handler2);

    service.start();
    latestEventSource().simulateEvent("log-init", "log-data");

    expect(handler1.onEvent).not.toHaveBeenCalled();
    expect(handler2.onEvent).toHaveBeenCalledWith("log-init", "log-data");
  });

  // --- Disconnect ---

  it("should notify all handlers on error (disconnect)", () => {
    vi.useFakeTimers();
    const handler = makeHandler();
    service.registerHandler(handler);

    service.start();
    latestEventSource().simulateError();

    expect(handler.onDisconnected).toHaveBeenCalled();
  });

  it("should close EventSource on error", () => {
    vi.useFakeTimers();
    service.start();
    const es = latestEventSource();
    es.simulateError();

    expect(es.closed).toBe(true);
  });

  // --- Reconnection ---

  it("should reconnect after error with retry delay", () => {
    vi.useFakeTimers();
    service.start();
    expect(MockEventSource.instances.length).toBe(1);

    latestEventSource().simulateError();
    expect(MockEventSource.instances.length).toBe(1);

    vi.advanceTimersByTime(3000);
    expect(MockEventSource.instances.length).toBe(2);

  });

  it("should not reconnect before retry interval", () => {
    vi.useFakeTimers();
    service.start();
    latestEventSource().simulateError();

    vi.advanceTimersByTime(2999);
    expect(MockEventSource.instances.length).toBe(1);

  });

  // --- API key ---

  it("should include API key in URL when set before start", () => {
    service.setApiKey("secret-key");
    service.start();

    expect(latestEventSource().url).toBe(
      "/server/stream?api_key=secret-key",
    );
  });

  it("should encode special characters in API key", () => {
    service.setApiKey("key with spaces&special=chars");
    service.start();

    expect(latestEventSource().url).toBe(
      `/server/stream?api_key=${encodeURIComponent("key with spaces&special=chars")}`,
    );
  });

  it("should reconnect with new API key when key changes during active connection", () => {
    service.start();
    const firstEs = latestEventSource();
    expect(firstEs.url).toBe("/server/stream");

    service.setApiKey("new-key");

    expect(firstEs.closed).toBe(true);
    expect(MockEventSource.instances.length).toBe(2);
    expect(latestEventSource().url).toBe(
      "/server/stream?api_key=new-key",
    );
  });

  it("should not reconnect when same API key is set", () => {
    service.setApiKey("same-key");
    service.start();
    expect(MockEventSource.instances.length).toBe(1);

    service.setApiKey("same-key");
    expect(MockEventSource.instances.length).toBe(1);
  });

  it("should not reconnect when API key is set but no active connection", () => {
    // No start() called, no active connection or pending retry
    service.setApiKey("key");
    expect(MockEventSource.instances.length).toBe(0);
  });

  it("should reconnect with new key during pending retry", () => {
    vi.useFakeTimers();
    service.start();
    latestEventSource().simulateError();
    // Now there's a pending retry timeout

    service.setApiKey("retry-key");
    // Should have created a new connection immediately
    expect(MockEventSource.instances.length).toBe(2);
    expect(latestEventSource().url).toBe(
      "/server/stream?api_key=retry-key",
    );

    // The old pending retry should have been cancelled
    vi.advanceTimersByTime(3000);
    expect(MockEventSource.instances.length).toBe(2);
  });

  it("should use URL without api_key param when key is null", () => {
    service.setApiKey("some-key");
    service.start();
    expect(latestEventSource().url).toContain("api_key=");

    service.setApiKey(null);
    expect(latestEventSource().url).toBe("/server/stream");
  });

  // --- Stale EventSource guard ---

  it("should ignore error from a stale EventSource after API key change", () => {
    vi.useFakeTimers();
    const handler = makeHandler();
    service.registerHandler(handler);

    service.start();
    const staleEs = latestEventSource();

    // Change API key which replaces the EventSource
    service.setApiKey("new-key");
    handler.onDisconnected.mockClear();

    // Simulate error on the OLD (stale) EventSource
    staleEs.simulateError();

    // Handler should NOT be notified because the stale EventSource is guarded
    expect(handler.onDisconnected).not.toHaveBeenCalled();

    // Stale error should not schedule a reconnect
    vi.advanceTimersByTime(3000);
    expect(MockEventSource.instances.length).toBe(2);
  });
});
