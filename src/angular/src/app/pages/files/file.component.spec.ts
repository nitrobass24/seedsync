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
    isQueueable: false,
    isStoppable: false,
    isExtractable: false,
    isLocallyDeletable: true,
    isRemotelyDeletable: true,
    isCleanupLocalable: true,
    isValidatable: false,
    validateTooltip: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
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
