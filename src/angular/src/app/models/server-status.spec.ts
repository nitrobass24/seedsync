import { describe, it, expect } from 'vitest';
import { serverStatusFromJson, ServerStatusJson } from './server-status';

describe('serverStatusFromJson', () => {
  function makeJson(overrides: Partial<ServerStatusJson> = {}): ServerStatusJson {
    return {
      server: { up: true, error_msg: '' },
      controller: {
        latest_local_scan_time: null,
        latest_remote_scan_time: null,
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
      },
      ...overrides,
    };
  }

  it('should map error_msg to errorMessage and snake_case to camelCase', () => {
    const json = makeJson({
      server: { up: false, error_msg: 'Connection refused' },
      controller: {
        latest_local_scan_time: null,
        latest_remote_scan_time: null,
        latest_remote_scan_failed: true,
        latest_remote_scan_error: 'Timeout',
      },
    });

    const result = serverStatusFromJson(json);

    expect(result.server.up).toBe(false);
    expect(result.server.errorMessage).toBe('Connection refused');
    expect(result.controller.latestRemoteScanFailed).toBe(true);
    expect(result.controller.latestRemoteScanError).toBe('Timeout');
  });

  it('should convert timestamps from seconds to milliseconds', () => {
    const json = makeJson({
      controller: {
        latest_local_scan_time: '1700000000',
        latest_remote_scan_time: '1700000100',
        latest_remote_scan_failed: false,
        latest_remote_scan_error: null,
      },
    });

    const result = serverStatusFromJson(json);

    expect(result.controller.latestLocalScanTime).toEqual(new Date(1700000000 * 1000));
    expect(result.controller.latestRemoteScanTime).toEqual(new Date(1700000100 * 1000));
  });

  it('should handle null timestamps', () => {
    const result = serverStatusFromJson(makeJson());

    expect(result.controller.latestLocalScanTime).toBeNull();
    expect(result.controller.latestRemoteScanTime).toBeNull();
  });
});
