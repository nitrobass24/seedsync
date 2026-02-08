import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { StreamEventHandler, StreamDispatchService } from '../base/stream-dispatch.service';
import { LoggerService } from '../utils/logger.service';
import { RestService, WebReaction } from '../utils/rest.service';
import { ModelFile, modelFileFromJson } from '../../models/model-file';

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
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    return this.restService.sendRequest('/server/command/queue/' + fileNameEncoded);
  }

  stop(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Stop model file: ' + file.name);
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    return this.restService.sendRequest('/server/command/stop/' + fileNameEncoded);
  }

  extract(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Extract model file: ' + file.name);
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    return this.restService.sendRequest('/server/command/extract/' + fileNameEncoded);
  }

  deleteLocal(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Delete locally model file: ' + file.name);
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    return this.restService.sendRequest('/server/command/delete_local/' + fileNameEncoded);
  }

  deleteRemote(file: ModelFile): Observable<WebReaction> {
    this.logger.debug('Delete remotely model file: ' + file.name);
    const fileNameEncoded = encodeURIComponent(encodeURIComponent(file.name));
    return this.restService.sendRequest('/server/command/delete_remote/' + fileNameEncoded);
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

    if (name === this.EVENT_INIT) {
      let t0: number;
      let t1: number;

      t0 = performance.now();
      const parsed: any[] = JSON.parse(data);
      t1 = performance.now();
      this.logger.debug('Parsing took', (t1 - t0).toFixed(0), 'ms');

      t0 = performance.now();
      const newMap = new Map<string, ModelFile>();
      for (const file of parsed) {
        const modelFile = modelFileFromJson(file);
        newMap.set(modelFile.name, modelFile);
      }
      t1 = performance.now();
      this.logger.debug('ModelFile map creation took', (t1 - t0).toFixed(0), 'ms');

      this.filesSubject.next(newMap);
    } else if (name === this.EVENT_ADDED) {
      const parsed: { new_file: any } = JSON.parse(data);
      const file = modelFileFromJson(parsed.new_file);
      if (currentFiles.has(file.name)) {
        this.logger.error('ModelFile named ' + file.name + ' already exists');
      } else {
        const updated = new Map(currentFiles);
        updated.set(file.name, file);
        this.filesSubject.next(updated);
        this.logger.debug('Added file: %O', file);
      }
    } else if (name === this.EVENT_REMOVED) {
      const parsed: { old_file: any } = JSON.parse(data);
      const file = modelFileFromJson(parsed.old_file);
      if (currentFiles.has(file.name)) {
        const updated = new Map(currentFiles);
        updated.delete(file.name);
        this.filesSubject.next(updated);
        this.logger.debug('Removed file: %O', file);
      } else {
        this.logger.error('Failed to find ModelFile named ' + file.name);
      }
    } else if (name === this.EVENT_UPDATED) {
      const parsed: { new_file: any } = JSON.parse(data);
      const file = modelFileFromJson(parsed.new_file);
      if (currentFiles.has(file.name)) {
        const updated = new Map(currentFiles);
        updated.set(file.name, file);
        this.filesSubject.next(updated);
        this.logger.debug('Updated file: %O', file);
      } else {
        this.logger.error('Failed to find ModelFile named ' + file.name);
      }
    } else {
      this.logger.error('Unrecognized event:', name);
    }
  }
}
