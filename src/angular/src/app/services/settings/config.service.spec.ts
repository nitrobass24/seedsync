import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
// Injector not needed — TestBed handles DI
import { BehaviorSubject, of } from "rxjs";

import { ConfigService, EMPTY_VALUE_SENTINEL } from "./config.service";
import { ConnectedService } from "../utils/connected.service";
import { LoggerService } from "../utils/logger.service";
import { RestService, WebReaction } from "../utils/rest.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { StorageKeys } from "../../common/storage-keys";
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
      notify_on_download_start: false,
      notify_on_download_complete: false,
      notify_on_extraction_complete: false,
      notify_on_extraction_failed: false,
      notify_on_delete_complete: false,
      discord_webhook_url: null,
      telegram_bot_token: null,
      telegram_chat_id: null,
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
  let store: Record<string, string>;
  let mockSessionStorage: {
    getItem: ReturnType<typeof vi.fn>;
    setItem: ReturnType<typeof vi.fn>;
    removeItem: ReturnType<typeof vi.fn>;
  };
  let originalSessionStorage: Storage;

  /**
   * Lazily construct the service. The constructor fetches config and
   * rehydrates the persisted API key, so each test configures its mocks
   * (sendRequest return values, seeded sessionStorage) BEFORE calling this.
   */
  function createService(): ConfigService {
    service = TestBed.inject(ConfigService);
    return service;
  }

  beforeEach(() => {
    connectedSubject = new BehaviorSubject<boolean>(false);
    // Safe default so the constructor's init fetch never crashes on undefined.
    mockRestService = {
      sendRequest: vi.fn().mockReturnValue(
        of({ success: false, data: null, errorMessage: "not configured" }),
      ),
    };
    mockStreamDispatch = { setApiKey: vi.fn() };

    store = {};
    mockSessionStorage = {
      getItem: vi.fn((key: string) => (key in store ? store[key] : null)),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
    };
    originalSessionStorage = globalThis.sessionStorage;
    Object.defineProperty(globalThis, "sessionStorage", {
      value: mockSessionStorage,
      configurable: true,
      writable: true,
    });

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
  });

  afterEach(() => {
    Object.defineProperty(globalThis, "sessionStorage", {
      value: originalSessionStorage,
      configurable: true,
      writable: true,
    });
  });

  // --- Initial state ---

  it("should emit null as the initial config", () => {
    // Default mock returns a failure reaction, so the init fetch leaves config null.
    createService();
    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  it("should return null from configSnapshot initially", () => {
    createService();
    expect(service.configSnapshot).toBeNull();
  });

  // --- Loading config on connect ---

  it("should fetch config from REST when connected", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    createService();
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

    createService();
    connectedSubject.next(true);
    expect(service.configSnapshot).toEqual(config);
  });

  it("should sync API key to StreamDispatchService on successful config load", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "my-key" } });
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    createService();
    connectedSubject.next(true);
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("my-key");
  });

  // --- Init-ordering deadlock fix (#514) ---

  it("should fetch config at init independent of connected$", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    // connected$ is still false (never emits true)
    createService();

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toEqual(config);
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/config/get",
    );
  });

  it("should rehydrate persisted api_key from sessionStorage at init and push it to the stream before any connect", () => {
    store[StorageKeys.API_KEY] = "real-key";

    // connected$ stays false; the key must reach the stream during construction
    createService();

    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("real-key");
  });

  it("should NOT push the redacted sentinel to the stream and should keep the persisted key", () => {
    store[StorageKeys.API_KEY] = "real-key";
    const config = makeConfig({ web: { port: 8080, api_key: "********" } });
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    createService();

    // The persisted real key is pushed at init, but the redacted '********'
    // returned by /server/config/get must never reach the stream.
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("real-key");
    expect(mockStreamDispatch.setApiKey).not.toHaveBeenCalledWith("********");
    expect(store[StorageKeys.API_KEY]).toBe("real-key");
  });

  it("should tolerate sessionStorage throwing during init (private browsing)", () => {
    mockSessionStorage.getItem.mockImplementation(() => {
      throw new Error("denied");
    });
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );

    expect(() => createService()).not.toThrow();
  });

  // --- Disconnect ---

  it("should retain config on disconnect so the UI keeps working", () => {
    const config = makeConfig();
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    createService();
    connectedSubject.next(true);

    connectedSubject.next(false);

    // Config is fetched at init independent of the stream, so a transient
    // disconnect must not wipe it out (and trigger a deadlock-prone refetch loop).
    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toEqual(config);
  });

  it("should NOT clear the api key on disconnect so the next reconnect can authenticate", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "my-key" } });
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: JSON.stringify(config), errorMessage: null }),
    );
    createService();
    connectedSubject.next(true);
    mockStreamDispatch.setApiKey.mockClear();

    connectedSubject.next(false);

    // The key must stay on the stream so the backoff-driven reconnect carries it.
    expect(mockStreamDispatch.setApiKey).not.toHaveBeenCalledWith(null);
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

    createService();
    connectedSubject.next(true);

    let result: Config | null | undefined;
    service.config$.subscribe((c) => (result = c));
    expect(result).toBeNull();
  });

  it("should emit null config when response JSON is invalid", () => {
    mockRestService.sendRequest.mockReturnValue(
      of({ success: true, data: "not valid json {{{", errorMessage: null }),
    );

    createService();
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
    createService();
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
    createService();
    connectedSubject.next(true);

    let result: WebReaction | undefined;
    service.set("web", "nonexistent", "value").subscribe((r: WebReaction) => (result = r));

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toContain("web.nonexistent");
  });

  it("should return error when config is null", () => {
    // Default mock returns failure, so config stays null after init.
    createService();
    let result: WebReaction | undefined;
    service.set("web", "port", "9090").subscribe((r: WebReaction) => (result = r));

    expect(result!.success).toBe(false);
  });

  it("should call REST with double-encoded value", () => {
    const config = makeConfig();
    // init fetch -> connect fetch -> set response
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
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
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);

    service.set("web", "api_key", "");

    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/web/api_key/${EMPTY_VALUE_SENTINEL}`,
    );
    // Empty api_key should propagate as null to StreamDispatchService
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith(null);
  });

  it("should remove persisted api_key from sessionStorage when set empty", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    store[StorageKeys.API_KEY] = "old";
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);

    service.set("web", "api_key", "");

    expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(StorageKeys.API_KEY);
    expect(store[StorageKeys.API_KEY]).toBeUndefined();
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith(null);
  });

  it("should persist the real api_key to sessionStorage on successful set", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);

    service.set("web", "api_key", "new-key");

    expect(mockSessionStorage.setItem).toHaveBeenCalledWith(
      StorageKeys.API_KEY,
      "new-key",
    );
    expect(store[StorageKeys.API_KEY]).toBe("new-key");
  });

  it("should not throw when sessionStorage throws during set", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);
    mockSessionStorage.setItem.mockImplementation(() => {
      throw new Error("denied");
    });

    expect(() => service.set("web", "api_key", "new-key")).not.toThrow();
    // Stream still receives the key even if persistence failed.
    expect(mockStreamDispatch.setApiKey).toHaveBeenCalledWith("new-key");
  });

  it("should update BehaviorSubject on successful set", () => {
    const config = makeConfig({ web: { port: 8080, api_key: "old" } });
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
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
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: false, data: null, errorMessage: "fail" }),
      );
    createService();
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
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
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
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);

    service.set("autoqueue", "enabled", true);

    const encoded = encodeURIComponent(encodeURIComponent("true"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/autoqueue/enabled/${encoded}`,
    );
    expect(service.configSnapshot!.autoqueue.enabled).toBe(true);
  });

  it("should encode boolean false as 'false' in the URL", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);

    service.set("autoqueue", "enabled", false);

    const encoded = encodeURIComponent(encodeURIComponent("false"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      `/server/config/set/autoqueue/enabled/${encoded}`,
    );
    expect(service.configSnapshot!.autoqueue.enabled).toBe(false);
  });

  it("should use __empty__ sentinel for null value", () => {
    const config = makeConfig();
    mockRestService.sendRequest
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
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
        of({ success: true, data: JSON.stringify(config), errorMessage: null }),
      )
      .mockReturnValueOnce(
        of({ success: true, data: null, errorMessage: null }),
      );
    createService();
    connectedSubject.next(true);
    mockStreamDispatch.setApiKey.mockClear();

    service.set("web", "port", "9090");

    expect(mockStreamDispatch.setApiKey).not.toHaveBeenCalled();
  });
});
