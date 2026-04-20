import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BehaviorSubject, Observable, of, EMPTY } from 'rxjs';
import { ScrollingModule } from '@angular/cdk/scrolling';

import { FileListComponent } from './file-list.component';
import { ViewFileService } from '../../services/files/view-file.service';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { LoggerService } from '../../services/utils/logger.service';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions, SortMethod } from '../../models/view-file-options';
import { fileKey } from '../../services/files/file-key';

interface MockViewFileService {
  filteredFiles$: Observable<ViewFile[]>;
  checked$: Observable<Set<string>>;
  setSelected: ReturnType<typeof vi.fn>;
  unsetSelected: ReturnType<typeof vi.fn>;
  queue: ReturnType<typeof vi.fn>;
  stop: ReturnType<typeof vi.fn>;
  extract: ReturnType<typeof vi.fn>;
  validate: ReturnType<typeof vi.fn>;
  deleteLocal: ReturnType<typeof vi.fn>;
  deleteRemote: ReturnType<typeof vi.fn>;
  toggleCheck: ReturnType<typeof vi.fn>;
  shiftCheck: ReturnType<typeof vi.fn>;
  checkAll: ReturnType<typeof vi.fn>;
  uncheckAll: ReturnType<typeof vi.fn>;
  bulkQueue: ReturnType<typeof vi.fn>;
  bulkStop: ReturnType<typeof vi.fn>;
  bulkDeleteLocal: ReturnType<typeof vi.fn>;
  bulkDeleteRemote: ReturnType<typeof vi.fn>;
}

function makeViewFile(overrides: Partial<ViewFile> = {}): ViewFile {
  return {
    name: 'test.txt',
    pairId: null,
    pairName: null,
    isDir: false,
    localSize: 100,
    remoteSize: 200,
    percentDownloaded: 50,
    status: ViewFileStatus.DEFAULT,
    downloadingSpeed: 0,
    eta: 0,
    fullPath: '/remote/test.txt',
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

describe('FileListComponent', () => {
  let fixture: ComponentFixture<FileListComponent>;
  let component: FileListComponent;

  let filteredFilesSubject: BehaviorSubject<ViewFile[]>;
  let checkedSubject: BehaviorSubject<Set<string>>;
  let optionsSubject: BehaviorSubject<ViewFileOptions>;
  let mockViewFileService: MockViewFileService;

  beforeEach(async () => {
    filteredFilesSubject = new BehaviorSubject<ViewFile[]>([]);
    checkedSubject = new BehaviorSubject<Set<string>>(new Set());
    optionsSubject = new BehaviorSubject<ViewFileOptions>({
      showDetails: false,
      sortMethod: SortMethod.STATUS,
      selectedStatusFilter: null,
      nameFilter: '',
      pinFilter: false,
    });

    mockViewFileService = {
      filteredFiles$: filteredFilesSubject.asObservable(),
      checked$: checkedSubject.asObservable(),
      setSelected: vi.fn(),
      unsetSelected: vi.fn(),
      queue: vi.fn().mockReturnValue(EMPTY),
      stop: vi.fn().mockReturnValue(EMPTY),
      extract: vi.fn().mockReturnValue(EMPTY),
      validate: vi.fn().mockReturnValue(EMPTY),
      deleteLocal: vi.fn().mockReturnValue(EMPTY),
      deleteRemote: vi.fn().mockReturnValue(EMPTY),
      toggleCheck: vi.fn(),
      shiftCheck: vi.fn(),
      checkAll: vi.fn(),
      uncheckAll: vi.fn(),
      bulkQueue: vi.fn().mockReturnValue(EMPTY),
      bulkStop: vi.fn().mockReturnValue(EMPTY),
      bulkDeleteLocal: vi.fn().mockReturnValue(EMPTY),
      bulkDeleteRemote: vi.fn().mockReturnValue(EMPTY),
    };

    await TestBed.configureTestingModule({
      imports: [FileListComponent, ScrollingModule],
      providers: [
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FileListComponent);
    // Give the virtual scroll viewport a stable height so it renders items
    (fixture.nativeElement as HTMLElement).style.height = '400px';
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  // --- Rendering ---

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should render files from ViewFileService', () => {
    filteredFilesSubject.next([
      makeViewFile({ name: 'alpha.mkv' }),
      makeViewFile({ name: 'beta.mkv' }),
    ]);
    fixture.detectChanges();

    const fileElements = fixture.nativeElement.querySelectorAll('app-file');
    expect(fileElements.length).toBe(2);
  });

  it('should render no app-file elements when file list is empty', () => {
    filteredFilesSubject.next([]);
    fixture.detectChanges();

    const fileElements = fixture.nativeElement.querySelectorAll('app-file');
    expect(fileElements.length).toBe(0);
  });

  it('should update rendered files when filteredFiles$ emits new values', () => {
    filteredFilesSubject.next([makeViewFile({ name: 'one.txt' })]);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('app-file').length).toBe(1);

    filteredFilesSubject.next([
      makeViewFile({ name: 'one.txt' }),
      makeViewFile({ name: 'two.txt' }),
      makeViewFile({ name: 'three.txt' }),
    ]);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('app-file').length).toBe(3);
  });

  // --- Header ---

  it('should render the header row with column labels', () => {
    const header = fixture.nativeElement.querySelector('#header');
    expect(header).toBeTruthy();
    expect(header.textContent).toContain('Filename');
    expect(header.textContent).toContain('Pair');
    expect(header.textContent).toContain('Status');
    expect(header.textContent).toContain('Speed');
    expect(header.textContent).toContain('ETA');
    expect(header.textContent).toContain('Size');
  });

  it('should render a select-all checkbox in the header', () => {
    const checkbox = fixture.nativeElement.querySelector('#header input[type="checkbox"]');
    expect(checkbox).toBeTruthy();
  });

  // --- Select-all checkbox ---

  it('should call checkAll when select-all checkbox is checked', () => {
    const checkbox = fixture.nativeElement.querySelector('#header input[type="checkbox"]') as HTMLInputElement;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(mockViewFileService.checkAll).toHaveBeenCalled();
  });

  it('should call uncheckAll when select-all checkbox is unchecked', () => {
    const checkbox = fixture.nativeElement.querySelector('#header input[type="checkbox"]') as HTMLInputElement;
    // First check it
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    // Then uncheck it
    checkbox.checked = false;
    checkbox.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(mockViewFileService.uncheckAll).toHaveBeenCalled();
  });

  // --- Bulk action bar visibility ---

  it('should not show bulk action bar when no files are checked', () => {
    checkedSubject.next(new Set());
    fixture.detectChanges();

    const bulkBar = fixture.nativeElement.querySelector('app-bulk-action-bar');
    expect(bulkBar).toBeNull();
  });

  it('should show bulk action bar when files are checked', () => {
    checkedSubject.next(new Set(['test.txt']));
    fixture.detectChanges();

    const bulkBar = fixture.nativeElement.querySelector('app-bulk-action-bar');
    expect(bulkBar).toBeTruthy();
  });

  it('should hide bulk action bar when checked set returns to empty', () => {
    checkedSubject.next(new Set(['test.txt']));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-bulk-action-bar')).toBeTruthy();

    checkedSubject.next(new Set());
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-bulk-action-bar')).toBeNull();
  });

  // --- Selection (click on file) ---

  it('should call setSelected when clicking an unselected file', () => {
    const file = makeViewFile({ name: 'click-me.txt', isSelected: false });
    component.onSelect(file);

    expect(mockViewFileService.setSelected).toHaveBeenCalledWith(file);
  });

  it('should call unsetSelected when clicking an already-selected file', () => {
    const file = makeViewFile({ name: 'click-me.txt', isSelected: true });
    component.onSelect(file);

    expect(mockViewFileService.unsetSelected).toHaveBeenCalled();
  });

  // --- Check toggling ---

  it('should call toggleCheck on onCheck without shiftKey', () => {
    const file = makeViewFile({ name: 'check-me.txt' });
    component.onCheck({ file, shiftKey: false });

    expect(mockViewFileService.toggleCheck).toHaveBeenCalledWith(file);
  });

  it('should call shiftCheck on onCheck with shiftKey', () => {
    const file = makeViewFile({ name: 'check-me.txt' });
    component.onCheck({ file, shiftKey: true });

    expect(mockViewFileService.shiftCheck).toHaveBeenCalledWith(file);
  });

  // --- Individual file actions ---

  it('should call viewFileService.queue on onQueue', () => {
    const file = makeViewFile({ name: 'queue-me.txt' });
    mockViewFileService.queue.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onQueue(file);

    expect(mockViewFileService.queue).toHaveBeenCalledWith(file);
  });

  it('should call viewFileService.stop on onStop', () => {
    const file = makeViewFile({ name: 'stop-me.txt' });
    mockViewFileService.stop.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onStop(file);

    expect(mockViewFileService.stop).toHaveBeenCalledWith(file);
  });

  it('should call viewFileService.extract on onExtract', () => {
    const file = makeViewFile({ name: 'extract-me.txt' });
    mockViewFileService.extract.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onExtract(file);

    expect(mockViewFileService.extract).toHaveBeenCalledWith(file);
  });

  it('should call viewFileService.validate on onValidate', () => {
    const file = makeViewFile({ name: 'validate-me.txt' });
    mockViewFileService.validate.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onValidate(file);

    expect(mockViewFileService.validate).toHaveBeenCalledWith(file);
  });

  it('should call viewFileService.deleteLocal on onDeleteLocal', () => {
    const file = makeViewFile({ name: 'del-local.txt' });
    mockViewFileService.deleteLocal.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onDeleteLocal(file);

    expect(mockViewFileService.deleteLocal).toHaveBeenCalledWith(file);
  });

  it('should call viewFileService.deleteRemote on onDeleteRemote', () => {
    const file = makeViewFile({ name: 'del-remote.txt' });
    mockViewFileService.deleteRemote.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onDeleteRemote(file);

    expect(mockViewFileService.deleteRemote).toHaveBeenCalledWith(file);
  });

  // --- Bulk actions ---

  it('should call viewFileService.bulkQueue on onBulkQueue', () => {
    mockViewFileService.bulkQueue.mockReturnValue(of([]));

    component.onBulkQueue();

    expect(mockViewFileService.bulkQueue).toHaveBeenCalled();
  });

  it('should call viewFileService.bulkStop on onBulkStop', () => {
    mockViewFileService.bulkStop.mockReturnValue(of([]));

    component.onBulkStop();

    expect(mockViewFileService.bulkStop).toHaveBeenCalled();
  });

  it('should call viewFileService.bulkDeleteLocal on onBulkDeleteLocal', () => {
    mockViewFileService.bulkDeleteLocal.mockReturnValue(of([]));

    component.onBulkDeleteLocal();

    expect(mockViewFileService.bulkDeleteLocal).toHaveBeenCalled();
  });

  it('should call viewFileService.bulkDeleteRemote on onBulkDeleteRemote', () => {
    mockViewFileService.bulkDeleteRemote.mockReturnValue(of([]));

    component.onBulkDeleteRemote();

    expect(mockViewFileService.bulkDeleteRemote).toHaveBeenCalled();
  });

  // --- Track-by function ---

  it('should generate track key from pairId and name', () => {
    const file = makeViewFile({ pairId: 'pair-x', name: 'movie.mkv' });
    expect(FileListComponent.identify(0, file)).toBe(fileKey('pair-x', 'movie.mkv'));
  });

  it('should generate track key with just name when pairId is null', () => {
    const file = makeViewFile({ pairId: null, name: 'movie.mkv' });
    expect(FileListComponent.identify(0, file)).toBe(fileKey(null, 'movie.mkv'));
  });

  // --- Bulk response handling ---

  it('should log failures from bulk action responses', () => {
    const logger = TestBed.inject(LoggerService);
    mockViewFileService.bulkQueue.mockReturnValue(of([
      { success: true, data: 'ok', errorMessage: null },
      { success: false, data: null, errorMessage: 'Failed' },
    ]));

    component.onBulkQueue();

    expect(logger.error).toHaveBeenCalled();
    expect(logger.warn).toHaveBeenCalled();
  });

  it('should log info for successful bulk items', () => {
    const logger = TestBed.inject(LoggerService);
    mockViewFileService.bulkStop.mockReturnValue(of([
      { success: true, data: 'stopped', errorMessage: null },
    ]));

    component.onBulkStop();

    expect(logger.info).toHaveBeenCalledWith('stopped');
  });

  // --- Dynamic chrome-height observer ---

  describe('chrome-height observer', () => {
    // Capture the ResizeObserver callback so the test can trigger it on demand,
    // and record which elements were observed/unobserved.
    interface FakeObserverState {
      callback: ResizeObserverCallback | null;
      observed: Element[];
      disconnected: boolean;
    }

    let observerState: FakeObserverState;
    let originalResizeObserver: typeof ResizeObserver | undefined;
    let originalRaf: typeof window.requestAnimationFrame;
    let rafCallbacks: FrameRequestCallback[];
    let topHeader: HTMLElement;
    let fileOptions: HTMLElement;

    beforeEach(() => {
      // The outer beforeEach already built a fixture with the real ResizeObserver.
      // Destroy it so we can rebuild under a fake and get deterministic behaviour.
      fixture?.destroy();
      document.documentElement.style.removeProperty('--file-list-chrome-height');

      // Extra chrome elements above the file list — the observer queries the
      // document for these so they have to live in the real DOM.
      topHeader = document.createElement('div');
      topHeader.id = 'top-header';
      fileOptions = document.createElement('div');
      fileOptions.id = 'file-options';
      document.body.prepend(fileOptions);
      document.body.prepend(topHeader);

      observerState = { callback: null, observed: [], disconnected: false };
      originalResizeObserver = (globalThis as { ResizeObserver?: typeof ResizeObserver }).ResizeObserver;
      (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver =
        class FakeResizeObserver {
          constructor(cb: ResizeObserverCallback) { observerState.callback = cb; }
          observe(el: Element): void { observerState.observed.push(el); }
          unobserve(): void { /* noop */ }
          disconnect(): void { observerState.disconnected = true; }
        };

      // Run any queued rAF callbacks synchronously for deterministic assertions.
      rafCallbacks = [];
      originalRaf = window.requestAnimationFrame;
      window.requestAnimationFrame = ((cb: FrameRequestCallback) => {
        rafCallbacks.push(cb);
        return rafCallbacks.length;
      }) as typeof window.requestAnimationFrame;
    });

    afterEach(() => {
      document.documentElement.style.removeProperty('--file-list-chrome-height');
      topHeader.remove();
      fileOptions.remove();
      if (originalResizeObserver) {
        (globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
          originalResizeObserver;
      }
      window.requestAnimationFrame = originalRaf;
    });

    function flushRaf(): void {
      const pending = rafCallbacks;
      rafCallbacks = [];
      pending.forEach(cb => cb(performance.now()));
    }

    it('observes top-header, file-options, and the host element', () => {
      // Re-create the fixture so ngAfterViewInit runs with our fake observer.
      fixture = TestBed.createComponent(FileListComponent);
      (fixture.nativeElement as HTMLElement).style.height = '400px';
      fixture.detectChanges();

      expect(observerState.observed).toContain(topHeader);
      expect(observerState.observed).toContain(fileOptions);
      expect(observerState.observed).toContain(fixture.nativeElement);
    });

    it('sets --file-list-chrome-height from the viewport element position', () => {
      fixture = TestBed.createComponent(FileListComponent);
      (fixture.nativeElement as HTMLElement).style.height = '400px';
      fixture.detectChanges();

      const viewportEl = fixture.nativeElement.querySelector('cdk-virtual-scroll-viewport') as HTMLElement;
      // Pin a known top offset — the observer should round it up and expose it.
      vi.spyOn(viewportEl, 'getBoundingClientRect').mockReturnValue({
        top: 137.4, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0,
        toJSON: () => ({}),
      } as DOMRect);
      Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });

      // Trigger the observer callback and flush the rAF-scheduled update.
      observerState.callback?.([], {} as ResizeObserver);
      flushRaf();

      expect(document.documentElement.style.getPropertyValue('--file-list-chrome-height'))
        .toBe('138px');
    });

    it('disconnects the observer and clears the CSS var on destroy', () => {
      fixture = TestBed.createComponent(FileListComponent);
      (fixture.nativeElement as HTMLElement).style.height = '400px';
      fixture.detectChanges();

      document.documentElement.style.setProperty('--file-list-chrome-height', '123px');
      fixture.destroy();

      expect(observerState.disconnected).toBe(true);
      expect(document.documentElement.style.getPropertyValue('--file-list-chrome-height'))
        .toBe('');
    });
  });
});
