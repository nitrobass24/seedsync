import { Component, ChangeDetectionStrategy, input, output } from '@angular/core';

@Component({
    selector: 'app-bulk-action-bar',
    standalone: true,
    template: `
        <div class="bulk-bar">
            <span class="count">{{ count() }} selected</span>
            <button class="btn btn-sm btn-outline-primary" (click)="queueEvent.emit()">Queue</button>
            <button class="btn btn-sm btn-outline-warning" (click)="stopEvent.emit()">Stop</button>
            <button class="btn btn-sm btn-outline-danger" (click)="deleteLocalEvent.emit()">Delete Local</button>
            <button class="btn btn-sm btn-outline-danger" (click)="deleteRemoteEvent.emit()">Delete Remote</button>
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
    `],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class BulkActionBarComponent {
    count = input.required<number>();

    queueEvent = output<void>();
    stopEvent = output<void>();
    deleteLocalEvent = output<void>();
    deleteRemoteEvent = output<void>();
    clearEvent = output<void>();
}
