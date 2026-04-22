import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
// Injector not needed — TestBed handles DI
import { BehaviorSubject, of } from "rxjs";

import { ConfigService, EMPTY_VALUE_SENTINEL } from "./config.service";
import { ConnectedService } from "../utils/connected.service";
import { LoggerService } from "../utils/logger.service";
import { RestService, WebReaction } from "../utils/rest.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { Config } from "../../models/config";

function makeConfig(overrides: Partial<Config> = {}): Config {
  return {
    general: { log_level: "INFO", verbose: false, exclude_patterns: "" },
    lftp: {
      remote_address: "host",
      remote_username: "user",
      remote_password: "pass",
      remote_port: 22,
      remote_path: "/remote",
      local_path: "/local",
      remote_path_to_scan_script: null,
      use_ssh_key: false,
      num_max_parallel_downloads: 1,
      num_max_parallel_files_per_download: 1,
      num_max_connections_per_root_file: 1,
      num_max_connections_per_dir_file: 1,
      num_max_total_connections: 1,
      use_temp_file: false,
      net_limit_rate: null,
      net_socket_buffer: null,
      pget_min_chunk_size: null,
      mirror_parallel_directories: false,
      net_timeout: null,
      net_max_retries: null,
      net_reconnect_interval_base: null,
      net_reconnect_interval_multiplier: null,
    },
    controller: {
      interval_ms_remote_scan: 30000,
      interval_ms_local_scan: 30000,
      interval_ms_downloading_scan: 2000,
      extract_path: null,
      use_local_path_as_extract_path: true,
      staging_path: null,
      use_staging: false,
    },
    web: { port: 8080, api_key: "test-key" },
    autoqueue: {
      enabled: false,
      patterns_only: false,
      auto_extract: false,
      auto_delete_remote: false,
    },
    logging: { log_format: null },
    notifications: {
      webhook_url: null,
      notify_on_download_complete: false,
      notify_on_extraction_complete: false,
      notify_on_extraction_failed: false,
      notify_on_delete_complete: false,
    },
    integrations: {
      sonarr_url: null,
      sonarr_api_key: null,
      sonarr_enabled: false,
      radarr_url: null,
      radarr_api_key: null,
      radarr_enabled: false,
    },
    validate: {
      enabled: false,
      algorithm: "md5",
      auto_validate: false,
      xfer_verify: false,
    },
    ...overrides,
  };
}

describe("ConfigService", () => {
  let service: ConfigService;
  let connectedSubject: BehaviorSubject<boolean>;
  let mockRestService: { sendRequest: ReturnType<typeof vi.fn> };
  let mockStreamDispatch: { setApiKey: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    connectedSubject = new BehaviorSubject<boolean>(false);
    mockRestService = { sendRequest: vi.fn() };
    mockStreamDispatch = { setApiKey: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        ConfigService,
        {
          provide: ConnectedService,
          useValue: { connected$: connectedSubject.asObservable() },
        },
        { provide: RestService, useValue: mockRestService },
        {
          provide: LoggerService,
          useValue: {
            debug: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
            warn: vi.fn(),
          },
        },
        {
          provide: StreamDispatchService,
          useValue: mockStreamDispatch,
        },
      ],
    });
    service = TestBed.inject(ConfigService);
  });

  // --- Initial state ---

  it("should emit null as the initial config", () => {
    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  it("should return null from configSnapshot initially", () => {
    expect(service.configSnapshot).toBeNull();
  });

  // --- Loading config on connect ---

  it("should fetch config from REST when connected", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    connectedSubject.next(true);

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toEqual(config);
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/config/get",
    );
  });

  it("should update configSnapshot after successful fetch", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    connectedSubject.next(true);
    expect(service.configSnapshot).toEqual(config);
  });

  it("should sync API key to StreamDispatchService on successful config load", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "my-key" } });
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    connectedSubject.next(true);
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("my-key");
  });

  // --- Disconnect ---

  it("should emit null config when disconnected", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    connectedSubject.next(true);

    connectedSubject.next(false);

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  it("should sync null API key when disconnected", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    connectedSubject.next(true);
    mockStreamDispatch.setApiKey.mockClear();

    connectedSubject.next(false);
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith(null);
  });

  // --- Error handling ---

  it("should emit null config when REST request fails", () => {
    mockRestService.sendRequest.mockReturnValue(
      of({
        success: false,
        data: null,
        errorMessage: "Server error",
      }),
    );

    connectedSubject.next(true);

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  it("should emit null config when response JSON is invalid", () => {
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: "not valid json {{{", errorMessage: null }),
    );

    connectedSubject.next(true);

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  // --- set() ---

  it("should return error when setting unknown section", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    connectedSubject.next(true);

    let result: WebReaction | undefined;
    service.set("nonexistent", "option", "value").subscribe((r) => (result = r));

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toContain("nonexistent.option");
  });

  it("should return error when setting unknown option in valid section", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    connectedSubject.next(true);

    let result: WebReaction | undefined;
    service.set("web", "nonexistent", "value").subscribe((r: WebReaction) => (result = r));

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toContain("web.nonexistent");
  });

  it("should return error when config is null", () => {
    // Config is null by default (not connected)
    let result: WebReaction | undefined;
    service.set("web", "port", "9090").subscribe((r: WebReaction) => (result = r));

    expect(result!.success).toBe(false);
  });

  it("should call REST with double-encoded value", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("web", "api_key", "my/key");

    const encoded = encodeURIComponent(encodeURIComponent("my/key"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/web/api_key/${encoded}`,
    );
  });

  it("should use __empty__ sentinel for empty string value", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("web", "api_key", "");

    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/web/api_key/${EMPTY_VALUE_SENTINEL}`,
    );
    // Empty api_key should propagate as null to StreamDispatchService
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith(null);
  });

  it("should update BehaviorSubject on successful set", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("web", "api_key", "new-key");

    expect(service.configSnapshot!.web.api_key).toBe("new-key");
  });

  it("should not update BehaviorSubject when set request fails", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: false, data: null, errorMessage: "fail" }),
      );
    connectedSubject.next(true);

    service.set("web", "api_key", "new-key");

    expect(service.configSnapshot!.web.api_key).toBe("old");
  });

  it("should sync API key to StreamDispatchService when web.api_key is set", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);
    mockStreamDispatch.setApiKey.mockClear();

    service.set("web", "api_key", "new-key");

    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("new-key");
  });

  it("should encode boolean true as 'true' in the URL", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("autoqueue", "enabled", true);

    const encoded = encodeURIComponent(encodeURIComponent("true"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/autoqueue/enabled/${encoded}`,
    );
  });

  it("should encode boolean false as 'false' in the URL", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("autoqueue", "enabled", false);

    const encoded = encodeURIComponent(encodeURIComponent("false"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/autoqueue/enabled/${encoded}`,
    );
  });

  it("should use __empty__ sentinel for null value", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);

    service.set("lftp", "net_limit_rate", null);

    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/lftp/net_limit_rate/${EMPTY_VALUE_SENTINEL}`,
    );
  });

  it("should not sync API key when setting a non-api_key option", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    connectedSubject.next(true);
    mockStreamDispatch.setApiKey.mockClear();

    service.set("web", "port", "9090");

    expect(mockStreamDispatch.setApiKey).not.toHaveBeenCalled();
  });
});
