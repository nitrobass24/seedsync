import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { LogService } from "./log.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { LogRecord, LogRecordJson } from "../../models/log-record";

describe("LogService", () => {
  let service: LogService;
  let mockStreamDispatch: { registerHandler: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockStreamDispatch = { registerHandler: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        LogService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
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
    service.onEvent("log-record", JSON.stringify(logJson));

    let result: LogRecord | undefined;
    service.logs$.subscribe((r) => (result = r));
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
    service.onEvent("log-record", JSON.stringify(log1));
    service.onEvent("log-record", JSON.stringify(log2));

    const results: LogRecord[] = [];
    service.logs$.subscribe((r) => results.push(r));
    expect(results.length).toBe(2);
    expect(results[0].message).toBe("First");
    expect(results[1].message).toBe("Second");
  });
});
