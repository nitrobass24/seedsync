import {
  Component, ChangeDetectionStrategy, ChangeDetectorRef, OnChanges, OnDestroy, SimpleChanges,
  ViewChild, ElementRef, input, output, inject
} from '@angular/core';
import { AsyncPipe, DatePipe } from '@angular/common';

import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileOptions } from '../../models/view-file-options';
import { FileAction, FILE_ACTIONS } from '../../models/file-action';
import { FileSizePipe } from '../../common/file-size.pipe';
import { EtaPipe } from '../../common/eta.pipe';
import { CapitalizePipe } from '../../common/capitalize.pipe';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';
import { DoubleClickConfirm } from '../../common/double-click-confirm';
import { Observable } from 'rxjs';

// Payload emitted for each single-file action. Carries the action, the target
// file, plus a callback the parent invokes to clear this child's activeAction
// when the backend rejects the request — the file model never changes on
// failure, so ngOnChanges cannot recover the row on its own. The callback is
// necessary because <app-file> is rendered inside *cdkVirtualFor, which
// recycles instances and prevents the parent from keying a @ViewChildren to a
// file.
export interface FileActionEvent {
  action: FileAction;
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
  actionEvent = output<FileActionEvent>();

  activeAction: FileAction | null = null;

  // Inline double-click delete confirmation state
  private readonly deleteConfirm = new DoubleClickConfirm<'local' | 'remote'>(() => this.cdr.markForCheck());

  get confirmingDelete(): 'local' | 'remote' | null {
    return this.deleteConfirm.confirming;
  }

  ngOnChanges(changes: SimpleChanges): void {
    const fileChange = changes['file'];
    if (fileChange) {
      const oldFile: ViewFile | undefined = fileChange.previousValue;
      const newFile: ViewFile | undefined = fileChange.currentValue;
      if (oldFile != null && newFile != null) {
        if (oldFile.pairId !== newFile.pairId || oldFile.name !== newFile.name) {
          this.activeAction = null;
          this.deleteConfirm.reset();
        } else if (oldFile.status !== newFile.status) {
          this.activeAction = null;
          this.deleteConfirm.reset();
        } else if (this.activeAction === FileAction.DELETE_REMOTE &&
                   oldFile.isRemotelyDeletable && !newFile.isRemotelyDeletable) {
          this.activeAction = null;
          this.deleteConfirm.reset();
        } else if (this.activeAction === FileAction.DELETE_LOCAL &&
                   oldFile.isLocallyDeletable && !newFile.isLocallyDeletable) {
          this.activeAction = null;
          this.deleteConfirm.reset();
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
    this.deleteConfirm.clearTimer();
  }

  onCheck(event: Event, file: ViewFile): void {
    event.stopPropagation();
    const shiftKey = (event as MouseEvent | KeyboardEvent).shiftKey ?? false;
    this.checkEvent.emit({file, shiftKey});
  }

  canDo(action: FileAction): boolean {
    return this.activeAction == null && FILE_ACTIONS[action].isAllowed(this.file());
  }

  // Cleared by the parent when an action's backend request fails or errors.
  // Runs inside the parent's async subscribe callback, so OnPush needs an
  // explicit markForCheck to re-enable the buttons and stop the spinner.
  // <app-file> is recycled by *cdkVirtualFor, so a late failure callback may
  // target an instance now bound to a different file/action; only clear when
  // this instance still represents the same file and the same in-flight action.
  clearActiveAction(forFile?: ViewFile, forAction?: FileAction | null): void {
    if (forFile !== undefined) {
      const current = this.file();
      if (
        current.pairId !== forFile.pairId ||
        current.name !== forFile.name ||
        this.activeAction !== forAction
      ) {
        return;
      }
    }
    this.activeAction = null;
    this.cdr.markForCheck();
  }

  onAction(action: FileAction, file: ViewFile): void {
    if (action === FileAction.DELETE_LOCAL && !this.deleteConfirm.confirm('local')) {
      return;
    }
    if (action === FileAction.DELETE_REMOTE && !this.deleteConfirm.confirm('remote')) {
      return;
    }
    this.activeAction = action;
    this.actionEvent.emit({ action, file, clearActiveAction: () => this.clearActiveAction(file, action) });
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
