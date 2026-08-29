import { Injectable, inject } from '@angular/core';
import { Observable, of, from } from 'rxjs';
import { mergeMap, toArray, tap, catchError } from 'rxjs/operators';

import { LoggerService } from '../utils/logger.service';
import { ModelFileService } from './model-file.service';
import { WebReaction } from '../utils/rest.service';
import { ModelFile } from '../../models/model-file';
import { ViewFile } from '../../models/view-file';
import { FileAction, FILE_ACTIONS } from '../../models/file-action';
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

  command(action: FileAction, file: ViewFile, resolve: ModelFileResolver): Observable<WebReaction> {
    this.logger.debug(FILE_ACTIONS[action].logNoun + ' view file: ' + file.name);
    return this.createAction(file, resolve, (f) => this.modelFileService.command(action, f));
  }

  bulk(action: FileAction, files: readonly ViewFile[], resolve: ModelFileResolver): Observable<WebReaction[]> {
    const spec = FILE_ACTIONS[action];
    const checked = files.filter((f) => this.selection.isChecked(viewFileKey(f)) && spec.isAllowed(f));
    if (checked.length === 0) {
      return of([]);
    }
    return from(checked).pipe(
      mergeMap((f) => this.command(action, f, resolve), spec.bulkConcurrency),
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
