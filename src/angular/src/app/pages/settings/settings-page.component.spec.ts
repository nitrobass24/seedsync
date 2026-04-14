import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BehaviorSubject, of } from 'rxjs';
import { SettingsPageComponent } from './settings-page.component';
import { OptionType } from './option.component';
import { LoggerService } from '../../services/utils/logger.service';
import { ConfigService } from '../../services/settings/config.service';
import { IntegrationsService, TestConnectionResult } from '../../services/settings/integrations.service';
import { NotificationService } from '../../services/utils/notification.service';
import { ServerCommandService } from '../../services/server/server-command.service';
import { ConnectedService } from '../../services/utils/connected.service';
import { PathPairsService } from '../../services/settings/path-pairs.service';
import { Config, DEFAULT_CONFIG } from '../../models/config';
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

describe('SettingsPageComponent integration tests', () => {
  let fixture: ComponentFixture<SettingsPageComponent>;
  let component: SettingsPageComponent;
  let configSubject: BehaviorSubject<Config | null>;
  let connectedSubject: BehaviorSubject<boolean>;
  let pairsSubject: BehaviorSubject<any[]>;
  let mockIntegrationsService: { testSonarr: ReturnType<typeof vi.fn>; testRadarr: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    configSubject = new BehaviorSubject<Config | null>({ ...DEFAULT_CONFIG });
    connectedSubject = new BehaviorSubject<boolean>(true);
    pairsSubject = new BehaviorSubject<any[]>([]);
    mockIntegrationsService = {
      testSonarr: vi.fn(),
      testRadarr: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [SettingsPageComponent],
      providers: [
        { provide: LoggerService, useValue: { info: vi.fn(), error: vi.fn(), debug: vi.fn(), warn: vi.fn() } },
        { provide: ConfigService, useValue: { config$: configSubject.asObservable(), set: vi.fn(() => of({ success: true, data: 'ok', errorMessage: null })) } },
        { provide: IntegrationsService, useValue: mockIntegrationsService },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: connectedSubject.asObservable() } },
        { provide: PathPairsService, useValue: { pairs$: pairsSubject.asObservable() } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should render Integrations card with Sonarr and Radarr headings', () => {
    const el = fixture.nativeElement as HTMLElement;
    const headings = Array.from(el.querySelectorAll('h5')).map((h) => h.textContent?.trim());
    expect(headings).toContain('Sonarr');
    expect(headings).toContain('Radarr');
  });

  it('should render test connection buttons with type="button"', () => {
    const el = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(el.querySelectorAll('.test-connection button'));
    expect(buttons.length).toBe(2);
    for (const btn of buttons) {
      expect(btn.getAttribute('type')).toBe('button');
    }
  });

  it('should call integrationsService.testSonarr on Sonarr test button click', () => {
    const successResult: TestConnectionResult = { success: true, message: 'Sonarr connected (v4.0.0)' };
    mockIntegrationsService.testSonarr.mockReturnValue(of(successResult));

    component.onTestSonarr();
    fixture.detectChanges();

    expect(mockIntegrationsService.testSonarr).toHaveBeenCalledOnce();
    expect(component.sonarrTestResult).toEqual(successResult);
    expect(component.sonarrTesting).toBe(false);
  });

  it('should call integrationsService.testRadarr on Radarr test button click', () => {
    const successResult: TestConnectionResult = { success: true, message: 'Radarr connected (v5.2.0)' };
    mockIntegrationsService.testRadarr.mockReturnValue(of(successResult));

    component.onTestRadarr();
    fixture.detectChanges();

    expect(mockIntegrationsService.testRadarr).toHaveBeenCalledOnce();
    expect(component.radarrTestResult).toEqual(successResult);
    expect(component.radarrTesting).toBe(false);
  });

  it('should display failure result in the DOM after failed test', () => {
    const failResult: TestConnectionResult = { success: false, message: 'Connection failed: refused' };
    mockIntegrationsService.testSonarr.mockReturnValue(of(failResult));

    component.onTestSonarr();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const resultSpan = el.querySelector('.test-connection .test-result.text-danger');
    expect(resultSpan).not.toBeNull();
    expect(resultSpan!.textContent?.trim()).toContain('Connection failed');
  });

  it('should display success result in the DOM after successful test', () => {
    const successResult: TestConnectionResult = { success: true, message: 'Sonarr connected (v4.0.0)' };
    mockIntegrationsService.testSonarr.mockReturnValue(of(successResult));

    component.onTestSonarr();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const resultSpan = el.querySelector('.test-connection .test-result.text-success');
    expect(resultSpan).not.toBeNull();
    expect(resultSpan!.textContent?.trim()).toContain('Sonarr connected');
  });
});
