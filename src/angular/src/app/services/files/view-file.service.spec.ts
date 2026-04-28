import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { BehaviorSubject, of } from "rxjs";
import { ViewFileService, ViewFileFilterCriteria } from "./view-file.service";
import { ModelFileService } from "./model-file.service";
import { PathPairsService } from "../settings/path-pairs.service";
import { LoggerService } from "../utils/logger.service";
import { ModelFile, ModelFileState } from "../../models/model-file";
import { PathPair } from "../../models/path-pair";
import { ViewFile, ViewFileStatus } from "../../models/view-file";
import { WebReaction } from "../utils/rest.service";
import { fileKey } from "./file-key";

function makeModelFile(
  overrides: Partial<ModelFile> & { name: string },
): ModelFile {
  return {
    pair_id: null,
    is_dir: false,
    local_size: 0,
    remote_size: 0,
    state: ModelFileState.DEFAULT,
    downloading_speed: 0,
    eta: 0,
    full_path: "/path/" + overrides.name,
    is_extractable: false,
    local_created_timestamp: null,
    local_modified_timestamp: null,
    remote_created_timestamp: null,
    remote_modified_timestamp: null,
    children: [],
    ...overrides,
  };
}

describe("ViewFileService", () => {
  let service: ViewFileService;
  let modelFilesSubject: BehaviorSubject<Map<string, ModelFile>>;
  let pairsSubject: BehaviorSubject<PathPair[]>;
  let mockModelFileService: {
    files$: ReturnType<BehaviorSubject<Map<string, ModelFile>>["asObservable"]>;
    queue: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    extract: ReturnType<typeof vi.fn>;
    deleteLocal: ReturnType<typeof vi.fn>;
    deleteRemote: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    modelFilesSubject = new BehaviorSubject<Map<string, ModelFile>>(new Map());
    pairsSubject = new BehaviorSubject<PathPair[]>([]);
    mockModelFileService = {
      files$: modelFilesSubject.asObservable(),
      queue: vi.fn(),
      stop: vi.fn(),
      extract: vi.fn(),
      deleteLocal: vi.fn(),
      deleteRemote: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        ViewFileService,
        { provide: ModelFileService, useValue: mockModelFileService },
        { provide: PathPairsService, useValue: { pairs$: pairsSubject.asObservable() } },
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
    service = TestBed.inject(ViewFileService);
  });

  function latestFiles(): ViewFile[] {
    let result: ViewFile[] = [];
    service.files$.subscribe((f) => (result = f));
    return result;
  }

  function latestFilteredFiles(): ViewFile[] {
    let result: ViewFile[] = [];
    service.filteredFiles$.subscribe((f) => (result = f));
    return result;
  }

  function emitModelFiles(files: ModelFile[]): void {
    const map = new Map<string, ModelFile>();
    for (const f of files) {
      const key = fileKey(f.pair_id, f.name);
      map.set(key, f);
    }
    modelFilesSubject.next(map);
  }

  // --- Status mapping ---

  it("should map DEFAULT state with local_size > 0 and remote_size > 0 to STOPPED", () => {
    emitModelFiles([
      makeModelFile({
        name: "partial",
        local_size: 50,
        remote_size: 200,
        state: ModelFileState.DEFAULT,
      }),
    ]);

    const files = latestFiles();
    expect(files.length).toBe(1);
    expect(files[0].status).toBe(ViewFileStatus.STOPPED);
  });

  it("should map DEFAULT state with local_size = 0 to DEFAULT", () => {
    emitModelFiles([
      makeModelFile({
        name: "empty",
        local_size: 0,
        remote_size: 200,
        state: ModelFileState.DEFAULT,
      }),
    ]);

    expect(latestFiles()[0].status).toBe(ViewFileStatus.DEFAULT);
  });

  it("should map QUEUED state to QUEUED status", () => {
    emitModelFiles([
      makeModelFile({ name: "q", state: ModelFileState.QUEUED }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.QUEUED);
  });

  it("should map DOWNLOADING state to DOWNLOADING status", () => {
    emitModelFiles([
      makeModelFile({ name: "dl", state: ModelFileState.DOWNLOADING }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.DOWNLOADING);
  });

  it("should map DOWNLOADED state to DOWNLOADED status", () => {
    emitModelFiles([
      makeModelFile({ name: "done", state: ModelFileState.DOWNLOADED }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.DOWNLOADED);
  });

  it("should map DELETED state to DELETED status", () => {
    emitModelFiles([
      makeModelFile({ name: "del", state: ModelFileState.DELETED }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.DELETED);
  });

  it("should map EXTRACTING state to EXTRACTING status", () => {
    emitModelFiles([
      makeModelFile({ name: "ext", state: ModelFileState.EXTRACTING }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.EXTRACTING);
  });

  it("should map EXTRACTED state to EXTRACTED status", () => {
    emitModelFiles([
      makeModelFile({ name: "exd", state: ModelFileState.EXTRACTED }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.EXTRACTED);
  });

  // --- Percent downloaded ---

  it("should set percentDownloaded to 100 when remoteSize is 0", () => {
    emitModelFiles([
      makeModelFile({ name: "noremote", local_size: 50, remote_size: 0 }),
    ]);
    expect(latestFiles()[0].percentDownloaded).toBe(100);
  });

  it("should calculate percentDownloaded as truncated integer", () => {
    emitModelFiles([
      makeModelFile({ name: "partial", local_size: 50, remote_size: 200 }),
    ]);
    expect(latestFiles()[0].percentDownloaded).toBe(25);
  });

  it("should truncate percentDownloaded (not round)", () => {
    emitModelFiles([
      makeModelFile({ name: "trunc", local_size: 1, remote_size: 3 }),
    ]);
    // 100 * 1 / 3 = 33.33... → truncated to 33
    expect(latestFiles()[0].percentDownloaded).toBe(33);
  });

  // --- Action flags ---

  it("should set isQueueable for STOPPED status with remoteSize > 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "stopped",
        local_size: 50,
        remote_size: 200,
        state: ModelFileState.DEFAULT,
      }),
    ]);

    const file = latestFiles()[0];
    expect(file.status).toBe(ViewFileStatus.STOPPED);
    expect(file.isQueueable).toBe(true);
    expect(file.isStoppable).toBe(false);
  });

  it("should set isStoppable for DOWNLOADING status", () => {
    emitModelFiles([
      makeModelFile({ name: "dl", state: ModelFileState.DOWNLOADING }),
    ]);

    const file = latestFiles()[0];
    expect(file.isStoppable).toBe(true);
    expect(file.isQueueable).toBe(false);
  });

  it("should set isStoppable for QUEUED status", () => {
    emitModelFiles([
      makeModelFile({ name: "q", state: ModelFileState.QUEUED }),
    ]);
    expect(latestFiles()[0].isStoppable).toBe(true);
  });

  it("should set isExtractable when status allows and localSize > 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "downloaded",
        local_size: 100,
        remote_size: 100,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isExtractable).toBe(true);
  });

  it("should not set isExtractable when localSize is 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "remote-only",
        local_size: 0,
        remote_size: 100,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isExtractable).toBe(false);
  });

  it("should set isLocallyDeletable when status allows and localSize > 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "local",
        local_size: 100,
        remote_size: 100,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isLocallyDeletable).toBe(true);
  });

  it("should set isRemotelyDeletable when status allows and remoteSize > 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "remote",
        local_size: 0,
        remote_size: 100,
        state: ModelFileState.DEFAULT,
      }),
    ]);
    expect(latestFiles()[0].isRemotelyDeletable).toBe(true);
  });

  it("should set isRemotelyDeletable for DELETED status with remoteSize > 0", () => {
    emitModelFiles([
      makeModelFile({
        name: "del",
        remote_size: 100,
        state: ModelFileState.DELETED,
      }),
    ]);
    expect(latestFiles()[0].isRemotelyDeletable).toBe(true);
  });

  // --- isValidatable and validateTooltip ---

  it("should set isValidatable when status allows and both sizes are non-null", () => {
    emitModelFiles([
      makeModelFile({
        name: "valid",
        local_size: 100,
        remote_size: 100,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  it("should not set isValidatable when remote_size is null and show tooltip", () => {
    emitModelFiles([
      makeModelFile({
        name: "no-remote",
        local_size: 100,
        remote_size: null,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBe("Remote file not available for checksum comparison");
  });

  it("should not set isValidatable when local_size is null", () => {
    emitModelFiles([
      makeModelFile({
        name: "no-local",
        local_size: null,
        remote_size: 100,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  it("should not set isValidatable for non-validatable status", () => {
    emitModelFiles([
      makeModelFile({
        name: "queued",
        local_size: 100,
        remote_size: 100,
        state: ModelFileState.QUEUED,
      }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  // --- Filter criteria ---

  it("should apply filter criteria to filteredFiles$", () => {
    emitModelFiles([
      makeModelFile({
        name: "alpha",
        remote_size: 100,
        state: ModelFileState.QUEUED,
      }),
      makeModelFile({
        name: "beta",
        remote_size: 200,
        state: ModelFileState.DOWNLOADED,
      }),
    ]);

    const criteria: ViewFileFilterCriteria = {
      meetsCriteria: (vf: ViewFile) => vf.status === ViewFileStatus.QUEUED,
    };
    service.setFilterCriteria(criteria);

    const filtered = latestFilteredFiles();
    expect(filtered.length).toBe(1);
    expect(filtered[0].name).toBe("alpha");
  });

  it("should show all files when filter criteria is null", () => {
    emitModelFiles([
      makeModelFile({ name: "a", remote_size: 100 }),
      makeModelFile({ name: "b", remote_size: 200 }),
    ]);

    service.setFilterCriteria(null);

    expect(latestFilteredFiles().length).toBe(2);
  });

  // --- Comparator / sorting ---

  it("should sort files when comparator is set", () => {
    emitModelFiles([
      makeModelFile({ name: "banana", remote_size: 100 }),
      makeModelFile({ name: "apple", remote_size: 200 }),
    ]);

    service.setComparator((a, b) => a.name.localeCompare(b.name));

    const files = latestFiles();
    expect(files[0].name).toBe("apple");
    expect(files[1].name).toBe("banana");
  });

  // --- Selection ---

  it("should select a file via setSelected", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", remote_size: 100 }),
      makeModelFile({ name: "file2", remote_size: 200 }),
    ]);

    const target = latestFiles().find((f) => f.name === "file1")!;
    service.setSelected(target);

    const files = latestFiles();
    const selected = files.find((f) => f.name === "file1")!;
    expect(selected.isSelected).toBe(true);
    expect(files.find((f) => f.name === "file2")!.isSelected).toBe(false);
  });

  it("should unselect all files via unsetSelected", () => {
    emitModelFiles([makeModelFile({ name: "file1", remote_size: 100 })]);

    const target = latestFiles()[0];
    service.setSelected(target);
    expect(latestFiles()[0].isSelected).toBe(true);

    service.unsetSelected();
    expect(latestFiles()[0].isSelected).toBe(false);
  });

  it("should deselect previous file when selecting a different one", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", remote_size: 100 }),
      makeModelFile({ name: "file2", remote_size: 200 }),
    ]);

    service.setSelected(latestFiles().find((f) => f.name === "file1")!);
    service.setSelected(latestFiles().find((f) => f.name === "file2")!);

    const files = latestFiles();
    expect(files.find((f) => f.name === "file1")!.isSelected).toBe(false);
    expect(files.find((f) => f.name === "file2")!.isSelected).toBe(true);
  });

  // --- Add / update / remove diffs ---

  it("should grow files$ when a new file is added to the model", () => {
    emitModelFiles([makeModelFile({ name: "existing", remote_size: 100 })]);
    expect(latestFiles().length).toBe(1);

    emitModelFiles([
      makeModelFile({ name: "existing", remote_size: 100 }),
      makeModelFile({ name: "newfile", remote_size: 200 }),
    ]);
    expect(latestFiles().length).toBe(2);
    expect(latestFiles().find((f) => f.name === "newfile")).toBeDefined();
  });

  it("should shrink files$ when a file is removed from the model", () => {
    emitModelFiles([
      makeModelFile({ name: "keep", remote_size: 100 }),
      makeModelFile({ name: "remove", remote_size: 200 }),
    ]);
    expect(latestFiles().length).toBe(2);

    emitModelFiles([makeModelFile({ name: "keep", remote_size: 100 })]);
    expect(latestFiles().length).toBe(1);
    expect(latestFiles()[0].name).toBe("keep");
  });

  it("should update a file in-place when model file changes", () => {
    emitModelFiles([
      makeModelFile({
        name: "file1",
        local_size: 0,
        remote_size: 200,
        state: ModelFileState.DEFAULT,
      }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.DEFAULT);

    emitModelFiles([
      makeModelFile({
        name: "file1",
        local_size: 100,
        remote_size: 200,
        state: ModelFileState.DOWNLOADING,
      }),
    ]);
    expect(latestFiles()[0].status).toBe(ViewFileStatus.DOWNLOADING);
    expect(latestFiles()[0].percentDownloaded).toBe(50);
  });

  // --- Action delegation ---

  it("should delegate queue() to ModelFileService", () => {
    const mf = makeModelFile({ name: "file1", remote_size: 100 });
    emitModelFiles([mf]);
    mockModelFileService.queue.mockReturnValue(
      of({ success: true, data: null, errorMessage: null }),
    );

    const vf = latestFiles()[0];
    let result: WebReaction | undefined;
    service.queue(vf).subscribe((r) => (result = r));

    expect(mockModelFileService.queue).toHaveBeenCalledWith(mf);
    expect(result!.success).toBe(true);
  });

  it("should return error reaction when file not found for queue()", () => {
    emitModelFiles([]);

    const fakeVf = {
      name: "nonexistent",
    } as ViewFile;
    let result: WebReaction | undefined;
    service.queue(fakeVf).subscribe((r) => (result = r));

    expect(result!.success).toBe(false);
  });

  // --- Composite key (pair_id:name) ---

  it("should distinguish two files with the same name but different pair_id values", () => {
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200 }),
    ]);

    const files = latestFiles();
    expect(files.length).toBe(2);
    expect(files.find((f) => f.pairId === "pair-a")).toBeDefined();
    expect(files.find((f) => f.pairId === "pair-b")).toBeDefined();
  });

  it("should select the correct file when same-name files have different pair_ids", () => {
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200 }),
    ]);

    const targetB = latestFiles().find((f) => f.pairId === "pair-b")!;
    service.setSelected(targetB);

    const files = latestFiles();
    expect(files.find((f) => f.pairId === "pair-a")!.isSelected).toBe(false);
    expect(files.find((f) => f.pairId === "pair-b")!.isSelected).toBe(true);
  });

  it("should check the correct file when same-name files have different pair_ids", () => {
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100, state: ModelFileState.DOWNLOADED, local_size: 100 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200, state: ModelFileState.DOWNLOADED, local_size: 200 }),
    ]);

    const targetA = latestFiles().find((f) => f.pairId === "pair-a")!;
    service.toggleCheck(targetA);

    const files = latestFiles();
    expect(files.find((f) => f.pairId === "pair-a")!.isChecked).toBe(true);
    expect(files.find((f) => f.pairId === "pair-b")!.isChecked).toBe(false);
  });

  it("should delegate queue() to the correct model file when same-name files have different pair_ids", () => {
    const mfA = makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100 });
    const mfB = makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200 });
    emitModelFiles([mfA, mfB]);
    mockModelFileService.queue.mockReturnValue(
      of({ success: true, data: null, errorMessage: null }),
    );

    const vfB = latestFiles().find((f) => f.pairId === "pair-b")!;
    service.queue(vfB).subscribe();

    expect(mockModelFileService.queue).toHaveBeenCalledWith(mfB);
    expect(mockModelFileService.queue).not.toHaveBeenCalledWith(mfA);
  });

  it("should remove the correct file when same-name files have different pair_ids", () => {
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200 }),
    ]);
    expect(latestFiles().length).toBe(2);

    // Remove pair-a, keep pair-b
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200 }),
    ]);

    const files = latestFiles();
    expect(files.length).toBe(1);
    expect(files[0].pairId).toBe("pair-b");
  });

  // --- Pair name resolution ---

  it("should set pairName to null when pair_id is null", () => {
    pairsSubject.next([{ id: "pair-a", name: "Seedbox", remote_path: "/r", local_path: "/l", enabled: true, auto_queue: false, arr_target_ids: [] }]);
    emitModelFiles([makeModelFile({ name: "file1", pair_id: null, remote_size: 100 })]);

    expect(latestFiles()[0].pairName).toBeNull();
  });

  it("should resolve pairName from PathPairsService when pair_id matches", () => {
    pairsSubject.next([
      { id: "pair-a", name: "Seedbox", remote_path: "/r", local_path: "/l", enabled: true, auto_queue: false, arr_target_ids: [] },
      { id: "pair-b", name: "Media", remote_path: "/r2", local_path: "/l2", enabled: true, auto_queue: false, arr_target_ids: [] },
    ]);
    emitModelFiles([
      makeModelFile({ name: "file1", pair_id: "pair-a", remote_size: 100 }),
      makeModelFile({ name: "file2", pair_id: "pair-b", remote_size: 200 }),
    ]);

    const files = latestFiles();
    expect(files.find((f) => f.pairId === "pair-a")!.pairName).toBe("Seedbox");
    expect(files.find((f) => f.pairId === "pair-b")!.pairName).toBe("Media");
  });

  it("should set pairName to null when pair_id does not match any known pair", () => {
    pairsSubject.next([{ id: "pair-a", name: "Seedbox", remote_path: "/r", local_path: "/l", enabled: true, auto_queue: false, arr_target_ids: [] }]);
    emitModelFiles([makeModelFile({ name: "file1", pair_id: "pair-unknown", remote_size: 100 })]);

    expect(latestFiles()[0].pairName).toBeNull();
  });

  it("should update pairName immediately when pairs$ emits after model files", () => {
    // Pairs not yet known
    pairsSubject.next([]);
    emitModelFiles([makeModelFile({ name: "file1", pair_id: "pair-a", remote_size: 100 })]);
    expect(latestFiles()[0].pairName).toBeNull();

    // Pairs arrive — view should rebuild automatically without new model file emission
    pairsSubject.next([{ id: "pair-a", name: "Seedbox", remote_path: "/r", local_path: "/l", enabled: true, auto_queue: false, arr_target_ids: [] }]);
    expect(latestFiles()[0].pairName).toBe("Seedbox");
  });

  // --- Validation / isValidatable / validateTooltip ---

  it("should set isValidatable true when downloaded file has both local and remote sizes", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.DOWNLOADED, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  it("should set isValidatable false when remote_size is null", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.DOWNLOADED, local_size: 100, remote_size: null }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBe("Remote file not available for checksum comparison");
  });

  it("should set isValidatable false when local_size is null", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.DOWNLOADED, local_size: null, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  it("should set isValidatable false when both sizes are null", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.DOWNLOADED, local_size: null, remote_size: null }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBe("Remote file not available for checksum comparison");
  });

  it("should not set isValidatable for non-validatable states even with sizes present", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.DEFAULT, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(false);
    expect(latestFiles()[0].validateTooltip).toBeNull();
  });

  it("should set isValidatable true for EXTRACTED state with sizes present", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.EXTRACTED, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
  });

  it("should set isValidatable true for EXTRACT_FAILED state with sizes present", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.EXTRACT_FAILED, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
  });

  it("should set isValidatable true for VALIDATED state with sizes present", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.VALIDATED, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
  });

  it("should set isValidatable true for CORRUPT state allowing re-validation", () => {
    emitModelFiles([
      makeModelFile({ name: "file1", state: ModelFileState.CORRUPT, local_size: 100, remote_size: 100 }),
    ]);
    expect(latestFiles()[0].isValidatable).toBe(true);
  });

  it("should update the correct file when same-name files have different pair_ids", () => {
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100, state: ModelFileState.DEFAULT, local_size: 0 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200, state: ModelFileState.DEFAULT, local_size: 0 }),
    ]);

    // Update only pair-a to DOWNLOADING
    emitModelFiles([
      makeModelFile({ name: "movie.mkv", pair_id: "pair-a", remote_size: 100, state: ModelFileState.DOWNLOADING, local_size: 50 }),
      makeModelFile({ name: "movie.mkv", pair_id: "pair-b", remote_size: 200, state: ModelFileState.DEFAULT, local_size: 0 }),
    ]);

    const files = latestFiles();
    expect(files.find((f) => f.pairId === "pair-a")!.status).toBe(ViewFileStatus.DOWNLOADING);
    expect(files.find((f) => f.pairId === "pair-b")!.status).toBe(ViewFileStatus.DEFAULT);
  });
});
