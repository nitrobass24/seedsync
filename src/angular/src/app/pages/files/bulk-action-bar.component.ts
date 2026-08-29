import {
    Component, ChangeDetectionStrategy, ChangeDetectorRef, OnDestroy, input, output, inject
} from '@angular/core';
import { DoubleClickConfirm } from '../../common/double-click-confirm';
import { FileAction } from '../../models/file-action';

@Component({
    selector: 'app-bulk-action-bar',
    standalone: true,
    template: `
        <div class="bulk-bar">
            <span class="count">{{ count() }} selected</span>
            <button class="btn btn-sm btn-outline-primary" (click)="actionEvent.emit(FileAction.QUEUE)">Queue</button>
            <button class="btn btn-sm btn-outline-warning" (click)="actionEvent.emit(FileAction.STOP)">Stop</button>
            <button class="btn btn-sm btn-outline-danger"
                    [class.confirming]="confirmingDelete === 'local'"
                    (click)="onDeleteLocal()">
                {{ confirmingDelete === 'local' ? 'Confirm?' : 'Delete Local' }}
            </button>
            <button class="btn btn-sm btn-outline-danger"
                    [class.confirming]="confirmingDelete === 'remote'"
                    (click)="onDeleteRemote()">
                {{ confirmingDelete === 'remote' ? 'Confirm?' : 'Delete Remote' }}
            </button>
            <button class="btn btn-sm btn-outline-secondary" (click)="clearEvent.emit()">Clear</button>
        </div>
    `,
    styles: [`
        .bulk-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background-color: var(--ss-secondary);
            border-bottom: 1px solid var(--ss-border);
        }
        .count {
            font-weight: bold;
            margin-right: 8px;
        }
        .btn.confirming {
            background-color: var(--bs-danger);
            color: #fff;
        }
    `],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class BulkActionBarComponent implements OnDestroy {
    private readonly cdr = inject(ChangeDetectorRef);
    FileAction = FileAction;

    count = input.required<number>();

    actionEvent = output<FileAction>();
    clearEvent = output<void>();

    private readonly deleteConfirm = new DoubleClickConfirm<'local' | 'remote'>(() => this.cdr.markForCheck());

    get confirmingDelete(): 'local' | 'remote' | null {
        return this.deleteConfirm.confirming;
    }

    ngOnDestroy(): void {
        this.deleteConfirm.clearTimer();
    }

    onDeleteLocal(): void {
        if (this.deleteConfirm.confirm('local')) {
            this.actionEvent.emit(FileAction.DELETE_LOCAL);
        }
    }

    onDeleteRemote(): void {
        if (this.deleteConfirm.confirm('remote')) {
            this.actionEvent.emit(FileAction.DELETE_REMOTE);
        }
    }
}
