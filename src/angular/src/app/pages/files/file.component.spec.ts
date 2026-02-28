import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { SimpleChange } from '@angular/core';
import { FileComponent, FileAction } from './file.component';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { of } from 'rxjs';

function makeViewFile(overrides: Partial<ViewFile> = {}): ViewFile {
  return {
    name: 'test.txt',
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
