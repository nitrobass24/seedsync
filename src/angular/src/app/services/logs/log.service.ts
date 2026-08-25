import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LoggerService } from '../utils/logger.service';
import { LogRecord, logRecordFromJson } from '../../models/log-record';

export interface LogHistoryParams {
    search?: string;
    level?: string;
    limit?: number;
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
    private readonly logger = inject(LoggerService);

    private readonly logsSubject = new Subject<LogRecord>();

    readonly logs$: Observable<LogRecord> = this.logsSubject.asObservable();

    constructor() {
        this.streamDispatch.registerHandler(this);
    }

    getEventNames(): string[] {
        return ['log-record'];
    }

    onEvent(_eventName: string, data: string): void {
        // Guard the parse of server-controlled SSE payloads: a malformed/truncated
        // event must not throw inside the listener callback. Log and skip the bad
        // record, emitting nothing (mirrors ConfigService.getConfig).
        try {
            this.logsSubject.next(logRecordFromJson(JSON.parse(data)));
        } catch (e) {
            this.logger.error('Failed to parse log-record event: %O', e);
        }
    }

    fetchHistory(params: LogHistoryParams = {}): Observable<LogHistoryEntry[]> {
        let httpParams = new HttpParams();
        for (const [key, value] of Object.entries(params)) {
            if (value) httpParams = httpParams.set(key, String(value));
        }
        return this.http.get<LogHistoryEntry[]>('/server/logs', { params: httpParams });
    }
}
