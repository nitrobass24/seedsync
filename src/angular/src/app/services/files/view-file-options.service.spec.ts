import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { ViewFileOptionsService } from "./view-file-options.service";
import { LoggerService } from "../utils/logger.service";
import { ViewFileOptions, SortMethod } from "../../models/view-file-options";
import { ViewFileStatus } from "../../models/view-file";
import { StorageKeys } from "../../common/storage-keys";

describe("ViewFileOptionsService", () => {
  let service: ViewFileOptionsService;
  let store: Record<string, string> = {};

  beforeEach(() => {
    store = {};
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(
      (key: string) => store[key] ?? null,
    );
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(
      (key: string, value: string) => {
        store[key] = value;
      },
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function createService(): ViewFileOptionsService {
    TestBed.configureTestingModule({
      providers: [
        ViewFileOptionsService,
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
    return TestBed.inject(ViewFileOptionsService);
  }

  function latestOptions(): ViewFileOptions {
    let result: ViewFileOptions | undefined;
    service.options$.subscribe((o) => (result = o));
    return result!;
  }

  // --- Initialization ---

  it("should initialize with defaults when localStorage is empty", () => {
    service = createService();
    const options = latestOptions();
    expect(options.showDetails).toBe(false);
    expect(options.sortMethod).toBe(SortMethod.STATUS);
    expect(options.selectedStatusFilter).toBeNull();
    expect(options.nameFilter).toBe("");
    expect(options.pinFilter).toBe(false);
  });

  it("should initialize from localStorage values when present", () => {
    store[StorageKeys.VIEW_OPTION_SHOW_DETAILS] = JSON.stringify(true);
    store[StorageKeys.VIEW_OPTION_SORT_METHOD] = JSON.stringify(
      SortMethod.NAME_ASC,
    );
    store[StorageKeys.VIEW_OPTION_PIN] = JSON.stringify(true);

    service = createService();
    const options = latestOptions();
    expect(options.showDetails).toBe(true);
    expect(options.sortMethod).toBe(SortMethod.NAME_ASC);
    expect(options.pinFilter).toBe(true);
  });

  // --- setShowDetails ---

  it("should update showDetails and persist to localStorage", () => {
    service = createService();
    service.setShowDetails(true);

    expect(latestOptions().showDetails).toBe(true);
    expect(store[StorageKeys.VIEW_OPTION_SHOW_DETAILS]).toBe(
      JSON.stringify(true),
    );
  });

  it("should not emit when setShowDetails is called with the same value", () => {
    service = createService();
    let emitCount = 0;
    service.options$.subscribe(() => emitCount++);

    const countAfterInit = emitCount;
    service.setShowDetails(false); // already false
    expect(emitCount).toBe(countAfterInit);
  });

  // --- setSortMethod ---

  it("should update sortMethod and persist to localStorage", () => {
    service = createService();
    service.setSortMethod(SortMethod.NAME_DESC);

    expect(latestOptions().sortMethod).toBe(SortMethod.NAME_DESC);
    expect(store[StorageKeys.VIEW_OPTION_SORT_METHOD]).toBe(
      JSON.stringify(SortMethod.NAME_DESC),
    );
  });

  it("should not emit when setSortMethod is called with the same value", () => {
    service = createService();
    let emitCount = 0;
    service.options$.subscribe(() => emitCount++);

    const countAfterInit = emitCount;
    service.setSortMethod(SortMethod.STATUS); // already STATUS
    expect(emitCount).toBe(countAfterInit);
  });

  // --- setSelectedStatusFilter ---

  it("should update selectedStatusFilter", () => {
    service = createService();
    service.setSelectedStatusFilter(ViewFileStatus.DOWNLOADING);

    expect(latestOptions().selectedStatusFilter).toBe(
      ViewFileStatus.DOWNLOADING,
    );
  });

  it("should clear selectedStatusFilter when set to null", () => {
    service = createService();
    service.setSelectedStatusFilter(ViewFileStatus.QUEUED);
    service.setSelectedStatusFilter(null);

    expect(latestOptions().selectedStatusFilter).toBeNull();
  });

  // --- setNameFilter ---

  it("should update nameFilter", () => {
    service = createService();
    service.setNameFilter("test");

    expect(latestOptions().nameFilter).toBe("test");
  });

  it("should not emit when setNameFilter is called with the same value", () => {
    service = createService();
    let emitCount = 0;
    service.options$.subscribe(() => emitCount++);

    const countAfterInit = emitCount;
    service.setNameFilter(""); // already empty
    expect(emitCount).toBe(countAfterInit);
  });

  // --- setPinFilter ---

  it("should update pinFilter and persist to localStorage", () => {
    service = createService();
    service.setPinFilter(true);

    expect(latestOptions().pinFilter).toBe(true);
    expect(store[StorageKeys.VIEW_OPTION_PIN]).toBe(JSON.stringify(true));
  });

  it("should not emit when setPinFilter is called with the same value", () => {
    service = createService();
    let emitCount = 0;
    service.options$.subscribe(() => emitCount++);

    const countAfterInit = emitCount;
    service.setPinFilter(false); // already false
    expect(emitCount).toBe(countAfterInit);
  });
});
