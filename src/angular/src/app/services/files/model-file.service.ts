import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { ModelFile, ModelFileJson, modelFileFromJson } from '../../models/model-file';
import { fileKey } from './file-key';

@Injectable({ providedIn: 'root' })
export class ModelFileService implements StreamEventHandler {
  private readonly EVENT_INIT = 'model-init';
  private readonly EVENT_ADDED = 'model-added';
  private readonly EVENT_UPDATED = 'model-updated';
  private readonly EVENT_REMOVED = 'model-removed';

  private readonly logger = inject(LoggerService);
  private readonly restService = inject(RestService);
  private readonly streamDispatch = inject(StreamDispatchService);

  private readonly filesSubject = new BehaviorSubject<Map<string, ModelFile>>(new Map());

  readonly files$: Observable<Map<string, ModelFile>> = this.filesSubject.asObservable();

  constructor() {
    this.streamDispatch.registerHandler(this);
  }

  getEventNames(): string[] {
    return [this.EVENT_INIT, this.EVENT_ADDED, this.EVENT_UPDATED, this.EVENT_REMOVED];
  }

  queue(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Queue model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('queue', file));
  }

  stop(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Stop model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('stop', file));
  }

  extract(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Extract model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('extract', file));
  }

  deleteLocal(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Delete locally model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('delete_local', file));
  }

  deleteRemote(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Delete remotely model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('delete_remote', file));
  }

  validate(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Validate model file: ' + file.name);
    return this.restService.sendRequest(this.commandUrl('validate', file));
  }

  private commandUrl(action: string, file: ModelFile): string {
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    let url = `/server/command/${action}/${fileNameEncoded}`;
    if (file.pair_id) {
      url += `?pair_id=${encodeURIComponent(file.pair_id)}`;
    }
    return url;
  }

  onEvent(eventName: string, data: string): void {
    this.parseEvent(eventName, data);
  }

  onConnected(): void {
    // nothing to do
  }

  onDisconnected(): void {
    this.filesSubject.next(new Map());
  }

  private parseEvent(name: string, data: string): void {
    const currentFiles = this.filesSubject.getValue();

    // Guard the parse of server-controlled SSE payloads: a malformed/truncated
    // event must not throw inside the listener callback. Log and skip the bad
    // event, leaving existing state untouched (mirrors ConfigService.getConfig).
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch (e) {
      this.logger.error('Failed to parse %s event: %O', name, e);
      return;
    }

    // The payload parsed, but a valid-JSON-but-wrong-shape event (e.g. model-init
    // not an array, or model-added missing new_file) would throw in the mapping
    // below; guard the dispatch too so one bad event is logged and skipped, not
    // fatal to the listener.
    try {
      if (name === this.EVENT_INIT) {
        const init = parsed as ModelFileJson[];
        const t0 = performance.now();
        const newMap = new Map<string, ModelFile>();
        for (const file of init) {
          const modelFile = modelFileFromJson(file);
          newMap.set(fileKey(modelFile.pair_id, modelFile.name), modelFile);
        }
        const t1 = performance.now();
        this.logger.debug('ModelFile map creation took', (t1 - t0).toFixed(0), 'ms');

        this.filesSubject.next(newMap);
      } else if (name === this.EVENT_ADDED) {
        const added = parsed as { new_file: ModelFileJson };
        const file = modelFileFromJson(added.new_file);
        const key = fileKey(file.pair_id, file.name);
        if (currentFiles.has(key)) {
          this.logger.error('ModelFile named ' + key + ' already exists');
        } else {
          const updated = new Map(currentFiles);
          updated.set(key, file);
          this.filesSubject.next(updated);
          this.logger.debug('Added file: %O', file);
        }
      } else if (name === this.EVENT_REMOVED) {
        const removed = parsed as { old_file: ModelFileJson };
        const file = modelFileFromJson(removed.old_file);
        const key = fileKey(file.pair_id, file.name);
        if (currentFiles.has(key)) {
          const updated = new Map(currentFiles);
          updated.delete(key);
          this.filesSubject.next(updated);
          this.logger.debug('Removed file: %O', file);
        } else {
          this.logger.error('Failed to find ModelFile named ' + key);
        }
      } else if (name === this.EVENT_UPDATED) {
        const updatedFile = parsed as { new_file: ModelFileJson };
        const file = modelFileFromJson(updatedFile.new_file);
        const key = fileKey(file.pair_id, file.name);
        if (currentFiles.has(key)) {
          const updated = new Map(currentFiles);
          updated.set(key, file);
          this.filesSubject.next(updated);
          this.logger.debug('Updated file: %O', file);
        } else {
          this.logger.error('Failed to find ModelFile named ' + key);
        }
      } else {
        this.logger.error('Unrecognized event:', name);
      }
    } catch (e) {
      this.logger.error('Failed to handle %s event (unexpected shape): %O', name, e);
    }
  }
}
