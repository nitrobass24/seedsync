import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LogRecord, logRecordFromJson } from '../../models/log-record';

export interface LogHistoryParams {
    search?: string;
    level?: string;
    limit?: number;
    before?: number;
}

export interface LogHistoryEntry {
    timestamp: string;
    level: string;
    logger: string;
    process: string;
    thread: string;
    message: string;
}

@Injectable({ providedIn: 'root' })
export class LogService implements StreamEventHandler {
    private readonly streamDispatch = inject(StreamDispatchService);
    private readonly http = inject(HttpClient);

    private readonly logsSubject = new Subject<LogRecord>();

    readonly logs$: Observable<LogRecord> = this.logsSubject.asObservable();

    constructor() {
        this.streamDispatch.registerHandler(this);
    }

    getEventNames(): string[] {
        return ['log-record'];
    }

    onEvent(_eventName: string, data: string): void {
        this.logsSubject.next(logRecordFromJson(JSON.parse(data)));
    }

    onConnected(): void {}

    onDisconnected(): void {}

    fetchHistory(params: LogHistoryParams = {}): Observable<LogHistoryEntry[]> {
        const queryParts: string[] = [];
        if (params.search) queryParts.push(`search=${encodeURIComponent(params.search)}`);
        if (params.level) queryParts.push(`level=${encodeURIComponent(params.level)}`);
        if (params.limit) queryParts.push(`limit=${params.limit}`);
        if (params.before) queryParts.push(`before=${params.before}`);
        const qs = queryParts.length > 0 ? '?' + queryParts.join('&') : '';
        return this.http.get<LogHistoryEntry[]>(`/server/logs${qs}`);
    }
}
