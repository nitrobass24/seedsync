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

// Payload emitted for each single-file action. Carries the target file plus a
// callback the parent invokes to clear this child's activeAction when the
// backend rejects the request — the file model never changes on failure, so
// ngOnChanges cannot recover the row on its own. The callback is necessary
// because <app-file> is rendered inside *cdkVirtualFor, which recycles
// instances and prevents the parent from keying a @ViewChildren to a file.
export interface FileActionEvent {
  file: ViewFile;
  clearActiveAction: () => void;
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
  queueEvent = output<FileActionEvent>();
  stopEvent = output<FileActionEvent>();
  extractEvent = output<FileActionEvent>();
  deleteLocalEvent = output<FileActionEvent>();
  validateEvent = output<FileActionEvent>();
  deleteRemoteEvent = output<FileActionEvent>();

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
        } else if (this.activeAction === FileAction.VALIDATE &&
                   oldFile.isValidatable && !newFile.isValidatable) {
          this.activeAction = null;
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

  onCheck(event: Event, file: ViewFile): void {
    event.stopPropagation();
    const shiftKey = (event as MouseEvent | KeyboardEvent).shiftKey ?? false;
    this.checkEvent.emit({file, shiftKey});
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

  // Cleared by the parent when an action's backend request fails or errors.
  // Runs inside the parent's async subscribe callback, so OnPush needs an
  // explicit markForCheck to re-enable the buttons and stop the spinner.
  clearActiveAction(): void {
    this.activeAction = null;
    this.cdr.markForCheck();
  }

  private actionEvent(file: ViewFile): FileActionEvent {
    return { file, clearActiveAction: () => this.clearActiveAction() };
  }

  onQueue(file: ViewFile): void {
    this.activeAction = FileAction.QUEUE;
    this.queueEvent.emit(this.actionEvent(file));
  }

  onStop(file: ViewFile): void {
    this.activeAction = FileAction.STOP;
    this.stopEvent.emit(this.actionEvent(file));
  }

  onExtract(file: ViewFile): void {
    this.activeAction = FileAction.EXTRACT;
    this.extractEvent.emit(this.actionEvent(file));
  }

  onValidate(file: ViewFile): void {
    this.activeAction = FileAction.VALIDATE;
    this.validateEvent.emit(this.actionEvent(file));
  }

  onDeleteLocal(file: ViewFile): void {
    if (this.confirmingDelete === 'local') {
      this.clearConfirmTimer();
      this.confirmingDelete = null;
      this.activeAction = FileAction.DELETE_LOCAL;
      this.deleteLocalEvent.emit(this.actionEvent(file));
    } else {
      this.setConfirming('local');
    }
  }

  onDeleteRemote(file: ViewFile): void {
    if (this.confirmingDelete === 'remote') {
      this.clearConfirmTimer();
      this.confirmingDelete = null;
      this.activeAction = FileAction.DELETE_REMOTE;
      this.deleteRemoteEvent.emit(this.actionEvent(file));
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
