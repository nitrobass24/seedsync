import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import {
  provideHttpClient,
  withInterceptors,
  HttpClient,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";

import { apiKeyInterceptor } from "./api-key.interceptor";
import { ConfigService } from "../settings/config.service";
import { Web } from "../../models/config";

// Shape used by the interceptor's partial-config tests. The interceptor only
// looks at `config.web.api_key`, so tests set a minimal subset (Partial<Web>)
// and the empty-object case simulates "missing web section".
type MockConfigSnapshot = { web?: Partial<Web> } | Record<string, never> | null;

describe("apiKeyInterceptor", () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;
  let mockConfigService: { configSnapshot: MockConfigSnapshot };

  beforeEach(() => {
    mockConfigService = { configSnapshot: null };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiKeyInterceptor])),
        provideHttpClientTesting(),
        { provide: ConfigService, useValue: mockConfigService },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  // --- API key added to /server/* requests ---

  it("should add X-Api-Key header to /server/config/get requests", () => {
    mockConfigService.configSnapshot = { web: { api_key: "my-secret" } };

    http.get("/server/config/get", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.headers.get("X-Api-Key")).toBe("my-secret");
    req.flush("");
  });

  it("should add X-Api-Key header to /server subpath requests", () => {
    mockConfigService.configSnapshot = { web: { api_key: "key123" } };

    http.get("/server/command/queue/file", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/command/queue/file");
    expect(req.request.headers.get("X-Api-Key")).toBe("key123");
    req.flush("");
  });

  it("should add X-Api-Key header to the exact /server URL", () => {
    mockConfigService.configSnapshot = { web: { api_key: "key123" } };

    http.get("/server", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server");
    expect(req.request.headers.get("X-Api-Key")).toBe("key123");
    req.flush("");
  });

  // --- No API key when not configured ---

  it("should not add X-Api-Key header when config is null", () => {
    mockConfigService.configSnapshot = null;

    http.get("/server/config/get", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  it("should not add X-Api-Key header when api_key is empty string", () => {
    mockConfigService.configSnapshot = { web: { api_key: "" } };

    http.get("/server/config/get", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  it("should not add X-Api-Key header when api_key is null", () => {
    mockConfigService.configSnapshot = { web: { api_key: null } };

    http.get("/server/config/get", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  it("should not add X-Api-Key header when web section is missing", () => {
    mockConfigService.configSnapshot = {};

    http.get("/server/config/get", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  // --- Non-server URLs are not intercepted ---

  it("should not add X-Api-Key header to non-server URLs", () => {
    mockConfigService.configSnapshot = { web: { api_key: "my-secret" } };

    http.get("/api/other", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/api/other");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  it("should not add X-Api-Key to URLs that contain server but do not start with /server", () => {
    mockConfigService.configSnapshot = { web: { api_key: "my-secret" } };

    http.get("/other/server/path", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/other/server/path");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });

  it("should not intercept /serverExtra path (not starting with /server/)", () => {
    mockConfigService.configSnapshot = { web: { api_key: "my-secret" } };

    http.get("/serverExtra", { responseType: "text" }).subscribe();

    const req = httpTesting.expectOne("/serverExtra");
    expect(req.request.headers.has("X-Api-Key")).toBe(false);
    req.flush("");
  });
});
