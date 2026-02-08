import {
  Component, ChangeDetectionStrategy, OnChanges, SimpleChanges,
  ViewChild, ElementRef, input, output
} from '@angular/core';
import { AsyncPipe, DatePipe } from '@angular/common';

import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { Localization } from '../../models/localization';
import { FileSizePipe } from '../../common/file-size.pipe';
import { EtaPipe } from '../../common/eta.pipe';
import { CapitalizePipe } from '../../common/capitalize.pipe';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';
import { Observable } from 'rxjs';

export enum FileAction {
  QUEUE,
  STOP,
  EXTRACT,
  DELETE_LOCAL,
  DELETE_REMOTE
}

@Component({
  selector: 'app-file',
  standalone: true,
  imports: [
    AsyncPipe,
    DatePipe,
    FileSizePipe,
    EtaPipe,
    CapitalizePipe,
    ClickStopPropagationDirective,
  ],
  templateUrl: './file.component.html',
  styleUrls: ['./file.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileComponent implements OnChanges {
  ViewFileStatus = ViewFileStatus;
  FileAction = FileAction;
  min = Math.min;

  @ViewChild('fileElement') fileElement!: ElementRef;

  file = input.required<ViewFile>();
  options = input.required<Observable<ViewFileOptions>>();

  queueEvent = output<ViewFile>();
  stopEvent = output<ViewFile>();
  extractEvent = output<ViewFile>();
  deleteLocalEvent = output<ViewFile>();
  deleteRemoteEvent = output<ViewFile>();

  activeAction: FileAction | null = null;

  // Delete confirmation state
  deleteConfirmationType: 'local' | 'remote' | null = null;
  deleteConfirmationTitle = '';
  deleteConfirmationMessage = '';

  ngOnChanges(changes: SimpleChanges): void {
    const fileChange = changes['file'];
    if (fileChange) {
      const oldFile: ViewFile | undefined = fileChange.previousValue;
      const newFile: ViewFile | undefined = fileChange.currentValue;
      if (oldFile != null && newFile != null && oldFile.status !== newFile.status) {
        this.activeAction = null;

        if (newFile.isSelected && this.fileElement &&
            !FileComponent.isElementInViewport(this.fileElement.nativeElement)) {
          this.fileElement.nativeElement.scrollIntoView();
        }
      }
    }
  }

  isQueueable(): boolean {
    return this.activeAction == null && this.file().isQueueable;
  }

  isStoppable(): boolean {
    return this.activeAction == null && this.file().isStoppable;
  }

  isExtractable(): boolean {
    return this.activeAction == null && this.file().isExtractable && this.file().isArchive;
  }

  isLocallyDeletable(): boolean {
    return this.activeAction == null && this.file().isLocallyDeletable;
  }

  isRemotelyDeletable(): boolean {
    return this.activeAction == null && this.file().isRemotelyDeletable;
  }

  onQueue(file: ViewFile): void {
    this.activeAction = FileAction.QUEUE;
    this.queueEvent.emit(file);
  }

  onStop(file: ViewFile): void {
    this.activeAction = FileAction.STOP;
    this.stopEvent.emit(file);
  }

  onExtract(file: ViewFile): void {
    this.activeAction = FileAction.EXTRACT;
    this.extractEvent.emit(file);
  }

  onDeleteLocal(file: ViewFile): void {
    this.deleteConfirmationType = 'local';
    this.deleteConfirmationTitle = Localization.Modal.DELETE_LOCAL_TITLE;
    this.deleteConfirmationMessage = Localization.Modal.DELETE_LOCAL_MESSAGE(file.name);
  }

  onDeleteRemote(file: ViewFile): void {
    this.deleteConfirmationType = 'remote';
    this.deleteConfirmationTitle = Localization.Modal.DELETE_REMOTE_TITLE;
    this.deleteConfirmationMessage = Localization.Modal.DELETE_REMOTE_MESSAGE(file.name);
  }

  confirmDelete(): void {
    const file = this.file();
    if (this.deleteConfirmationType === 'local') {
      this.activeAction = FileAction.DELETE_LOCAL;
      this.deleteLocalEvent.emit(file);
    } else if (this.deleteConfirmationType === 'remote') {
      this.activeAction = FileAction.DELETE_REMOTE;
      this.deleteRemoteEvent.emit(file);
    }
    this.deleteConfirmationType = null;
  }

  cancelDelete(): void {
    this.deleteConfirmationType = null;
  }

  private static isElementInViewport(el: HTMLElement): boolean {
    const rect = el.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }
}
