import {
    Component, ChangeDetectionStrategy, ChangeDetectorRef, OnDestroy, input, output, inject
} from '@angular/core';

@Component({
    selector: 'app-bulk-action-bar',
    standalone: true,
    template: `
        <div class="bulk-bar">
            <span class="count">{{ count() }} selected</span>
            <button class="btn btn-sm btn-outline-primary" (click)="queueEvent.emit()">Queue</button>
            <button class="btn btn-sm btn-outline-warning" (click)="stopEvent.emit()">Stop</button>
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

    count = input.required<number>();

    queueEvent = output<void>();
    stopEvent = output<void>();
    deleteLocalEvent = output<void>();
    deleteRemoteEvent = output<void>();
    clearEvent = output<void>();

    // Inline double-click delete confirmation state
    confirmingDelete: 'local' | 'remote' | null = null;
    private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

    ngOnDestroy(): void {
        this.clearConfirmTimer();
    }

    onDeleteLocal(): void {
        if (this.confirmingDelete === 'local') {
            this.clearConfirmTimer();
            this.confirmingDelete = null;
            this.deleteLocalEvent.emit();
        } else {
            this.setConfirming('local');
        }
    }

    onDeleteRemote(): void {
        if (this.confirmingDelete === 'remote') {
            this.clearConfirmTimer();
            this.confirmingDelete = null;
            this.deleteRemoteEvent.emit();
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

    private clearConfirmTimer(): void {
        if (this.confirmResetTimer !== null) {
            clearTimeout(this.confirmResetTimer);
            this.confirmResetTimer = null;
        }
    }
}
