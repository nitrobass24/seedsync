import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { BehaviorSubject } from "rxjs";
import { ViewFileSortService } from "./view-file-sort.service";
import { ViewFileOptionsService } from "./view-file-options.service";
import { ViewFileService, ViewFileComparator } from "./view-file.service";
import { LoggerService } from "../utils/logger.service";
import { ViewFileOptions, SortMethod } from "../../models/view-file-options";
import { ViewFile, ViewFileStatus } from "../../models/view-file";

function makeViewFile(
  overrides: Partial<ViewFile> & { name: string },
): ViewFile {
  return {
    pairId: null,
    pairName: null,
    isDir: false,
    localSize: 0,
    remoteSize: 0,
    percentDownloaded: 0,
    status: ViewFileStatus.DEFAULT,
    downloadingSpeed: 0,
    eta: 0,
    fullPath: "/path/" + overrides.name,
    isArchive: false,
    isSelected: false,
    isChecked: false,
    isQueueable: false,
    isStoppable: false,
    isExtractable: false,
    isLocallyDeletable: false,
    isRemotelyDeletable: false,
    isValidatable: false,
    validateTooltip: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
    ...overrides,
  };
}

function defaultOptions(): ViewFileOptions {
  return {
    showDetails: false,
    sortMethod: SortMethod.STATUS,
    selectedStatusFilter: null,
    nameFilter: "",
    pinFilter: false,
  };
}

describe("ViewFileSortService", () => {
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let capturedComparator: ViewFileComparator | null;
  let mockViewFileService: { setComparator: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    optionsSubject = new BehaviorSubject<ViewFileOptions>(defaultOptions());
    capturedComparator = null;
    mockViewFileService = {
      setComparator: vi.fn((c: ViewFileComparator | null) => {
        capturedComparator = c;
      }),
    };

    TestBed.configureTestingModule({
      providers: [
        ViewFileSortService,
        {
          provide: ViewFileOptionsService,
          useValue: { options$: optionsSubject.asObservable() },
        },
        {
          provide: ViewFileService,
          useValue: mockViewFileService,
        },
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

    // Instantiate the service so the constructor subscription fires
    TestBed.inject(ViewFileSortService);
  });

  function setSort(method: SortMethod): void {
    optionsSubject.next({ ...defaultOptions(), sortMethod: method });
  }

  function sortFiles(files: ViewFile[]): ViewFile[] {
    return [...files].sort(capturedComparator!);
  }

  // --- Comparator selection ---

  it("should set Status comparator on init", () => {
    expect(mockViewFileService.setComparator).toHaveBeenCalled();
    expect(capturedComparator).not.toBeNull();
  });

  it("should set Size Asc comparator when SIZE_ASC selected", () => {
    setSort(SortMethod.SIZE_ASC);
    expect(capturedComparator).not.toBeNull();
  });

  it("should set Size Desc comparator when SIZE_DESC selected", () => {
    setSort(SortMethod.SIZE_DESC);
    expect(capturedComparator).not.toBeNull();
  });

  // --- Size Ascending ---

  describe("Size Ascending", () => {
    beforeEach(() => setSort(SortMethod.SIZE_ASC));

    it("should sort smaller files first", () => {
      const files = [
        makeViewFile({ name: "big", remoteSize: 1000 }),
        makeViewFile({ name: "small", remoteSize: 100 }),
        makeViewFile({ name: "medium", remoteSize: 500 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["small", "medium", "big"]);
    });

    it("should fall back to localSize when remoteSize is 0", () => {
      const files = [
        makeViewFile({ name: "remote", remoteSize: 200 }),
        makeViewFile({ name: "local-only", remoteSize: 0, localSize: 100 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["local-only", "remote"]);
    });

    it("should sort null sizes (both 0) last", () => {
      const files = [
        makeViewFile({ name: "no-size", remoteSize: 0, localSize: 0 }),
        makeViewFile({ name: "has-size", remoteSize: 50 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["has-size", "no-size"]);
    });

    it("should sort by name when sizes are equal", () => {
      const files = [
        makeViewFile({ name: "beta", remoteSize: 100 }),
        makeViewFile({ name: "alpha", remoteSize: 100 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["alpha", "beta"]);
    });

    it("should sort multiple null-size files by name", () => {
      const files = [
        makeViewFile({ name: "zebra", remoteSize: 0, localSize: 0 }),
        makeViewFile({ name: "apple", remoteSize: 0, localSize: 0 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["apple", "zebra"]);
    });
  });

  // --- Size Descending ---

  describe("Size Descending", () => {
    beforeEach(() => setSort(SortMethod.SIZE_DESC));

    it("should sort larger files first", () => {
      const files = [
        makeViewFile({ name: "small", remoteSize: 100 }),
        makeViewFile({ name: "big", remoteSize: 1000 }),
        makeViewFile({ name: "medium", remoteSize: 500 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["big", "medium", "small"]);
    });

    it("should fall back to localSize when remoteSize is 0", () => {
      const files = [
        makeViewFile({ name: "local-only", remoteSize: 0, localSize: 300 }),
        makeViewFile({ name: "remote", remoteSize: 200 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["local-only", "remote"]);
    });

    it("should sort null sizes (both 0) last", () => {
      const files = [
        makeViewFile({ name: "no-size", remoteSize: 0, localSize: 0 }),
        makeViewFile({ name: "has-size", remoteSize: 50 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["has-size", "no-size"]);
    });

    it("should sort by name when sizes are equal", () => {
      const files = [
        makeViewFile({ name: "beta", remoteSize: 100 }),
        makeViewFile({ name: "alpha", remoteSize: 100 }),
      ];
      const sorted = sortFiles(files);
      expect(sorted.map((f) => f.name)).toEqual(["alpha", "beta"]);
    });
  });
});
