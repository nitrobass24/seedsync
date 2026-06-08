import { describe, it, expect } from 'vitest';
import { getConfigValue } from './options-list';
import { Config, DEFAULT_CONFIG } from '../../models/config';

describe('getConfigValue', () => {
  const config: Config = {
    ...DEFAULT_CONFIG,
    lftp: { ...DEFAULT_CONFIG.lftp, remote_path: '/remote', remote_port: 22 },
    web: { ...DEFAULT_CONFIG.web, api_key: 'secret' },
  };

  it('reads a string field by typed path', () => {
    expect(getConfigValue(config, ['lftp', 'remote_path'])).toBe('/remote');
  });

  it('reads a numeric field by typed path', () => {
    expect(getConfigValue(config, ['lftp', 'remote_port'])).toBe(22);
  });

  it('reads a field from another section', () => {
    expect(getConfigValue(config, ['web', 'api_key'])).toBe('secret');
  });

  it('returns null for a field whose value is null', () => {
    expect(getConfigValue(config, ['lftp', 'local_path'])).toBeNull();
  });
});
