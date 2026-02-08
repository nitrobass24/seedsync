import { describe, it, expect, vi, beforeEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { of } from "rxjs";
import { ModelFileService } from "./model-file.service";
import { StreamDispatchService } from "../base/stream-dispatch.service";
import { LoggerService } from "../utils/logger.service";
import { RestService } from "../utils/rest.service";
import { ModelFile } from "../../models/model-file";

function makeFileJson(name: string, state = "DEFAULT") {
  return {
    name,
    is_dir: false,
    local_size: 100,
    remote_size: 200,
    state,
    downloading_speed: 0,
    eta: 0,
    full_path: "/path/" + name,
    is_extractable: false,
    local_created_timestamp: null,
    local_modified_timestamp: null,
    remote_created_timestamp: null,
    remote_modified_timestamp: null,
    children: [],
  };
}

describe("ModelFileService", () => {
  let service: ModelFileService;
  let mockStreamDispatch: { registerHandler: ReturnType<typeof vi.fn> };
  let mockRestService: { sendRequest: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockStreamDispatch = { registerHandler: vi.fn() };
    mockRestService = { sendRequest: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        ModelFileService,
        { provide: StreamDispatchService, useValue: mockStreamDispatch },
        {
          provide: LoggerService,
          useValue: {
            debug: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
            warn: vi.fn(),
          },
        },
        { provide: RestService, useValue: mockRestService },
      ],
    });
    service = TestBed.inject(ModelFileService);
  });

  it("should register with StreamDispatchService on construction", () => {
    expect(mockStreamDispatch.registerHandler).toHaveBeenCalledWith(service);
  });

  it("should return 4 event names", () => {
    expect(service.getEventNames()).toEqual([
      "model-init",
      "model-added",
      "model-updated",
      "model-removed",
    ]);
  });

  it("should replace all files on model-init event", () => {
    const data = JSON.stringify([makeFileJson("file1"), makeFileJson("file2")]);
    service.onEvent("model-init", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(2);
    expect(result!.has("file1")).toBe(true);
    expect(result!.has("file2")).toBe(true);
  });

  it("should add a file on model-added event", () => {
    // Initialize with one file
    service.onEvent("model-init", JSON.stringify([makeFileJson("existing")]));

    // Add a new file
    const data = JSON.stringify({ new_file: makeFileJson("new_file") });
    service.onEvent("model-added", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(2);
    expect(result!.has("new_file")).toBe(true);
  });

  it("should not add a file if it already exists", () => {
    service.onEvent("model-init", JSON.stringify([makeFileJson("file1")]));

    const data = JSON.stringify({ new_file: makeFileJson("file1") });
    service.onEvent("model-added", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(1);
  });

  it("should update an existing file on model-updated event", () => {
    service.onEvent(
      "model-init",
      JSON.stringify([makeFileJson("file1", "DEFAULT")]),
    );

    const data = JSON.stringify({
      new_file: makeFileJson("file1", "DOWNLOADING"),
    });
    service.onEvent("model-updated", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.get("file1")!.state).toBe("downloading");
  });

  it("should not update a file that does not exist", () => {
    service.onEvent("model-init", JSON.stringify([makeFileJson("file1")]));

    const data = JSON.stringify({
      new_file: makeFileJson("nonexistent", "DOWNLOADING"),
    });
    service.onEvent("model-updated", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(1);
    expect(result!.has("nonexistent")).toBe(false);
  });

  it("should remove a file on model-removed event", () => {
    service.onEvent(
      "model-init",
      JSON.stringify([makeFileJson("file1"), makeFileJson("file2")]),
    );

    const data = JSON.stringify({ old_file: makeFileJson("file1") });
    service.onEvent("model-removed", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(1);
    expect(result!.has("file1")).toBe(false);
    expect(result!.has("file2")).toBe(true);
  });

  it("should not remove a file that does not exist", () => {
    service.onEvent("model-init", JSON.stringify([makeFileJson("file1")]));

    const data = JSON.stringify({ old_file: makeFileJson("nonexistent") });
    service.onEvent("model-removed", data);

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(1);
  });

  it("should clear all files on disconnect", () => {
    service.onEvent(
      "model-init",
      JSON.stringify([makeFileJson("file1"), makeFileJson("file2")]),
    );
    service.onDisconnected();

    let result: Map<string, ModelFile> | undefined;
    service.files$.subscribe((f) => (result = f));
    expect(result!.size).toBe(0);
  });

  it("should call RestService.sendRequest with double-encoded filename for queue", () => {
    mockRestService.sendRequest.mockReturnValue(of({}));
    const file = { name: "my file/test" } as ModelFile;
    service.queue(file);

    const encoded = encodeURIComponent(encodeURIComponent("my file/test"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/command/queue/" + encoded,
    );
  });

  it("should call RestService.sendRequest with double-encoded filename for stop", () => {
    mockRestService.sendRequest.mockReturnValue(of({}));
    const file = { name: "my file/test" } as ModelFile;
    service.stop(file);

    const encoded = encodeURIComponent(encodeURIComponent("my file/test"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/command/stop/" + encoded,
    );
  });

  it("should call RestService.sendRequest with double-encoded filename for extract", () => {
    mockRestService.sendRequest.mockReturnValue(of({}));
    const file = { name: "my file/test" } as ModelFile;
    service.extract(file);

    const encoded = encodeURIComponent(encodeURIComponent("my file/test"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/command/extract/" + encoded,
    );
  });

  it("should call RestService.sendRequest with double-encoded filename for deleteLocal", () => {
    mockRestService.sendRequest.mockReturnValue(of({}));
    const file = { name: "my file/test" } as ModelFile;
    service.deleteLocal(file);

    const encoded = encodeURIComponent(encodeURIComponent("my file/test"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/command/delete_local/" + encoded,
    );
  });

  it("should call RestService.sendRequest with double-encoded filename for deleteRemote", () => {
    mockRestService.sendRequest.mockReturnValue(of({}));
    const file = { name: "my file/test" } as ModelFile;
    service.deleteRemote(file);

    const encoded = encodeURIComponent(encodeURIComponent("my file/test"));
    expect(mockRestService.sendRequest).toHaveBeenCalledWith(
      "/server/command/delete_remote/" + encoded,
    );
  });
});
