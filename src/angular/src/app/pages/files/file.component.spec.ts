import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { SimpleChange } from '@angular/core';
import { FileComponent } from './file.component';
import { FileAction } from '../../models/file-action';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { of } from 'rxjs';

function makeViewFile(overrides: Partial<ViewFile> = {}): ViewFile {
  return {
    name: 'test.txt',
    pairId: null,
    pairName: null,
    isDir: false,
    localSize: 100,
    remoteSize: 200,
    percentDownloaded: 100,
    status: ViewFileStatus.DOWNLOADED,
    downloadingSpeed: 0,
    eta: 0,
    fullPath: '/remote/test.txt',
    isArchive: false,
    isSelected: false,
    isChecked: false,
    isIndeterminate: false,
    isQueueable: false,
    isStoppable: false,
    isExtractable: false,
    isLocallyDeletable: true,
    isRemotelyDeletable: true,
    isCleanupLocalable: true,
    hasDownloadingDescendant: false,
    isValidatable: false,
    validateTooltip: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
    children: [],
    ...overrides,
  };
}

describe('FileComponent.ngOnChanges', () => {
  let fixture: ComponentFixture<FileComponent>;
  let component: FileComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FileComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('file', makeViewFile());
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  it('should clear activeAction when status changes', () => {
    component.activeAction = FileAction.QUEUE;
    const oldFile = makeViewFile({ status: ViewFileStatus.QUEUED });
    const newFile = makeViewFile({ status: ViewFileStatus.DOWNLOADING });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should clear activeAction for DELETE_REMOTE when isRemotelyDeletable becomes false', () => {
    component.activeAction = FileAction.DELETE_REMOTE;
    const oldFile = makeViewFile({ isRemotelyDeletable: true });
    const newFile = makeViewFile({ isRemotelyDeletable: false, remoteSize: 0 });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should NOT clear activeAction for DELETE_REMOTE when isRemotelyDeletable stays true', () => {
    component.activeAction = FileAction.DELETE_REMOTE;
    const oldFile = makeViewFile({ isRemotelyDeletable: true });
    const newFile = makeViewFile({ isRemotelyDeletable: true });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBe(FileAction.DELETE_REMOTE);
  });

  it('should clear activeAction for DELETE_LOCAL when isLocallyDeletable becomes false', () => {
    component.activeAction = FileAction.DELETE_LOCAL;
    const oldFile = makeViewFile({ isLocallyDeletable: true });
    const newFile = makeViewFile({ isLocallyDeletable: false, localSize: 0 });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should NOT clear activeAction for DELETE_LOCAL when isLocallyDeletable stays true', () => {
    component.activeAction = FileAction.DELETE_LOCAL;
    const oldFile = makeViewFile({ isLocallyDeletable: true });
    const newFile = makeViewFile({ isLocallyDeletable: true });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBe(FileAction.DELETE_LOCAL);
  });

  it('should not clear unrelated activeAction when isRemotelyDeletable changes', () => {
    component.activeAction = FileAction.QUEUE;
    const oldFile = makeViewFile({ isRemotelyDeletable: true });
    const newFile = makeViewFile({ isRemotelyDeletable: false });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBe(FileAction.QUEUE);
  });

  it('should clear activeAction for CLEANUP_LOCAL when isCleanupLocalable becomes false', () => {
    component.activeAction = 'cleanup';
    const oldFile = makeViewFile({ isCleanupLocalable: true });
    const newFile = makeViewFile({ isCleanupLocalable: false });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should NOT clear activeAction for CLEANUP_LOCAL when isCleanupLocalable stays true', () => {
    component.activeAction = 'cleanup';
    const oldFile = makeViewFile({ isCleanupLocalable: true });
    const newFile = makeViewFile({ isCleanupLocalable: true });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBe('cleanup');
  });

  it('should clear activeAction for VALIDATE when status changes', () => {
    component.activeAction = FileAction.VALIDATE;
    const oldFile = makeViewFile({ status: ViewFileStatus.DOWNLOADED });
    const newFile = makeViewFile({ status: ViewFileStatus.VALIDATING });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should clear activeAction for STOP when hasDownloadingDescendant becomes false', () => {
    component.activeAction = FileAction.STOP;
    const oldFile = makeViewFile({ status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true });
    const newFile = makeViewFile({ status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: false });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBeNull();
  });

  it('should NOT clear activeAction for STOP when hasDownloadingDescendant stays true', () => {
    component.activeAction = FileAction.STOP;
    const oldFile = makeViewFile({ status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true });
    const newFile = makeViewFile({ status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.activeAction).toBe(FileAction.STOP);
  });
});

describe('FileComponent inline delete confirmation', () => {
  let fixture: ComponentFixture<FileComponent>;
  let component: FileComponent;

  beforeEach(async () => {
    vi.useFakeTimers();

    await TestBed.configureTestingModule({
      imports: [FileComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('file', makeViewFile());
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('first click on delete local sets confirming state', () => {
    component.onAction(FileAction.DELETE_LOCAL, makeViewFile());
    expect(component.confirmingDelete).toBe('local');
    expect(component.activeAction).toBeNull();
  });

  it('second click on delete local emits event and clears state', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onAction(FileAction.DELETE_LOCAL, file);
    expect(component.confirmingDelete).toBe('local');

    component.onAction(FileAction.DELETE_LOCAL, file);
    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBe(FileAction.DELETE_LOCAL);
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ file }));
  });

  it('first click on delete remote sets confirming state', () => {
    component.onAction(FileAction.DELETE_REMOTE, makeViewFile());
    expect(component.confirmingDelete).toBe('remote');
    expect(component.activeAction).toBeNull();
  });

  it('second click on delete remote emits event and clears state', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onAction(FileAction.DELETE_REMOTE, file);
    component.onAction(FileAction.DELETE_REMOTE, file);

    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBe(FileAction.DELETE_REMOTE);
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ file }));
  });

  it('first click on cleanup local sets confirming state', () => {
    component.onCleanupLocal(makeViewFile());
    expect(component.confirmingDelete).toBe('cleanup');
    expect(component.activeAction).toBeNull();
  });

  it('second click on cleanup local emits event and clears state', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.cleanupLocalEvent, 'emit');

    component.onCleanupLocal(file);
    component.onCleanupLocal(file);

    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBe('cleanup');
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ file }));
  });

  it('confirming state auto-resets after 3 seconds', () => {
    component.onAction(FileAction.DELETE_LOCAL, makeViewFile());
    expect(component.confirmingDelete).toBe('local');

    vi.advanceTimersByTime(3000);
    expect(component.confirmingDelete).toBeNull();
  });

  it('clicking delete local while confirming remote switches to local', () => {
    component.onAction(FileAction.DELETE_REMOTE, makeViewFile());
    expect(component.confirmingDelete).toBe('remote');

    component.onAction(FileAction.DELETE_LOCAL, makeViewFile());
    expect(component.confirmingDelete).toBe('local');
  });

  it('should reset confirmingDelete when bound file changes', () => {
    component.onAction(FileAction.DELETE_LOCAL, makeViewFile());
    expect(component.confirmingDelete).toBe('local');

    const oldFile = makeViewFile({ status: ViewFileStatus.DOWNLOADED });
    const newFile = makeViewFile({ status: ViewFileStatus.QUEUED });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBeNull();

    // Timer should not fire after reset
    vi.advanceTimersByTime(5000);
    expect(component.confirmingDelete).toBeNull();
  });

  it('should reset confirmingDelete when file name changes', () => {
    component.onAction(FileAction.DELETE_REMOTE, makeViewFile());
    expect(component.confirmingDelete).toBe('remote');

    const oldFile = makeViewFile({ name: 'file-a.txt' });
    const newFile = makeViewFile({ name: 'file-b.txt' });

    component.ngOnChanges({
      file: new SimpleChange(oldFile, newFile, false),
    });

    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBeNull();
  });

  it('ngOnDestroy clears the confirm timer', () => {
    component.onAction(FileAction.DELETE_LOCAL, makeViewFile());
    expect(component.confirmingDelete).toBe('local');

    component.ngOnDestroy();
    vi.advanceTimersByTime(5000);
    // State stays as-is (timer was cleared, no reset happened)
    expect(component.confirmingDelete).toBe('local');
  });
});

describe('FileComponent action events', () => {
  let fixture: ComponentFixture<FileComponent>;
  let component: FileComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FileComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('file', makeViewFile());
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  it('clearActiveAction resets activeAction to null', () => {
    component.activeAction = FileAction.QUEUE;
    component.clearActiveAction();
    expect(component.activeAction).toBeNull();
  });

  it.each([
    ['QUEUE', FileAction.QUEUE],
    ['STOP', FileAction.STOP],
    ['EXTRACT', FileAction.EXTRACT],
    ['VALIDATE', FileAction.VALIDATE],
  ] as const)(
    'onAction(%s) emits an event carrying the action, file and a clearActiveAction callback',
    (_label, action) => {
      const file = makeViewFile();
      const spy = vi.spyOn(component.actionEvent, 'emit');

      component.onAction(action, file);

      expect(spy).toHaveBeenCalledTimes(1);
      const payload = spy.mock.calls[0][0];
      expect(payload.action).toBe(action);
      expect(payload.file).toBe(file);
      expect(typeof payload.clearActiveAction).toBe('function');

      // Action is active until the callback fires.
      expect(component.activeAction).not.toBeNull();
      payload.clearActiveAction();
      expect(component.activeAction).toBeNull();
    },
  );

  it('delete emits a clearActiveAction callback that resets activeAction', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.actionEvent, 'emit');

    // Double-click to confirm and emit.
    component.onAction(FileAction.DELETE_LOCAL, file);
    component.onAction(FileAction.DELETE_LOCAL, file);

    expect(component.activeAction).toBe(FileAction.DELETE_LOCAL);
    const payload = spy.mock.calls[0][0];
    expect(payload.file).toBe(file);
    payload.clearActiveAction();
    expect(component.activeAction).toBeNull();
  });
});

describe('FileComponent.clearActiveAction recycle guard (#540)', () => {
  let fixture: ComponentFixture<FileComponent>;
  let component: FileComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [FileComponent] }).compileComponents();
    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
    component = fixture.componentInstance;
  });

  it('clears when the instance still represents the same file and action', () => {
    const fileA = makeViewFile({ name: 'a.txt' });
    fixture.componentRef.setInput('file', fileA);
    fixture.detectChanges();
    component.activeAction = FileAction.QUEUE;

    component.clearActiveAction(fileA, FileAction.QUEUE);
    expect(component.activeAction).toBeNull();
  });

  it('does NOT clear when recycled to a different file (stale failure callback)', () => {
    const fileA = makeViewFile({ name: 'a.txt' });
    const fileB = makeViewFile({ name: 'b.txt' });
    fixture.componentRef.setInput('file', fileB); // instance recycled to file B
    fixture.detectChanges();
    component.activeAction = FileAction.DELETE_LOCAL; // B started its own action

    // A late failure callback captured for file A must not clear B's action.
    component.clearActiveAction(fileA, FileAction.QUEUE);
    expect(component.activeAction).toBe(FileAction.DELETE_LOCAL);
  });

  it('does NOT clear when the same file started a different action since', () => {
    const fileA = makeViewFile({ name: 'a.txt' });
    fixture.componentRef.setInput('file', fileA);
    fixture.detectChanges();
    component.activeAction = FileAction.VALIDATE;

    component.clearActiveAction(fileA, FileAction.QUEUE); // stale callback for an older QUEUE
    expect(component.activeAction).toBe(FileAction.VALIDATE);
  });
});

describe('FileComponent nested navigation expand/collapse', () => {
  let fixture: ComponentFixture<FileComponent>;
  let component: FileComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FileComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('file', makeViewFile());
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
    component = fixture.componentInstance;
  });

  it('defaults depth/hasChildren/isExpanded to 0/false/false', () => {
    fixture.detectChanges();
    expect(component.depth()).toBe(0);
    expect(component.hasChildren()).toBe(false);
    expect(component.isExpanded()).toBe(false);
  });

  it('reflects depth/hasChildren/isExpanded inputs', () => {
    fixture.componentRef.setInput('depth', 2);
    fixture.componentRef.setInput('hasChildren', true);
    fixture.componentRef.setInput('isExpanded', true);
    fixture.detectChanges();

    expect(component.depth()).toBe(2);
    expect(component.hasChildren()).toBe(true);
    expect(component.isExpanded()).toBe(true);
  });

  it('onToggleExpand emits the file and stops event propagation', () => {
    fixture.detectChanges();
    const file = makeViewFile({ name: 'Top' });
    const spy = vi.spyOn(component.toggleExpandEvent, 'emit');
    const event = new MouseEvent('click');
    const stopSpy = vi.spyOn(event, 'stopPropagation');

    component.onToggleExpand(event, file);

    expect(stopSpy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledExactlyOnceWith(file);
  });

  it('does not render an expand toggle when hasChildren is false', () => {
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('.expand-toggle');
    expect(button).toBeNull();
  });

  it('renders an expand toggle that dispatches onToggleExpand when hasChildren is true', () => {
    fixture.componentRef.setInput('hasChildren', true);
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('.expand-toggle');
    expect(button).not.toBeNull();

    const spy = vi.spyOn(component.toggleExpandEvent, 'emit');
    button.click();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('renders the checkbox for a nested (depth > 0) row', () => {
    fixture.componentRef.setInput('depth', 1);
    fixture.detectChanges();
    const checkbox = fixture.nativeElement.querySelector('.checkbox');
    expect(checkbox).not.toBeNull();
  });

  it('renders the checkbox for a top-level (depth 0) row', () => {
    fixture.detectChanges();
    const checkbox = fixture.nativeElement.querySelector('.checkbox');
    expect(checkbox).not.toBeNull();
  });

  it('sets the checkbox input indeterminate when the file is indeterminate', () => {
    fixture.componentRef.setInput('file', makeViewFile({ name: 'Top', isChecked: false, isIndeterminate: true }));
    fixture.detectChanges();
    const input: HTMLInputElement = fixture.nativeElement.querySelector('.checkbox input[type="checkbox"]');
    expect(input.indeterminate).toBe(true);
    expect(input.checked).toBe(false);
  });

  it('sets aria-checked to mixed when the file is indeterminate', () => {
    fixture.componentRef.setInput('file', makeViewFile({ name: 'Top', isChecked: false, isIndeterminate: true }));
    fixture.detectChanges();
    const checkbox = fixture.nativeElement.querySelector('.checkbox');
    expect(checkbox.getAttribute('aria-checked')).toBe('mixed');
  });

  it('does not set the checkbox input indeterminate when the file is not indeterminate', () => {
    fixture.detectChanges();
    const input: HTMLInputElement = fixture.nativeElement.querySelector('.checkbox input[type="checkbox"]');
    expect(input.indeterminate).toBe(false);
  });
});

describe('FileComponent nested downloading indicator', () => {
  let fixture: ComponentFixture<FileComponent>;

  function getStopButton(): HTMLButtonElement {
    const buttons = Array.from(fixture.nativeElement.querySelectorAll('.actions button')) as HTMLButtonElement[];
    return buttons.find((b) => b.querySelector('img[src="assets/icons/stop.svg"]') !== null)!;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FileComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(FileComponent);
    fixture.componentRef.setInput('options', of({ nameFilter: '', statusFilter: '' }));
  });

  it('renders "Nested Files Downloading" status text, line-broken between "Files" and "Downloading", when hasDownloadingDescendant is true', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true, isStoppable: true,
    }));
    fixture.detectChanges();

    const text = fixture.nativeElement.querySelector('.status .text');
    expect(text.querySelector('br')).not.toBeNull();
    // No separator text node at the <br> itself - textContent concatenates
    // the two fragments directly.
    expect(text.textContent.trim()).toBe('Nested FilesDownloading');
  });

  it('does not fall through to the capitalized status text when hasDownloadingDescendant is true', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.QUEUED, hasDownloadingDescendant: true, isStoppable: true,
    }));
    fixture.detectChanges();

    const texts = Array.from(fixture.nativeElement.querySelectorAll('.status .text')) as HTMLElement[];
    expect(texts.length).toBe(1);
    expect(texts[0].textContent.trim()).toBe('Nested FilesDownloading');
  });

  it('renders the nested-downloading icon (not default-remote) when hasDownloadingDescendant is true', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DEFAULT, remoteSize: 200, hasDownloadingDescendant: true, isStoppable: true,
    }));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('img.nested-downloading')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('img.default-remote')).toBeNull();
  });

  it('renders the default-remote icon (not nested-downloading) when hasDownloadingDescendant is false', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DEFAULT, remoteSize: 200, hasDownloadingDescendant: false,
    }));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('img.default-remote')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('img.nested-downloading')).toBeNull();
  });

  it('renders the plain capitalized status text when hasDownloadingDescendant is false', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DOWNLOADED, hasDownloadingDescendant: false,
    }));
    fixture.detectChanges();

    const text = fixture.nativeElement.querySelector('.status .text');
    expect(text.textContent.trim()).toBe('Downloaded');
  });

  it('renders "Stop Nested Downloads" on the Stop button when hasDownloadingDescendant is true', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true, isStoppable: true,
    }));
    fixture.detectChanges();

    expect(getStopButton().textContent).toContain('Stop Nested Downloads');
  });

  it('renders plain "Stop" on the Stop button when hasDownloadingDescendant is false', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DOWNLOADING, hasDownloadingDescendant: false, isStoppable: true,
    }));
    fixture.detectChanges();

    expect(getStopButton().textContent).toContain('Stop');
    expect(getStopButton().textContent).not.toContain('Stop Nested Downloads');
  });

  it('enables the Stop button when isStoppable is true via hasDownloadingDescendant', () => {
    fixture.componentRef.setInput('file', makeViewFile({
      status: ViewFileStatus.DEFAULT, hasDownloadingDescendant: true, isStoppable: true,
    }));
    fixture.detectChanges();

    expect(getStopButton().disabled).toBe(false);
  });
});
