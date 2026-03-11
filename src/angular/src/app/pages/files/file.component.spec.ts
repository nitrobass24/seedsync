import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { SimpleChange } from '@angular/core';
import { FileComponent, FileAction } from './file.component';
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
    component.onDeleteLocal(makeViewFile());
    expect(component.confirmingDelete).toBe('local');
    expect(component.activeAction).toBeNull();
  });

  it('second click on delete local emits event and clears state', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.deleteLocalEvent, 'emit');

    component.onDeleteLocal(file);
    expect(component.confirmingDelete).toBe('local');

    component.onDeleteLocal(file);
    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBe(FileAction.DELETE_LOCAL);
    expect(spy).toHaveBeenCalledWith(file);
  });

  it('first click on delete remote sets confirming state', () => {
    component.onDeleteRemote(makeViewFile());
    expect(component.confirmingDelete).toBe('remote');
    expect(component.activeAction).toBeNull();
  });

  it('second click on delete remote emits event and clears state', () => {
    const file = makeViewFile();
    const spy = vi.spyOn(component.deleteRemoteEvent, 'emit');

    component.onDeleteRemote(file);
    component.onDeleteRemote(file);

    expect(component.confirmingDelete).toBeNull();
    expect(component.activeAction).toBe(FileAction.DELETE_REMOTE);
    expect(spy).toHaveBeenCalledWith(file);
  });

  it('confirming state auto-resets after 3 seconds', () => {
    component.onDeleteLocal(makeViewFile());
    expect(component.confirmingDelete).toBe('local');

    vi.advanceTimersByTime(3000);
    expect(component.confirmingDelete).toBeNull();
  });

  it('clicking delete local while confirming remote switches to local', () => {
    component.onDeleteRemote(makeViewFile());
    expect(component.confirmingDelete).toBe('remote');

    component.onDeleteLocal(makeViewFile());
    expect(component.confirmingDelete).toBe('local');
  });

  it('should reset confirmingDelete when bound file changes', () => {
    component.onDeleteLocal(makeViewFile());
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
    component.onDeleteRemote(makeViewFile());
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
    component.onDeleteLocal(makeViewFile());
    expect(component.confirmingDelete).toBe('local');

    component.ngOnDestroy();
    vi.advanceTimersByTime(5000);
    // State stays as-is (timer was cleared, no reset happened)
    expect(component.confirmingDelete).toBe('local');
  });
});
