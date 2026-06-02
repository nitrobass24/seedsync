import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { ServerStatusService } from "./server-status.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { LoggerService } from "../utils/logger.service";
import { ServerStatus, ServerStatusJson } from "../../models/server-status";
import { Localization } from "../../models/localization";

describe("ServerStatusService", () => {
  let service: ServerStatusService;
  let mockStreamDispatch: { registerHandler: ReturnType<typeof vi.fn> };
  let mockLogger: {
    debug: ReturnType<typeof vi.fn>;
    error: ReturnType<typeof vi.fn>;
    info: ReturnType<typeof vi.fn>;
    warn: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    mockStreamDispatch = { registerHandler: vi.fn() };
    mockLogger = {
      debug: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        ServerStatusService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
        { provide: LoggerService, useValue: mockLogger },
      ],
    });
    service = TestBed.inject(ServerStatusService);
  });

  it("should register with StreamDispatchService on construction", () => {
    expect(mockStreamDispatch.registerHandler).toHaveBeenCalledWith(service);
  });

  it("should have initial status with server.up = false", () => {
    let result: ServerStatus | undefined;
    service.status$.subscribe((s) => (result = s));
    expect(result!.server.up).toBe(false);
    expect(result!.server.errorMessage).toBe(
      Localization.Notification.STATUS_CONNECTION_WAITING,
    );
  });

  it("should return ['status'] from getEventNames()", () => {
    expect(service.getEventNames()).toEqual(["status"]);
  });

  it("should parse and push status on onEvent", () => {
    const statusJson: ServerStatusJson = {
      server: { up: true, error_msg: "" },
      controller: {
        latest_local_scan_time: "1700000000",
        latest_remote_scan_time: null,
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
        no_enabled_pairs: false,
      },
    };
    service.onEvent("status", JSON.stringify(statusJson));

    let result: ServerStatus | undefined;
    service.status$.subscribe((s) => (result = s));
    expect(result!.server.up).toBe(true);
    expect(result!.server.errorMessage).toBe("");
    expect(result!.controller.latestLocalScanTime).toEqual(
      new Date(1000 * 1700000000),
    );
    expect(result!.controller.latestRemoteScanTime).toBeNull();
    expect(result!.controller.latestRemoteScanFailed).toBe(false);
  });

  it("should reset to disconnected status on onDisconnected()", () => {
    // First set a connected status
    const statusJson: ServerStatusJson = {
      server: { up: true, error_msg: "" },
      controller: {
        latest_local_scan_time: "1700000000",
        latest_remote_scan_time: "1700000000",
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
        no_enabled_pairs: false,
      },
    };
    service.onEvent("status", JSON.stringify(statusJson));

    // Then disconnect
    service.onDisconnected();

    let result: ServerStatus | undefined;
    service.status$.subscribe((s) => (result = s));
    expect(result!.server.up).toBe(false);
    expect(result!.server.errorMessage).toBe(
      Localization.Error.SERVER_DISCONNECTED,
    );
    expect(result!.controller.latestLocalScanTime).toBeNull();
    expect(result!.controller.latestRemoteScanTime).toBeNull();
    expect(result!.controller.latestRemoteScanFailed).toBe(false);
    expect(result!.controller.latestRemoteScanError).toBeNull();
  });

  it("should not throw and should keep last-good status on a malformed status event (issue #516)", () => {
    // Seed a valid connected status.
    const statusJson: ServerStatusJson = {
      server: { up: true, error_msg: "" },
      controller: {
        latest_local_scan_time: "1700000000",
        latest_remote_scan_time: null,
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
        no_enabled_pairs: false,
      },
    };
    service.onEvent("status", JSON.stringify(statusJson));

    // A malformed payload must not throw and must not degrade the status.
    expect(() => service.onEvent("status", "garbage")).not.toThrow();
    expect(mockLogger.error).toHaveBeenCalled();

    let result: ServerStatus | undefined;
    service.status$.subscribe((s) => (result = s));
    expect(result!.server.up).toBe(true);
  });

  it("should still parse a valid status event after a malformed one (issue #516)", () => {
    service.onEvent("status", "garbage");

    const statusJson: ServerStatusJson = {
      server: { up: true, error_msg: "" },
      controller: {
        latest_local_scan_time: null,
        latest_remote_scan_time: null,
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
        no_enabled_pairs: false,
      },
    };
    service.onEvent("status", JSON.stringify(statusJson));

    let result: ServerStatus | undefined;
    service.status$.subscribe((s) => (result = s));
    expect(result!.server.up).toBe(true);
  });
});
