import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { ServerStatusService } from "./server-status.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { ServerStatus, ServerStatusJson } from "../../models/server-status";
import { Localization } from "../../models/localization";

describe("ServerStatusService", () => {
  let service: ServerStatusService;
  let mockStreamDispatch: { registerHandler: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockStreamDispatch = { registerHandler: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        ServerStatusService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
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
});
