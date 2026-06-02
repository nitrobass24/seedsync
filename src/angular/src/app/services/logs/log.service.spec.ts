import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { LogService } from "./log.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { LoggerService } from "../utils/logger.service";
import { LogRecord, LogRecordJson } from "../../models/log-record";

describe("LogService", () => {
  let service: LogService;
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
        LogService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
        { provide: LoggerService, useValue: mockLogger },
      ],
    });
    service = TestBed.inject(LogService);
  });

  it("should register with StreamDispatchService on construction", () => {
    expect(mockStreamDispatch.registerHandler).toHaveBeenCalledWith(service);
  });

  it("should return ['log-record'] from getEventNames()", () => {
    expect(service.getEventNames()).toEqual(["log-record"]);
  });

  it("should parse and push log record on onEvent", () => {
    const logJson: LogRecordJson = {
      time: 1700000000,
      level_name: "INFO",
      logger_name: "test.logger",
      message: "Test message",
      exc_tb: "",
    };

    let result: LogRecord | undefined;
    service.logs$.subscribe((r) => (result = r));
    service.onEvent("log-record", JSON.stringify(logJson));
    expect(result!.time).toEqual(new Date(1000 * 1700000000));
    expect(result!.level).toBe("INFO");
    expect(result!.loggerName).toBe("test.logger");
    expect(result!.message).toBe("Test message");
    expect(result!.exceptionTraceback).toBe("");
  });

  it("should emit multiple log records in order", () => {
    const log1: LogRecordJson = {
      time: 1700000001,
      level_name: "DEBUG",
      logger_name: "logger1",
      message: "First",
      exc_tb: "",
    };
    const log2: LogRecordJson = {
      time: 1700000002,
      level_name: "ERROR",
      logger_name: "logger2",
      message: "Second",
      exc_tb: "traceback here",
    };

    const results: LogRecord[] = [];
    service.logs$.subscribe((r) => results.push(r));
    service.onEvent("log-record", JSON.stringify(log1));
    service.onEvent("log-record", JSON.stringify(log2));
    expect(results.length).toBe(2);
    expect(results[0].message).toBe("First");
    expect(results[1].message).toBe("Second");
  });

  it("should not throw and should emit nothing on a malformed log-record event (issue #516)", () => {
    const results: LogRecord[] = [];
    service.logs$.subscribe((r) => results.push(r));

    expect(() => service.onEvent("log-record", "not json")).not.toThrow();
    expect(mockLogger.error).toHaveBeenCalled();
    expect(results.length).toBe(0);
  });

  it("should still emit a valid log-record after a malformed one (issue #516)", () => {
    const results: LogRecord[] = [];
    service.logs$.subscribe((r) => results.push(r));

    service.onEvent("log-record", "not json");
    const logJson: LogRecordJson = {
      time: 1700000000,
      level_name: "INFO",
      logger_name: "test.logger",
      message: "After malformed",
      exc_tb: "",
    };
    service.onEvent("log-record", JSON.stringify(logJson));

    expect(results.length).toBe(1);
    expect(results[0].message).toBe("After malformed");
  });
});
