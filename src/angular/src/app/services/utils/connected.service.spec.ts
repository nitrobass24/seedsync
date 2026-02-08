import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { ConnectedService } from "./connected.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";

describe("ConnectedService", () => {
  let service: ConnectedService;
  let mockStreamDispatch: { registerHandler: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockStreamDispatch = { registerHandler: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        ConnectedService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
      ],
    });
    service = TestBed.inject(ConnectedService);
  });

  it("should register with StreamDispatchService on construction", () => {
    expect(mockStreamDispatch.registerHandler).toHaveBeenCalledWith(service);
  });

  it("should return empty array from getEventNames()", () => {
    expect(service.getEventNames()).toEqual([]);
  });

  it("should set connected$ to true on onConnected()", () => {
    service.onConnected();

    let result: boolean | undefined;
    service.connected$.subscribe((v) => (result = v));
    expect(result).toBe(true);
  });

  it("should set connected$ to false on onDisconnected()", () => {
    service.onConnected();
    service.onDisconnected();

    let result: boolean | undefined;
    service.connected$.subscribe((v) => (result = v));
    expect(result).toBe(false);
  });

  it("should not re-emit when onConnected() called twice", () => {
    let emitCount = 0;
    service.connected$.subscribe(() => emitCount++);
    const countAfterSubscribe = emitCount;

    service.onConnected();
    service.onConnected();

    expect(emitCount).toBe(countAfterSubscribe + 1);
  });

  it("should not re-emit when onDisconnected() called while already false", () => {
    let emitCount = 0;
    service.connected$.subscribe(() => emitCount++);
    const countAfterSubscribe = emitCount;

    service.onDisconnected();

    expect(emitCount).toBe(countAfterSubscribe);
  });

  it("should have initial value of false for connected$", () => {
    let result: boolean | undefined;
    service.connected$.subscribe((v) => (result = v));
    expect(result).toBe(false);
  });
});
