import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { ViewFileCommandService, ModelFileResolver } from './view-file-command.service';
import { ModelFileService } from './model-file.service';
import { ViewFileSelectionService } from './view-file-selection.service';
import { LoggerService } from '../utils/logger.service';
import { ModelFile, ModelFileState } from '../../models/model-file';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { WebReaction } from '../utils/rest.service';
import { fileKey } from './file-key';

function makeModelFile(overrides: Partial<ModelFile> & { name: string }): ModelFile {
  return {
    pair_id: null,
    is_dir: false,
    local_size: 0,
    remote_size: 0,
    state: ModelFileState.DEFAULT,
    downloading_speed: 0,
    eta: 0,
    full_path: '/path/' + overrides.name,
    is_extractable: false,
    local_created_timestamp: null,
    local_modified_timestamp: null,
    remote_created_timestamp: null,
    remote_modified_timestamp: null,
    ...overrides,
  };
}

function makeViewFile(overrides: Partial<ViewFile> & { name: string }): ViewFile {
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
    fullPath: '/path/' + overrides.name,
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

const OK: WebReaction = { success: true, data: null, errorMessage: null };

describe('ViewFileCommandService', () => {
  let service: ViewFileCommandService;
  let selection: ViewFileSelectionService;
  let mockModelFileService: {
    queue: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    extract: ReturnType<typeof vi.fn>;
    deleteLocal: ReturnType<typeof vi.fn>;
    deleteRemote: ReturnType<typeof vi.fn>;
    validate: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    mockModelFileService = {
      queue: vi.fn().mockReturnValue(of(OK)),
      stop: vi.fn().mockReturnValue(of(OK)),
      extract: vi.fn().mockReturnValue(of(OK)),
      deleteLocal: vi.fn().mockReturnValue(of(OK)),
      deleteRemote: vi.fn().mockReturnValue(of(OK)),
      validate: vi.fn().mockReturnValue(of(OK)),
    };
    TestBed.configureTestingModule({
      providers: [
        ViewFileCommandService,
        ViewFileSelectionService,
        { provide: ModelFileService, useValue: mockModelFileService },
        {
          provide: LoggerService,
          useValue: { debug: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() },
        },
      ],
    });
    service = TestBed.inject(ViewFileCommandService);
    selection = TestBed.inject(ViewFileSelectionService);
  });

  /** A resolver backed by a Map, mirroring ViewFileService's prevModelFiles. */
  function resolverFor(models: ModelFile[]): ModelFileResolver {
    const map = new Map<string, ModelFile>();
    for (const m of models) {
      map.set(fileKey(m.pair_id, m.name), m);
    }
    return (key) => map.get(key);
  }

  // --- single dispatch: resolves ViewFile -> ModelFile ---

  it('queue() resolves the ViewFile to its ModelFile and dispatches it', () => {
    const mf = makeModelFile({ name: 'file1', remote_size: 100 });
    const vf = makeViewFile({ name: 'file1', remoteSize: 100 });

    let result: WebReaction | undefined;
    service.queue(vf, resolverFor([mf])).subscribe((r) => (result = r));

    expect(mockModelFileService.queue).toHaveBeenCalledWith(mf);
    expect(result).toEqual(OK);
  });

  it('queue() resolves the correct ModelFile when same-name files differ by pairId', () => {
    const mfA = makeModelFile({ name: 'movie.mkv', pair_id: 'pair-a', remote_size: 100 });
    const mfB = makeModelFile({ name: 'movie.mkv', pair_id: 'pair-b', remote_size: 200 });
    const vfB = makeViewFile({ name: 'movie.mkv', pairId: 'pair-b', remoteSize: 200 });

    service.queue(vfB, resolverFor([mfA, mfB])).subscribe();

    expect(mockModelFileService.queue).toHaveBeenCalledWith(mfB);
    expect(mockModelFileService.queue).not.toHaveBeenCalledWith(mfA);
  });

  it('returns a failure reaction (without dispatching) when the ModelFile cannot be resolved', () => {
    const vf = makeViewFile({ name: 'missing' });

    let result: WebReaction | undefined;
    service.queue(vf, resolverFor([])).subscribe((r) => (result = r));

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe("File 'missing' not found");
    expect(mockModelFileService.queue).not.toHaveBeenCalled();
  });

  it('maps an action error to a failure reaction rather than erroring the observable', () => {
    const mf = makeModelFile({ name: 'file1' });
    const vf = makeViewFile({ name: 'file1' });
    mockModelFileService.stop.mockReturnValue(throwError(() => new Error('boom')));

    let result: WebReaction | undefined;
    let errored = false;
    service.stop(vf, resolverFor([mf])).subscribe({
      next: (r) => (result = r),
      error: () => (errored = true),
    });

    expect(errored).toBe(false);
    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe('boom');
  });

  it('each single command delegates to the matching ModelFileService method', () => {
    const mf = makeModelFile({ name: 'file1' });
    const vf = makeViewFile({ name: 'file1' });
    const resolve = resolverFor([mf]);

    service.stop(vf, resolve).subscribe();
    service.extract(vf, resolve).subscribe();
    service.deleteLocal(vf, resolve).subscribe();
    service.deleteRemote(vf, resolve).subscribe();
    service.validate(vf, resolve).subscribe();

    expect(mockModelFileService.stop).toHaveBeenCalledWith(mf);
    expect(mockModelFileService.extract).toHaveBeenCalledWith(mf);
    expect(mockModelFileService.deleteLocal).toHaveBeenCalledWith(mf);
    expect(mockModelFileService.deleteRemote).toHaveBeenCalledWith(mf);
    expect(mockModelFileService.validate).toHaveBeenCalledWith(mf);
  });

  // --- bulk dispatch: checked + capability filter ---

  it('bulkQueue() dispatches only files that are both checked AND queueable', () => {
    const queueableChecked = makeViewFile({ name: 'a', remoteSize: 100, isQueueable: true });
    const queueableUnchecked = makeViewFile({ name: 'b', remoteSize: 100, isQueueable: true });
    const notQueueableChecked = makeViewFile({ name: 'c', remoteSize: 100, isQueueable: false });
    const files = [queueableChecked, queueableUnchecked, notQueueableChecked];

    // Check 'a' (queueable) and 'c' (not queueable); leave 'b' unchecked.
    selection.toggle(fileKey(null, 'a'));
    selection.toggle(fileKey(null, 'c'));

    const models = [
      makeModelFile({ name: 'a', remote_size: 100 }),
      makeModelFile({ name: 'b', remote_size: 100 }),
      makeModelFile({ name: 'c', remote_size: 100 }),
    ];

    let results: WebReaction[] = [];
    service.bulkQueue(files, resolverFor(models)).subscribe((r) => (results = r));

    // Only 'a' satisfies checked AND queueable.
    expect(mockModelFileService.queue).toHaveBeenCalledTimes(1);
    expect(mockModelFileService.queue).toHaveBeenCalledWith(
      models.find((m) => m.name === 'a'),
    );
    expect(results).toEqual([OK]);
  });

  it('bulkStop() applies the isStoppable capability filter', () => {
    const stoppableChecked = makeViewFile({ name: 'dl', isStoppable: true });
    const stoppedChecked = makeViewFile({ name: 'st', isStoppable: false });
    const files = [stoppableChecked, stoppedChecked];

    selection.toggle(fileKey(null, 'dl'));
    selection.toggle(fileKey(null, 'st'));

    const models = [makeModelFile({ name: 'dl' }), makeModelFile({ name: 'st' })];

    service.bulkStop(files, resolverFor(models)).subscribe();

    expect(mockModelFileService.stop).toHaveBeenCalledTimes(1);
    expect(mockModelFileService.stop).toHaveBeenCalledWith(
      models.find((m) => m.name === 'dl'),
    );
  });

  it('bulk action returns an empty array and dispatches nothing when no file is both checked and capable', () => {
    const files = [makeViewFile({ name: 'a', isQueueable: true })];
    // 'a' is queueable but NOT checked.

    let results: WebReaction[] | undefined;
    service.bulkQueue(files, resolverFor([makeModelFile({ name: 'a' })])).subscribe(
      (r) => (results = r),
    );

    expect(results).toEqual([]);
    expect(mockModelFileService.queue).not.toHaveBeenCalled();
  });

  it('bulkDeleteRemote() applies the isRemotelyDeletable filter', () => {
    const deletable = makeViewFile({ name: 'r', remoteSize: 100, isRemotelyDeletable: true });
    const notDeletable = makeViewFile({ name: 'x', isRemotelyDeletable: false });
    const files = [deletable, notDeletable];

    selection.checkAll([fileKey(null, 'r'), fileKey(null, 'x')]);

    const models = [
      makeModelFile({ name: 'r', remote_size: 100 }),
      makeModelFile({ name: 'x' }),
    ];

    service.bulkDeleteRemote(files, resolverFor(models)).subscribe();

    expect(mockModelFileService.deleteRemote).toHaveBeenCalledTimes(1);
    expect(mockModelFileService.deleteRemote).toHaveBeenCalledWith(
      models.find((m) => m.name === 'r'),
    );
  });
});
