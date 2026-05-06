import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject, of } from 'rxjs';

import { FileOptionsComponent } from './file-options.component';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { ViewFileService } from '../../services/files/view-file.service';
import { DomService } from '../../services/utils/dom.service';
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

describe('FileOptionsComponent', () => {
  let component: FileOptionsComponent;
  let filesSubject: BehaviorSubject<ViewFile[]>;
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let mockViewFileOptionsService: {
    options$: ReturnType<typeof BehaviorSubject.prototype.asObservable>;
    setNameFilter: ReturnType<typeof vi.fn>;
    setSelectedStatusFilter: ReturnType<typeof vi.fn>;
    setSortMethod: ReturnType<typeof vi.fn>;
    setShowDetails: ReturnType<typeof vi.fn>;
    setPinFilter: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    filesSubject = new BehaviorSubject<ViewFile[]>([]);
    optionsSubject = new BehaviorSubject<ViewFileOptions>(makeOptions());

    mockViewFileOptionsService = {
      options$: optionsSubject.asObservable(),
      setNameFilter: vi.fn(),
      setSelectedStatusFilter: vi.fn(),
      setSortMethod: vi.fn(),
      setShowDetails: vi.fn(),
      setPinFilter: vi.fn(),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ViewFileOptionsService, useValue: mockViewFileOptionsService },
        { provide: ViewFileService, useValue: { files$: filesSubject.asObservable() } },
        { provide: DomService, useValue: { headerHeight$: of(0) } },
      ],
    });

    const fixture = TestBed.createComponent(FileOptionsComponent);
    component = fixture.componentInstance;
    component.ngOnInit();
  });

  // --- Status filter enablement ---

  it('should disable all status filters when file list is empty', () => {
    filesSubject.next([]);
    expect(component.isDownloadingStatusEnabled).toBe(false);
    expect(component.isDownloadedStatusEnabled).toBe(false);
    expect(component.isQueuedStatusEnabled).toBe(false);
    expect(component.isStoppedStatusEnabled).toBe(false);
    expect(component.isExtractedStatusEnabled).toBe(false);
    expect(component.isExtractingStatusEnabled).toBe(false);
  });

  it('should enable DOWNLOADING status filter when a downloading file exists', () => {
    filesSubject.next([makeViewFile({ status: ViewFileStatus.DOWNLOADING })]);
    expect(component.isDownloadingStatusEnabled).toBe(true);
    expect(component.isDownloadedStatusEnabled).toBe(false);
  });

  it('should enable multiple status filters based on file list contents', () => {
    filesSubject.next([
      makeViewFile({ name: 'a', status: ViewFileStatus.DOWNLOADING }),
      makeViewFile({ name: 'b', status: ViewFileStatus.QUEUED }),
      makeViewFile({ name: 'c', status: ViewFileStatus.EXTRACTED }),
    ]);
    expect(component.isDownloadingStatusEnabled).toBe(true);
    expect(component.isQueuedStatusEnabled).toBe(true);
    expect(component.isExtractedStatusEnabled).toBe(true);
    expect(component.isDownloadedStatusEnabled).toBe(false);
    expect(component.isStoppedStatusEnabled).toBe(false);
  });

  it('should update enablement reactively when file list changes', () => {
    filesSubject.next([makeViewFile({ status: ViewFileStatus.DOWNLOADING })]);
    expect(component.isDownloadingStatusEnabled).toBe(true);

    filesSubject.next([makeViewFile({ status: ViewFileStatus.QUEUED })]);
    expect(component.isDownloadingStatusEnabled).toBe(false);
    expect(component.isQueuedStatusEnabled).toBe(true);
  });

  // --- Delegation to ViewFileOptionsService ---

  it('should delegate name filter changes to ViewFileOptionsService', () => {
    component.onFilterByName('test');
    expect(mockViewFileOptionsService.setNameFilter).toHaveBeenCalledWith('test');
  });

  it('should delegate status filter changes to ViewFileOptionsService', () => {
    component.onFilterByStatus(ViewFileStatus.DOWNLOADING);
    expect(mockViewFileOptionsService.setSelectedStatusFilter).toHaveBeenCalledWith(ViewFileStatus.DOWNLOADING);
  });

  it('should delegate sort method changes to ViewFileOptionsService', () => {
    component.onSort(SortMethod.NAME_ASC);
    expect(mockViewFileOptionsService.setSortMethod).toHaveBeenCalledWith(SortMethod.NAME_ASC);
  });

  it('should toggle showDetails via ViewFileOptionsService', () => {
    // Initial showDetails is false (from makeOptions default)
    component.onToggleShowDetails();
    expect(mockViewFileOptionsService.setShowDetails).toHaveBeenCalledWith(true);
  });
});
