import { describe, it, expect } from 'vitest';

import { ConnectionStatusService } from './connection-status.service';

describe('ConnectionStatusService', () => {
  it('defaults to unverified', () => {
    const service = new ConnectionStatusService();
    let latest: boolean | undefined;
    service.verified$.subscribe((v) => (latest = v));

    expect(latest).toBe(false);
  });

  it('emits the latest value to new and existing subscribers', () => {
    const service = new ConnectionStatusService();
    const seen: boolean[] = [];
    service.verified$.subscribe((v) => seen.push(v));

    service.setVerified(true);
    service.setVerified(false);

    expect(seen).toEqual([false, true, false]);
  });

  it('replays the current value to a late subscriber', () => {
    const service = new ConnectionStatusService();
    service.setVerified(true);

    let latest: boolean | undefined;
    service.verified$.subscribe((v) => (latest = v));

    expect(latest).toBe(true);
  });
});
