import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BehaviorSubject, Observable, of, EMPTY, throwError } from 'rxjs';
import { ScrollingModule } from '@angular/cdk/scrolling';

import { FileListComponent } from './file-list.component';
import { ViewFileService } from '../../services/files/view-file.service';
import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { LoggerService } from '../../services/utils/logger.service';
import { NotificationService } from '../../services/utils/notification.service';
import { NotificationLevel } from '../../models/notification';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions, SortMethod } from '../../models/view-file-options';
import { fileKey } from '../../services/files/file-key';
import { FileActionEvent } from './file.component';
import { FileAction } from '../../models/file-action';

interface MockViewFileService {
  filteredFiles$: Observable<ViewFile[]>;
  checked$: Observable<Set<string>>;
  setSelected: ReturnType<typeof vi.fn>;
  unsetSelected: ReturnType<typeof vi.fn>;
  command: ReturnType<typeof vi.fn>;
  cleanupLocal: ReturnType<typeof vi.fn>;
  toggleCheck: ReturnType<typeof vi.fn>;
  shiftCheck: ReturnType<typeof vi.fn>;
  checkAll: ReturnType<typeof vi.fn>;
  uncheckAll: ReturnType<typeof vi.fn>;
  bulkCommand: ReturnType<typeof vi.fn>;
}

interface MockNotificationService {
  show: ReturnType<typeof vi.fn>;
  hide: ReturnType<typeof vi.fn>;
}

function makeActionEvent(file: ViewFile, action: FileAction = FileAction.QUEUE): FileActionEvent {
  return { action, file, clearActiveAction: vi.fn() };
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
    isCleanupLocalable: false,
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
  let mockNotifService: MockNotificationService;

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
      command: vi.fn().mockReturnValue(EMPTY),
      cleanupLocal: vi.fn().mockReturnValue(EMPTY),
      toggleCheck: vi.fn(),
      shiftCheck: vi.fn(),
      checkAll: vi.fn(),
      uncheckAll: vi.fn(),
      bulkCommand: vi.fn().mockReturnValue(EMPTY),
    };

    mockNotifService = { show: vi.fn(), hide: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [FileListComponent, ScrollingModule],
      providers: [
        { provide: ViewFileService, useValue: mockViewFileService },
        { provide: ViewFileOptionsService, useValue: { options$: optionsSubject.asObservable() } },
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
        { provide: NotificationService, useValue: mockNotifService },
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

  it('should follow the mobile media query and remove its listener on destroy', () => {
    fixture.destroy();
    const mediaQueryTarget = new EventTarget();
    const addEventListener = vi.spyOn(mediaQueryTarget, 'addEventListener');
    const removeEventListener = vi.spyOn(mediaQueryTarget, 'removeEventListener');
    const mediaQueryList = Object.assign(mediaQueryTarget, {
      matches: true,
      media: '(max-width: 600px)',
      onchange: null,
    }) as unknown as MediaQueryList;
    const matchMedia = vi.fn().mockReturnValue(mediaQueryList);
    const originalDescriptor = Object.getOwnPropertyDescriptor(window, 'matchMedia');
    Object.defineProperty(window, 'matchMedia', {
      value: matchMedia,
      configurable: true,
    });

    try {
      fixture = TestBed.createComponent(FileListComponent);
      component = fixture.componentInstance;

      expect(matchMedia).toHaveBeenCalledWith('(max-width: 600px)');
      expect(component.useNativeScrolling()).toBe(true);
      expect(addEventListener).toHaveBeenCalledWith('change', expect.any(Function));

      const listener = addEventListener.mock.calls[0][1] as (event: MediaQueryListEvent) => void;
      const changeEvent = new Event('change') as MediaQueryListEvent;
      Object.defineProperty(changeEvent, 'matches', { value: false });
      mediaQueryList.dispatchEvent(changeEvent);
      expect(component.useNativeScrolling()).toBe(false);

      fixture.destroy();
      expect(removeEventListener).toHaveBeenCalledWith('change', listener);
    } finally {
      if (!fixture.componentRef.hostView.destroyed) fixture.destroy();
      if (originalDescriptor) {
        Object.defineProperty(window, 'matchMedia', originalDescriptor);
      } else {
        delete (window as unknown as { matchMedia?: typeof window.matchMedia }).matchMedia;
      }
    }
  });

  it('should render naturally-sized rows instead of fixed virtual rows on mobile', () => {
    fixture.destroy();
    fixture = TestBed.createComponent(FileListComponent);
    component = fixture.componentInstance;
    component.useNativeScrolling.set(true);
    filteredFilesSubject.next(Array.from(
      { length: 25 },
      (_, index) => makeViewFile({ name: `file-${index}.mkv` }),
    ));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('cdk-virtual-scroll-viewport')).toBeNull();
    expect(fixture.nativeElement.querySelector('.native-file-viewport')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.file-row').length).toBe(25);
  });

  it('should retain virtual scrolling outside the mobile breakpoint', () => {
    component.useNativeScrolling.set(false);
    fixture.detectChanges();

    const viewport = fixture.nativeElement.querySelector('cdk-virtual-scroll-viewport');
    expect(viewport).not.toBeNull();
    expect(viewport.getAttribute('itemsize')).toBe('82');
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

  it.each([
    ['QUEUE', FileAction.QUEUE],
    ['STOP', FileAction.STOP],
    ['EXTRACT', FileAction.EXTRACT],
    ['VALIDATE', FileAction.VALIDATE],
    ['DELETE_LOCAL', FileAction.DELETE_LOCAL],
    ['DELETE_REMOTE', FileAction.DELETE_REMOTE],
  ] as const)('should dispatch %s through viewFileService.command on onAction', (_label, action) => {
    const file = makeViewFile({ name: 'act-on-me.txt' });
    mockViewFileService.command.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onAction(makeActionEvent(file, action));

    expect(mockViewFileService.command).toHaveBeenCalledWith(action, file);
  });

  it('should call viewFileService.cleanupLocal on onCleanupLocal', () => {
    const file = makeViewFile({ name: 'cleanup-me', isDir: true });
    mockViewFileService.cleanupLocal.mockReturnValue(of({ success: true, data: 'ok', errorMessage: null }));

    component.onCleanupLocal(makeActionEvent(file));

    expect(mockViewFileService.cleanupLocal).toHaveBeenCalledWith(file);
  });

  // --- Single-file action error surfacing (#513) ---

  it('shows a DANGER banner and clears activeAction when an action fails', () => {
    const file = makeViewFile({ name: 'fail-me.txt' });
    const event = makeActionEvent(file);
    mockViewFileService.command.mockReturnValue(
      of({ success: false, data: null, errorMessage: 'Boom' }),
    );

    component.onAction(event);

    expect(mockNotifService.show).toHaveBeenCalledTimes(1);
    const notif = mockNotifService.show.mock.calls[0][0];
    expect(notif.level).toBe(NotificationLevel.DANGER);
    expect(notif.text).toContain('Boom');
    expect(event.clearActiveAction).toHaveBeenCalledTimes(1);
  });

  it('falls back to a generic message when a failed reaction has no errorMessage', () => {
    const event = makeActionEvent(makeViewFile());
    mockViewFileService.command.mockReturnValue(
      of({ success: false, data: null, errorMessage: null }),
    );

    component.onAction(event);

    expect(mockNotifService.show).toHaveBeenCalledTimes(1);
    expect(mockNotifService.show.mock.calls[0][0].text).toBe('Action failed');
    expect(event.clearActiveAction).toHaveBeenCalledTimes(1);
  });

  it('does not show a banner or clear activeAction on a successful action', () => {
    const logger = TestBed.inject(LoggerService);
    const event = makeActionEvent(makeViewFile());
    mockViewFileService.command.mockReturnValue(
      of({ success: true, data: 'ok', errorMessage: null }),
    );

    component.onAction(event);

    expect(mockNotifService.show).not.toHaveBeenCalled();
    expect(event.clearActiveAction).not.toHaveBeenCalled();
    expect(logger.info).toHaveBeenCalledWith('ok');
  });

  it('shows a DANGER banner and clears activeAction when the action stream errors', () => {
    const event = makeActionEvent(makeViewFile());
    mockViewFileService.command.mockReturnValue(
      throwError(() => new Error('net')),
    );

    component.onAction(event);

    expect(mockNotifService.show).toHaveBeenCalledTimes(1);
    expect(mockNotifService.show.mock.calls[0][0].level).toBe(NotificationLevel.DANGER);
    expect(event.clearActiveAction).toHaveBeenCalledTimes(1);
  });

  // --- Bulk actions ---

  it.each([
    ['QUEUE', FileAction.QUEUE],
    ['STOP', FileAction.STOP],
    ['DELETE_LOCAL', FileAction.DELETE_LOCAL],
    ['DELETE_REMOTE', FileAction.DELETE_REMOTE],
  ] as const)('should dispatch bulk %s through viewFileService.bulkCommand on onBulkAction', (_label, action) => {
    mockViewFileService.bulkCommand.mockReturnValue(of([]));

    component.onBulkAction(action);

    expect(mockViewFileService.bulkCommand).toHaveBeenCalledWith(action);
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

  it('should log failures and show a DANGER banner from bulk action responses', () => {
    const logger = TestBed.inject(LoggerService);
    mockViewFileService.bulkCommand.mockReturnValue(of([
      { success: true, data: 'ok', errorMessage: null },
      { success: false, data: null, errorMessage: 'Failed' },
    ]));

    component.onBulkAction(FileAction.QUEUE);

    expect(logger.error).toHaveBeenCalled();
    expect(logger.warn).toHaveBeenCalled();
    expect(mockNotifService.show).toHaveBeenCalledTimes(1);
    const notif = mockNotifService.show.mock.calls[0][0];
    expect(notif.level).toBe(NotificationLevel.DANGER);
    expect(notif.text).toBe('1 of 2 items failed');
  });

  it('should not show a banner when all bulk items succeed', () => {
    mockViewFileService.bulkCommand.mockReturnValue(of([
      { success: true, data: 'ok', errorMessage: null },
      { success: true, data: 'ok2', errorMessage: null },
    ]));

    component.onBulkAction(FileAction.DELETE_LOCAL);

    expect(mockNotifService.show).not.toHaveBeenCalled();
  });

  it('should log info for successful bulk items', () => {
    const logger = TestBed.inject(LoggerService);
    mockViewFileService.bulkCommand.mockReturnValue(of([
      { success: true, data: 'stopped', errorMessage: null },
    ]));

    component.onBulkAction(FileAction.STOP);

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
    let originalScrollYDescriptor: PropertyDescriptor | undefined;
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

      // Pin scrollY so chrome-height assertions are deterministic regardless
      // of prior-test scroll state. Capture the original descriptor so we can
      // restore JSDOM's live getter after the test.
      originalScrollYDescriptor = Object.getOwnPropertyDescriptor(window, 'scrollY');
      Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
    });

    afterEach(() => {
      document.documentElement.style.removeProperty('--file-list-chrome-height');
      topHeader.remove();
      fileOptions.remove();
      const g = globalThis as unknown as { ResizeObserver?: typeof ResizeObserver };
      if (originalResizeObserver !== undefined) {
        g.ResizeObserver = originalResizeObserver;
      } else {
        delete g.ResizeObserver;
      }
      window.requestAnimationFrame = originalRaf;
      if (originalScrollYDescriptor) {
        Object.defineProperty(window, 'scrollY', originalScrollYDescriptor);
      } else {
        delete (window as unknown as { scrollY?: number }).scrollY;
      }
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
