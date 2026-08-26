import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { PathPair } from '../../models/path-pair';
import { CollectionService } from './collection.service';

@Injectable({ providedIn: 'root' })
export class PathPairsService extends CollectionService<PathPair> {
  readonly pairs$: Observable<PathPair[]> = this.items$;

  constructor() {
    super('/server/pathpairs', 'path pair', true);
  }

  create(pair: Omit<PathPair, 'id'>): Observable<PathPair | null> {
    return this.createItem(pair);
  }

  update(pair: PathPair): Observable<PathPair | null> {
    return this.updateItem(pair.id, pair);
  }

  remove(pairId: string): Observable<boolean> {
    return this.removeItem(pairId);
  }
}
