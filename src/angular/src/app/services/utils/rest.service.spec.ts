import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import {
  provideHttpClient,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";

import { RestService, WebReaction } from "./rest.service";
import { LoggerService } from "./logger.service";

describe("RestService", () => {
  let service: RestService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        RestService,
        provideHttpClient(),
        provideHttpClientTesting(),
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
    service = TestBed.inject(RestService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  // --- Successful GET ---

  it("should return a successful WebReaction for a 200 response", () => {
    let result: WebReaction | undefined;
    service.sendRequest("/server/config/get").subscribe((r) => (result = r));

    const req = httpTesting.expectOne("/server/config/get");
    expect(req.request.method).toBe("GET");
    req.flush("response body");

    expect(result!.success).toBe(true);
    expect(result!.data).toBe("response body");
    expect(result!.errorMessage).toBeNull();
  });

  it("should request with responseType text", () => {
    service.sendRequest("/server/test").subscribe();

    const req = httpTesting.expectOne("/server/test");
    expect(req.request.responseType).toBe("text");
    req.flush("");
  });

  // --- Error handling ---

  it("should return a failed WebReaction for a 404 response", () => {
    let result: WebReaction | undefined;
    service.sendRequest("/server/missing").subscribe((r) => (result = r));

    httpTesting
      .expectOne("/server/missing")
      .flush("Not Found", { status: 404, statusText: "Not Found" });

    expect(result!.success).toBe(false);
    expect(result!.data).toBeNull();
    expect(result!.errorMessage).toBe("Not Found");
  });

  it("should return a failed WebReaction for a 500 response", () => {
    let result: WebReaction | undefined;
    service.sendRequest("/server/error").subscribe((r) => (result = r));

    httpTesting
      .expectOne("/server/error")
      .flush("Internal Server Error", {
        status: 500,
        statusText: "Internal Server Error",
      });

    expect(result!.success).toBe(false);
    expect(result!.data).toBeNull();
    expect(result!.errorMessage).toBe("Internal Server Error");
  });

  it("should handle network error (Event-based error)", () => {
    let result: WebReaction | undefined;
    service.sendRequest("/server/network-fail").subscribe((r) => (result = r));

    httpTesting
      .expectOne("/server/network-fail")
      .error(new ProgressEvent("error"));

    expect(result!.success).toBe(false);
    expect(result!.data).toBeNull();
    expect(result!.errorMessage).toBe("error");
  });

  // --- shareReplay behavior ---

  it("should replay the last value to late subscribers via shareReplay", () => {
    const obs = service.sendRequest("/server/config/get");

    // First subscriber triggers the request
    let result1: WebReaction | undefined;
    obs.subscribe((r) => (result1 = r));

    httpTesting.expectOne("/server/config/get").flush("data");

    // Late subscriber should still get the value
    let result2: WebReaction | undefined;
    obs.subscribe((r) => (result2 = r));

    expect(result1!.data).toBe("data");
    expect(result2!.data).toBe("data");
  });

  // --- URL construction ---

  it("should send GET to the exact URL provided", () => {
    service.sendRequest("/server/command/queue/my%20file").subscribe();

    const req = httpTesting.expectOne("/server/command/queue/my%20file");
    expect(req.request.method).toBe("GET");
    req.flush("");
  });

});
