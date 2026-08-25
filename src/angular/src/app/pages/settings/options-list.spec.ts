import { describe, it, expect } from 'vitest';
import {
  FTPS_ONLY_NOTE,
  IOption,
  IOptionsContext,
  OVERRIDE_NOTE,
  OPTIONS_CONTEXT_AUTOQUEUE,
  OPTIONS_CONTEXT_FTPS,
  OPTIONS_CONTEXT_SERVER,
  OPTIONS_CONTEXT_VALIDATE,
  applyDisableRules,
  getConfigValue,
} from './options-list';
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

// --- applyDisableRules ---

const inactive = { pairsEnabled: false, validateDisabled: false, protocolSftp: false };
const buildServerContext = (hasEnabledPairs: boolean): IOptionsContext =>
  applyDisableRules(OPTIONS_CONTEXT_SERVER, { ...inactive, pairsEnabled: hasEnabledPairs });
const buildFtpsContext = (protocolIsSftp: boolean): IOptionsContext =>
  applyDisableRules(OPTIONS_CONTEXT_FTPS, { ...inactive, protocolSftp: protocolIsSftp });
const buildAutoqueueContext = (hasEnabledPairs: boolean): IOptionsContext =>
  applyDisableRules(OPTIONS_CONTEXT_AUTOQUEUE, { ...inactive, pairsEnabled: hasEnabledPairs });

describe('applyDisableRules: buildServerContext', () => {
  it('should disable remote_path and local_path when pairs are enabled', () => {
    const ctx = buildServerContext(true);
    const remotePath = ctx.options.find((o) => o.valuePath[1] === 'remote_path')!;
    const localPath = ctx.options.find((o) => o.valuePath[1] === 'local_path')!;

    expect(remotePath.disabled).toBe(true);
    expect(remotePath.description).toBe(OVERRIDE_NOTE);
    expect(localPath.disabled).toBe(true);
    expect(localPath.description).toBe(OVERRIDE_NOTE);
  });

  it('should not disable remote_path and local_path when no pairs are enabled', () => {
    const ctx = buildServerContext(false);
    const remotePath = ctx.options.find((o) => o.valuePath[1] === 'remote_path')!;
    const localPath = ctx.options.find((o) => o.valuePath[1] === 'local_path')!;

    expect(remotePath.disabled).toBeFalsy();
    expect(localPath.disabled).toBeFalsy();
  });

  it('should not disable other server options when pairs are enabled', () => {
    const ctx = buildServerContext(true);
    const others = ctx.options.filter(
      (o) => o.valuePath[1] !== 'remote_path' && o.valuePath[1] !== 'local_path',
    );

    for (const option of others) {
      expect(option.disabled).toBeFalsy();
    }
  });
});

describe('applyDisableRules: buildFtpsContext', () => {
  const ftpOnlyPaths = ['remote_ftp_port', 'ftp_ssl_verify_certificate'];

  it('disables the FTP-only options when the protocol is sftp', () => {
    const ctx = buildFtpsContext(true);
    for (const path of ftpOnlyPaths) {
      const option = ctx.options.find((o) => o.valuePath[1] === path)!;
      expect(option.disabled).toBe(true);
      expect(option.description).toBe(FTPS_ONLY_NOTE);
    }
  });

  it('enables the FTP-only options when the protocol is ftps', () => {
    const ctx = buildFtpsContext(false);
    for (const path of ftpOnlyPaths) {
      const option = ctx.options.find((o) => o.valuePath[1] === path)!;
      expect(option.disabled).toBeFalsy();
    }
  });

  it('never disables the protocol selector itself', () => {
    const protocol = buildFtpsContext(true).options.find((o) => o.valuePath[1] === 'protocol')!;
    expect(protocol.disabled).toBeFalsy();
  });
});

describe('applyDisableRules: buildAutoqueueContext', () => {
  it('should disable enabled checkbox when pairs are enabled', () => {
    const ctx = buildAutoqueueContext(true);
    const enabled = ctx.options.find((o) => o.valuePath[1] === 'enabled')!;

    expect(enabled.disabled).toBe(true);
    expect(enabled.description).toBe(OVERRIDE_NOTE);
  });

  it('should not disable enabled checkbox when no pairs are enabled', () => {
    const ctx = buildAutoqueueContext(false);
    const enabled = ctx.options.find((o) => o.valuePath[1] === 'enabled')!;

    expect(enabled.disabled).toBeFalsy();
  });

  it('should not disable other autoqueue options when pairs are enabled', () => {
    const ctx = buildAutoqueueContext(true);
    const others = ctx.options.filter((o) => o.valuePath[1] !== 'enabled');

    for (const option of others) {
      expect(option.disabled).toBeFalsy();
    }
  });
});

const buildValidateContext = (enabled: boolean): IOptionsContext =>
  applyDisableRules(OPTIONS_CONTEXT_VALIDATE, { ...inactive, validateDisabled: !enabled });

describe('applyDisableRules: buildValidateContext', () => {
  it('disables auto_validate and algorithm when validation is disabled', () => {
    const ctx = buildValidateContext(false);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;
    const algorithm = ctx.options.find((o) => o.valuePath[1] === 'algorithm')!;

    expect(autoValidate.disabled).toBe(true);
    expect(algorithm.disabled).toBe(true);
  });

  it('keeps the original description on disabled validate options (no override note)', () => {
    const ctx = buildValidateContext(false);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;

    // validateDisabled options carry no overrideNote, so the description is unchanged.
    expect(autoValidate.description).toBe(
      'Automatically validate files when download completes. Requires post-download validation above.',
    );
  });

  it('does not disable auto_validate and algorithm when validation is enabled', () => {
    const ctx = buildValidateContext(true);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;
    const algorithm = ctx.options.find((o) => o.valuePath[1] === 'algorithm')!;

    expect(autoValidate.disabled).toBeFalsy();
    expect(algorithm.disabled).toBeFalsy();
  });

  it('never disables the other validate options', () => {
    const ctx = buildValidateContext(false);
    const others = ctx.options.filter(
      (o) => o.valuePath[1] !== 'auto_validate' && o.valuePath[1] !== 'algorithm',
    );

    for (const option of others) {
      expect(option.disabled).toBeFalsy();
    }
  });
});
