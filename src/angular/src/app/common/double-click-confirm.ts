/**
 * Two-click confirmation: the first call arms `confirming` for `key`, the
 * second call within the timeout confirms. Arming auto-expires after
 * `timeoutMs`; `onExpire` runs then (call `cdr.markForCheck()` there under
 * OnPush, since the timeout fires outside change detection).
 */
export class DoubleClickConfirm<K> {
  confirming: K | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly onExpire: () => void, private readonly timeoutMs = 3000) {}

  /** Returns true when `key` was already armed (i.e. this is the confirming click). */
  confirm(key: K): boolean {
    if (this.confirming === key) {
      this.reset();
      return true;
    }
    this.reset();
    this.confirming = key;
    this.timer = setTimeout(() => {
      this.confirming = null;
      this.timer = null;
      this.onExpire();
    }, this.timeoutMs);
    return false;
  }

  /** Disarm and clear state. */
  reset(): void {
    this.clearTimer();
    this.confirming = null;
  }

  /** Stop the pending expiry without touching state (for ngOnDestroy). */
  clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
