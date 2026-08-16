import { Injectable, inject } from '@angular/core';
import { Observable, of, from } from 'rxjs';
import { mergeMap, toArray, tap, catchError } from 'rxjs/operators';

import { LoggerService } from '../utils/logger.service';
import { ModelFileService } from './model-file.service';
import { WebReaction } from '../utils/rest.service';
import { ModelFile } from '../../models/model-file';
import { ViewFile } from '../../models/view-file';
import { fileKey } from './file-key';
import { ViewFileSelectionService } from './view-file-selection.service';

function viewFileKey(vf: ViewFile): string {
  return fileKey(vf.pairId, vf.name);
}

/** Resolves a view-file key back to its backing {@link ModelFile}, or undefined. */
export type ModelFileResolver = (key: string) => ModelFile | undefined;

/**
 * Owns command dispatch (single + bulk) for view files.
 *
 * The command slice straddles two owners: it needs the diffing-owned snapshot
 * of model files (to resolve a {@link ViewFile} back to its {@link ModelFile})
 * AND the selection-owned checked state (for the bulk checked+capability
 * filter). Rather than duplicating either, this service is *input-driven*:
 *  - single dispatch takes a {@link ModelFileResolver} threaded in by the caller
 *    (so resolution semantics stay identical to the caller's authoritative
 *    snapshot — e.g. ViewFileService's `prevModelFiles`), and
 *  - bulk dispatch takes the current display-order view files threaded in by the
 *    caller, then filters them against {@link ViewFileSelectionService}'s checked
 *    set plus a per-action capability predicate.
 *
 * ViewFileService delegates its command/bulk methods here so consumers keep a
 * single facade while command logic lives in one focused place (issue #541).
 */
@Injectable({ providedIn: 'root' })
export class ViewFileCommandService {
  private readonly logger = inject(LoggerService);
  private readonly modelFileService = inject(ModelFileService);
  private readonly selection = inject(ViewFileSelectionService);

  queue(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Queue view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.queue(f));
  }

  stop(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Stop view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.stop(f));
  }

  extract(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Extract view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.extract(f));
  }

  deleteLocal(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Locally delete view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.deleteLocal(f));
  }

  deleteRemote(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Remotely delete view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.deleteRemote(f));
  }

  validate(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Validate view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.validate(f));
  }

  cleanupLocal(file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug('Clean up local-only contents of view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.cleanupLocal(f));
  }

  bulkQueue(files: readonly ViewFile[], resolve: ModelFileResolver): Observable<WebReaction[]> {
    return this.bulkAction(files, (f) => f.isQueueable, (f) => this.queue(f, resolve));
  }

  bulkStop(files: readonly ViewFile[], resolve: ModelFileResolver): Observable<WebReaction[]> {
    return this.bulkAction(files, (f) => f.isStoppable, (f) => this.stop(f, resolve));
  }

  bulkDeleteLocal(files: readonly ViewFile[], resolve: ModelFileResolver): Observable<WebReaction[]> {
    return this.bulkAction(files, (f) => f.isLocallyDeletable, (f) => this.deleteLocal(f, resolve), 4);
  }

  bulkDeleteRemote(files: readonly ViewFile[], resolve: ModelFileResolver): Observable<WebReaction[]> {
    return this.bulkAction(files, (f) => f.isRemotelyDeletable, (f) => this.deleteRemote(f, resolve), 4);
  }

  private bulkAction(
    files: readonly ViewFile[],
    filter: (f: ViewFile) => boolean,
    action: (f: ViewFile) => Observable<WebReaction>,
    concurrency = Infinity,
  ): Observable<WebReaction[]> {
    const checked = files.filter((f) => this.selection.isChecked(viewFileKey(f)) && filter(f));
    if (checked.length === 0) {
      return of([]);
    }
    return from(checked).pipe(
      mergeMap((f) => action(f), concurrency),
      toArray(),
    );
  }

  private createAction(
    file: ViewFile,
    resolve: ModelFileResolver,
    action: (file: ModelFile) => Observable<WebReaction>,
  ): Observable<WebReaction> {
    const key = viewFileKey(file);
    const modelFile = resolve(key);
    if (modelFile === undefined) {
      this.logger.error('File not found: ' + key);
      return of<WebReaction>({ success: false, data: null, errorMessage: `File '${file.name}' not found` });
    }
    // Return the inner observable's pipeline directly (no manual subscribe) so
    // the caller's subscription drives the request and unsubscribing cancels the
    // in-flight HTTP call. Errors are recovered in-pipeline into a failure
    // WebReaction so the returned observable never errors.
    return action(modelFile).pipe(
      tap((reaction) => this.logger.debug('Received model reaction: %O', reaction)),
      catchError((err) => {
        this.logger.error('Action failed for file: ' + key, err);
        return of<WebReaction>({ success: false, data: null, errorMessage: String(err?.message ?? err) });
      }),
    );
  }
}
