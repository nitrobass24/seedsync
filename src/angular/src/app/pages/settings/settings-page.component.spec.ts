import '@angular/compiler';
import { describe, it, expect } from 'vitest';
import { SettingsPageComponent } from './settings-page.component';
import { OptionType } from './option.component';
import {
  IOptionsContext,
  OPTIONS_CONTEXT_INTEGRATIONS_SONARR,
  OPTIONS_CONTEXT_INTEGRATIONS_RADARR,
} from './options-list';

// Access private static methods for unit testing
const buildServerContext = (hasEnabledPairs: boolean): IOptionsContext =>
  (SettingsPageComponent as any).buildServerContext(hasEnabledPairs);
const buildAutoqueueContext = (hasEnabledPairs: boolean): IOptionsContext =>
  (SettingsPageComponent as any).buildAutoqueueContext(hasEnabledPairs);
const OVERRIDE_NOTE = (SettingsPageComponent as any).OVERRIDE_NOTE as string;

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

describe('Integrations options contexts', () => {
  it('Sonarr context should have correct options', () => {
    expect(OPTIONS_CONTEXT_INTEGRATIONS_SONARR.header).toBe('Sonarr');
    expect(OPTIONS_CONTEXT_INTEGRATIONS_SONARR.id).toBe('integrations-sonarr');
    const optionKeys = OPTIONS_CONTEXT_INTEGRATIONS_SONARR.options.map((o) => o.valuePath[1]);
    expect(optionKeys).toContain('sonarr_enabled');
    expect(optionKeys).toContain('sonarr_url');
    expect(optionKeys).toContain('sonarr_api_key');
  });

  it('Sonarr API key should be a Password field', () => {
    const apiKeyOption = OPTIONS_CONTEXT_INTEGRATIONS_SONARR.options.find(
      (o) => o.valuePath[1] === 'sonarr_api_key',
    )!;
    expect(apiKeyOption.type).toBe(OptionType.Password);
  });

  it('Radarr context should have correct options', () => {
    expect(OPTIONS_CONTEXT_INTEGRATIONS_RADARR.header).toBe('Radarr');
    expect(OPTIONS_CONTEXT_INTEGRATIONS_RADARR.id).toBe('integrations-radarr');
    const optionKeys = OPTIONS_CONTEXT_INTEGRATIONS_RADARR.options.map((o) => o.valuePath[1]);
    expect(optionKeys).toContain('radarr_enabled');
    expect(optionKeys).toContain('radarr_url');
    expect(optionKeys).toContain('radarr_api_key');
  });

  it('Radarr API key should be a Password field', () => {
    const apiKeyOption = OPTIONS_CONTEXT_INTEGRATIONS_RADARR.options.find(
      (o) => o.valuePath[1] === 'radarr_api_key',
    )!;
    expect(apiKeyOption.type).toBe(OptionType.Password);
  });

  it('all integrations options should reference the integrations section', () => {
    for (const opt of OPTIONS_CONTEXT_INTEGRATIONS_SONARR.options) {
      expect(opt.valuePath[0]).toBe('integrations');
    }
    for (const opt of OPTIONS_CONTEXT_INTEGRATIONS_RADARR.options) {
      expect(opt.valuePath[0]).toBe('integrations');
    }
  });
});
