import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class DomService {
  private readonly headerHeightSubject = new BehaviorSubject<number>(0);

  readonly headerHeight$: Observable<number> =
    this.headerHeightSubject.asObservable();

  setHeaderHeight(height: number): void {
    if (height !== this.headerHeightSubject.getValue()) {
      this.headerHeightSubject.next(height);
    }
  }
}
