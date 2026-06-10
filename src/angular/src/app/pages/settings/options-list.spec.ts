import { describe, it, expect } from 'vitest';
import { getConfigValue, OPTIONS_CONTEXT_FTPS, IOption } from './options-list';
import { OptionType } from './option.component';
import { Config, DEFAULT_CONFIG } from '../../models/config';

function findFtpsOption(section: string, option: string): IOption {
  const found = OPTIONS_CONTEXT_FTPS.options.find(
    (o) => o.valuePath[0] === section && o.valuePath[1] === option,
  );
  expect(found).toBeDefined();
  return found as IOption;
}

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

describe('OPTIONS_CONTEXT_FTPS options', () => {
  it('renders the transfer protocol as a Select of sftp/ftps requiring restart', () => {
    const protocol = findFtpsOption('lftp', 'protocol');
    expect(protocol.type).toBe(OptionType.Select);
    expect(protocol.choices).toEqual(['sftp', 'ftps']);
    expect(protocol.requiresRestart).toBe(true);
  });

  it('renders Remote FTP Port as a text field requiring restart', () => {
    const port = findFtpsOption('lftp', 'remote_ftp_port');
    expect(port.type).toBe(OptionType.Text);
    expect(port.label).toBe('Remote FTP Port');
    expect(port.requiresRestart).toBe(true);
  });

  it('renders the FTPS certificate verification as a Checkbox requiring restart', () => {
    const verify = findFtpsOption('lftp', 'ftp_ssl_verify_certificate');
    expect(verify.type).toBe(OptionType.Checkbox);
    expect(verify.requiresRestart).toBe(true);
  });
});
