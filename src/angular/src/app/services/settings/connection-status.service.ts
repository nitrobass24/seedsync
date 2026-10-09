import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Shares whether the configured lftp connection has been verified (via the
 * Server section's "Test Connection" button, or the silent auto-check on
 * settings load) across the Settings page and its child components — e.g.
 * Path Pairs, whose remote_path field needs the same server-directory-picker
 * gate as the top-level Server Directory field.
 */
@Injectable({ providedIn: 'root' })
export class ConnectionStatusService {
  private readonly verifiedSubject = new BehaviorSubject<boolean>(false);
  readonly verified$: Observable<boolean> = this.verifiedSubject.asObservable();

  /** True after a Test Connection fails with a bad-credential error. Held
   * here rather than on the Settings page so it survives navigating away and
   * back: otherwise each revisit's silent probe is one more failed login. */
  lockedOut = false;

  setVerified(verified: boolean): void {
    this.verifiedSubject.next(verified);
  }
}
