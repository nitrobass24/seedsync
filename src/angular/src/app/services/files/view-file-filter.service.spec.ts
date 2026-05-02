import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { ViewFileFilterService } from './view-file-filter.service';
import { ViewFileService, ViewFileFilterCriteria } from './view-file.service';
import { ViewFileOptionsService } from './view-file-options.service';
import { LoggerService } from '../utils/logger.service';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions, SortMethod } from '../../models/view-file-options';

function makeViewFile(overrides: Partial<ViewFile> = {}): ViewFile {
  return {
    name: 'TestFile.txt',
    pairId: null,
    pairName: null,
    isDir: false,
    localSize: 0,
    remoteSize: 100,
    percentDownloaded: 0,
    status: ViewFileStatus.DEFAULT,
    downloadingSpeed: 0,
    eta: 0,
    fullPath: '/TestFile.txt',
    isArchive: false,
    isSelected: false,
    isChecked: false,
    isQueueable: true,
    isStoppable: false,
    isExtractable: false,
    isLocallyDeletable: false,
    isRemotelyDeletable: true,
    isValidatable: false,
    validateTooltip: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
    ...overrides,
  };
}

function makeOptions(overrides: Partial<ViewFileOptions> = {}): ViewFileOptions {
  return {
    showDetails: false,
    sortMethod: SortMethod.STATUS,
    selectedStatusFilter: null,
    nameFilter: '',
    pinFilter: false,
    ...overrides,
  };
}

// ─── NameFilterCriteria (tested via service) ──────────────────────────

describe('ViewFileFilterService — NameFilterCriteria', () => {
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let capturedCriteria: ViewFileFilterCriteria | null;
  let mockViewFileService: { setFilterCriteria: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    capturedCriteria = null;
    optionsSubject = new BehaviorSubject<ViewFileOptions>(makeOptions());
    mockViewFileService = {
      setFilterCriteria: vi.fn((c: ViewFileFilterCriteria | null) => {
        capturedCriteria = c;
      }),
    };

    TestBed.configureTestingModule({
      providers: [
        ViewFileFilterService,
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });
    // Instantiate to trigger the constructor subscription
    TestBed.inject(ViewFileFilterService);
  });

  it('should match all files when name filter is null', () => {
    optionsSubject.next(makeOptions({ nameFilter: null as unknown as string }));
    const file = makeViewFile({ name: 'Anything.mkv' });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(true);
  });

  it('should match all files when name filter is empty string', () => {
    optionsSubject.next(makeOptions({ nameFilter: '' }));
    const file = makeViewFile({ name: 'Anything.mkv' });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(true);
  });

  it('should match substring case-insensitively', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'show' }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'My.Show.S01E01.mkv' }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'MY.SHOW.S01E01.mkv' }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'other-file.txt' }))).toBe(false);
  });

  it('should treat spaces as dots for fuzzy matching ("my show" matches "My.Show.S01E01")', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'my show' }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'My.Show.S01E01.mkv' }))).toBe(true);
  });

  it('should treat dots as spaces for fuzzy matching ("my.show" matches "My Show S01E01")', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'my.show' }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'My Show S01E01.mkv' }))).toBe(true);
  });

  it('should return false for all files when no name matches', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'nonexistent' }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'Something.Else.mkv' }))).toBe(false);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'Another.File.txt' }))).toBe(false);
  });

  it('should match when query contains mixed dots and spaces', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'my.show s01' }));
    // The original query lowercased: "my.show s01"
    // space→dot variant: "my.show.s01"
    // dot→space variant: "my show s01"
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ name: 'My.Show.S01E01.mkv' }))).toBe(true);
  });

  it('should match only on the file name, not other fields', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'download' }));
    // Name doesn't contain "download" but status is DOWNLOADING
    const file = makeViewFile({ name: 'SomeFile.txt', status: ViewFileStatus.DOWNLOADING });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(false);
  });
});

// ─── StatusFilterCriteria (tested via service) ────────────────────────

describe('ViewFileFilterService — StatusFilterCriteria', () => {
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let capturedCriteria: ViewFileFilterCriteria | null;
  let mockViewFileService: { setFilterCriteria: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    capturedCriteria = null;
    optionsSubject = new BehaviorSubject<ViewFileOptions>(makeOptions());
    mockViewFileService = {
      setFilterCriteria: vi.fn((c: ViewFileFilterCriteria | null) => {
        capturedCriteria = c;
      }),
    };

    TestBed.configureTestingModule({
      providers: [
        ViewFileFilterService,
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });
    TestBed.inject(ViewFileFilterService);
  });

  it('should match all files when status filter is null', () => {
    optionsSubject.next(makeOptions({ selectedStatusFilter: null }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.DEFAULT }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.DOWNLOADING }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.QUEUED }))).toBe(true);
  });

  it('should match only files with the specified status', () => {
    optionsSubject.next(makeOptions({ selectedStatusFilter: ViewFileStatus.DOWNLOADING }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.DOWNLOADING }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.DEFAULT }))).toBe(false);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.QUEUED }))).toBe(false);
  });

  it('should match each status enum value correctly', () => {
    optionsSubject.next(makeOptions({ selectedStatusFilter: ViewFileStatus.EXTRACTED }));
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.EXTRACTED }))).toBe(true);
    expect(capturedCriteria!.meetsCriteria(makeViewFile({ status: ViewFileStatus.EXTRACTING }))).toBe(false);
  });
});

// ─── AndFilterCriteria (combined name + status) ───────────────────────

describe('ViewFileFilterService — AndFilterCriteria', () => {
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let capturedCriteria: ViewFileFilterCriteria | null;
  let mockViewFileService: { setFilterCriteria: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    capturedCriteria = null;
    optionsSubject = new BehaviorSubject<ViewFileOptions>(makeOptions());
    mockViewFileService = {
      setFilterCriteria: vi.fn((c: ViewFileFilterCriteria | null) => {
        capturedCriteria = c;
      }),
    };

    TestBed.configureTestingModule({
      providers: [
        ViewFileFilterService,
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });
    TestBed.inject(ViewFileFilterService);
  });

  it('should pass when both name and status match', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'show', selectedStatusFilter: ViewFileStatus.DOWNLOADING }));
    const file = makeViewFile({ name: 'My.Show.S01E01.mkv', status: ViewFileStatus.DOWNLOADING });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(true);
  });

  it('should reject when name matches but status does not', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'show', selectedStatusFilter: ViewFileStatus.DOWNLOADING }));
    const file = makeViewFile({ name: 'My.Show.S01E01.mkv', status: ViewFileStatus.DEFAULT });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(false);
  });

  it('should reject when status matches but name does not', () => {
    optionsSubject.next(makeOptions({ nameFilter: 'show', selectedStatusFilter: ViewFileStatus.DOWNLOADING }));
    const file = makeViewFile({ name: 'Other.File.txt', status: ViewFileStatus.DOWNLOADING });
    expect(capturedCriteria!.meetsCriteria(file)).toBe(false);
  });
});

// ─── Service integration ──────────────────────────────────────────────

describe('ViewFileFilterService — service integration', () => {
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let mockViewFileService: { setFilterCriteria: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    optionsSubject = new BehaviorSubject<ViewFileOptions>(makeOptions());
    mockViewFileService = { setFilterCriteria: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        ViewFileFilterService,
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });
    TestBed.inject(ViewFileFilterService);
  });

  it('should call setFilterCriteria when status filter changes', () => {
    mockViewFileService.setFilterCriteria.mockClear();
    optionsSubject.next(makeOptions({ selectedStatusFilter: ViewFileStatus.QUEUED }));
    expect(mockViewFileService.setFilterCriteria).toHaveBeenCalledTimes(1);
  });

  it('should call setFilterCriteria when name filter changes', () => {
    mockViewFileService.setFilterCriteria.mockClear();
    optionsSubject.next(makeOptions({ nameFilter: 'test' }));
    expect(mockViewFileService.setFilterCriteria).toHaveBeenCalledTimes(1);
  });

  it('should not call setFilterCriteria when options re-emit with same filter values', () => {
    // Initial emission happened during construction with defaults (null status, '' name)
    mockViewFileService.setFilterCriteria.mockClear();

    // Re-emit with identical values — should NOT trigger a redundant update
    optionsSubject.next(makeOptions({ selectedStatusFilter: null, nameFilter: '' }));
    expect(mockViewFileService.setFilterCriteria).not.toHaveBeenCalled();
  });

  it('should call setFilterCriteria only once when both filters change simultaneously', () => {
    mockViewFileService.setFilterCriteria.mockClear();
    optionsSubject.next(makeOptions({ selectedStatusFilter: ViewFileStatus.DOWNLOADED, nameFilter: 'movie' }));
    expect(mockViewFileService.setFilterCriteria).toHaveBeenCalledTimes(1);
  });
});
