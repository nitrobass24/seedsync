import {
  Component, ChangeDetectionStrategy, ChangeDetectorRef, OnChanges, OnDestroy, SimpleChanges,
  ViewChild, ElementRef, input, output, inject
} from '@angular/core';
import { AsyncPipe, DatePipe } from '@angular/common';

import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { FileSizePipe } from '../../common/file-size.pipe';
import { EtaPipe } from '../../common/eta.pipe';
import { CapitalizePipe } from '../../common/capitalize.pipe';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';
import { Observable } from 'rxjs';

export enum FileAction {
  QUEUE,
  STOP,
  EXTRACT,
  VALIDATE,
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
export class FileComponent implements OnChanges, OnDestroy {
  private readonly cdr = inject(ChangeDetectorRef);
  ViewFileStatus = ViewFileStatus;
  FileAction = FileAction;
  min = Math.min;

  @ViewChild('fileElement') fileElement!: ElementRef;

  file = input.required<ViewFile>();
  options = input.required<Observable<ViewFileOptions>>();

  checkEvent = output<{file: ViewFile, shiftKey: boolean}>();
  queueEvent = output<ViewFile>();
  stopEvent = output<ViewFile>();
  extractEvent = output<ViewFile>();
  deleteLocalEvent = output<ViewFile>();
  validateEvent = output<ViewFile>();
  deleteRemoteEvent = output<ViewFile>();

  activeAction: FileAction | null = null;

  // Inline double-click delete confirmation state
  confirmingDelete: 'local' | 'remote' | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    const fileChange = changes['file'];
    if (fileChange) {
      const oldFile: ViewFile | undefined = fileChange.previousValue;
      const newFile: ViewFile | undefined = fileChange.currentValue;
      if (oldFile != null && newFile != null) {
        if (oldFile.pairId !== newFile.pairId || oldFile.name !== newFile.name) {
          this.activeAction = null;
          this.resetConfirmState();
        } else if (oldFile.status !== newFile.status) {
          this.activeAction = null;
          this.resetConfirmState();
        } else if (this.activeAction === FileAction.DELETE_REMOTE &&
                   oldFile.isRemotelyDeletable && !newFile.isRemotelyDeletable) {
          this.activeAction = null;
          this.resetConfirmState();
        } else if (this.activeAction === FileAction.DELETE_LOCAL &&
                   oldFile.isLocallyDeletable && !newFile.isLocallyDeletable) {
          this.activeAction = null;
          this.resetConfirmState();
        }

        if (!oldFile.isSelected && newFile.isSelected && this.fileElement &&
            !FileComponent.isElementInViewport(this.fileElement.nativeElement)) {
          this.fileElement.nativeElement.scrollIntoView();
        }
      }
    }
  }

  ngOnDestroy(): void {
    this.clearConfirmTimer();
  }

  onCheck(event: MouseEvent, file: ViewFile): void {
    event.stopPropagation();
    this.checkEvent.emit({file, shiftKey: event.shiftKey});
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

  isValidatable(): boolean {
    return this.activeAction == null && this.file().isValidatable;
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

  onValidate(file: ViewFile): void {
    this.activeAction = FileAction.VALIDATE;
    this.validateEvent.emit(file);
  }

  onDeleteLocal(file: ViewFile): void {
    if (this.confirmingDelete === 'local') {
      this.clearConfirmTimer();
      this.confirmingDelete = null;
      this.activeAction = FileAction.DELETE_LOCAL;
      this.deleteLocalEvent.emit(file);
    } else {
      this.setConfirming('local');
    }
  }

  onDeleteRemote(file: ViewFile): void {
    if (this.confirmingDelete === 'remote') {
      this.clearConfirmTimer();
      this.confirmingDelete = null;
      this.activeAction = FileAction.DELETE_REMOTE;
      this.deleteRemoteEvent.emit(file);
    } else {
      this.setConfirming('remote');
    }
  }

  private setConfirming(type: 'local' | 'remote'): void {
    this.clearConfirmTimer();
    this.confirmingDelete = type;
    this.confirmResetTimer = setTimeout(() => {
      this.confirmingDelete = null;
      this.confirmResetTimer = null;
      this.cdr.markForCheck();
    }, 3000);
  }

  private resetConfirmState(): void {
    this.clearConfirmTimer();
    this.confirmingDelete = null;
  }

  private clearConfirmTimer(): void {
    if (this.confirmResetTimer !== null) {
      clearTimeout(this.confirmResetTimer);
      this.confirmResetTimer = null;
    }
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
