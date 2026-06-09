import '@angular/compiler';
import { describe, it, expect } from 'vitest';
import { SettingsPageComponent } from './settings-page.component';
import { FTPS_ONLY_NOTE, IOptionsContext } from './options-list';

interface SettingsPageStatics {
  buildServerContext(hasEnabledPairs: boolean, protocolIsSftp: boolean): IOptionsContext;
  buildAutoqueueContext(hasEnabledPairs: boolean): IOptionsContext;
  OVERRIDE_NOTE: string;
}
const settingsStatics = SettingsPageComponent as unknown as SettingsPageStatics;
// protocolIsSftp defaults to false (ftps) so the pre-existing pairs-greying
// tests below see the FTP-only options enabled and unaffected.
const buildServerContext = (hasEnabledPairs: boolean, protocolIsSftp = false): IOptionsContext =>
  settingsStatics.buildServerContext(hasEnabledPairs, protocolIsSftp);
const buildAutoqueueContext = (hasEnabledPairs: boolean): IOptionsContext =>
  settingsStatics.buildAutoqueueContext(hasEnabledPairs);
const OVERRIDE_NOTE = settingsStatics.OVERRIDE_NOTE;

describe('SettingsPageComponent.buildServerContext', () => {
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

describe('SettingsPageComponent.buildServerContext FTPS greying', () => {
  const ftpOnlyPaths = ['remote_ftp_port', 'ftp_ssl_verify_certificate'];

  it('disables the FTP-only options when the protocol is sftp', () => {
    const ctx = buildServerContext(false, true);
    for (const path of ftpOnlyPaths) {
      const option = ctx.options.find((o) => o.valuePath[1] === path)!;
      expect(option.disabled).toBe(true);
      expect(option.description).toBe(FTPS_ONLY_NOTE);
    }
  });

  it('enables the FTP-only options when the protocol is ftps', () => {
    const ctx = buildServerContext(false, false);
    for (const path of ftpOnlyPaths) {
      const option = ctx.options.find((o) => o.valuePath[1] === path)!;
      expect(option.disabled).toBeFalsy();
    }
  });

  it('never disables the protocol selector itself', () => {
    const protocol = buildServerContext(false, true).options.find((o) => o.valuePath[1] === 'protocol')!;
    expect(protocol.disabled).toBeFalsy();
  });
});

describe('SettingsPageComponent.buildAutoqueueContext', () => {
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
