import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of, Subject } from 'rxjs';
import { SettingsPageComponent } from './settings-page.component';
import {
  FTPS_ONLY_NOTE,
  IOptionsContext,
  OVERRIDE_NOTE,
  OPTIONS_CONTEXT_AUTOQUEUE,
  OPTIONS_CONTEXT_FTPS,
  OPTIONS_CONTEXT_SERVER,
  applyDisableRules,
} from './options-list';
import { ConfigService } from '../../services/settings/config.service';
import { NotificationService } from '../../services/utils/notification.service';
import { NotificationsService } from '../../services/settings/notifications.service';
import { ConnectionTestService, TestResult as ConnectionTestResult } from '../../services/settings/connection-test.service';
import { ConnectionStatusService } from '../../services/settings/connection-status.service';
import { ServerCommandService } from '../../services/server/server-command.service';
import { ConnectedService } from '../../services/utils/connected.service';
import { PathPairsService } from '../../services/settings/path-pairs.service';

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

describe('SettingsPageComponent.onTestConnection', () => {
  let component: SettingsPageComponent;
  let testConnectionSubject: Subject<ConnectionTestResult>;
  let mockConnectionTestService: { testConnection: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    testConnectionSubject = new Subject<ConnectionTestResult>();
    mockConnectionTestService = {
      testConnection: vi.fn().mockReturnValue(testConnectionSubject.asObservable()),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of(null) } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { test: vi.fn() } },
        { provide: ConnectionTestService, useValue: mockConnectionTestService },
        {
          provide: ServerCommandService,
          useValue: { restart: vi.fn().mockReturnValue(of({ success: true, data: 'ok', errorMessage: null })) },
        },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(SettingsPageComponent);
    component = fixture.componentInstance;
  });

  it('sets testingConnection and clears the previous result while the request is in flight', () => {
    component.connectionResult = { success: false, message: 'stale' };
    component.onTestConnection();

    expect(component.testingConnection).toBe(true);
    expect(component.connectionResult).toBeNull();
    expect(mockConnectionTestService.testConnection).toHaveBeenCalled();
  });

  it('surfaces a successful result, marks the connection verified, and shares it via ConnectionStatusService', () => {
    let sharedVerified: boolean | undefined;
    TestBed.inject(ConnectionStatusService).verified$.subscribe((v) => (sharedVerified = v));

    component.onTestConnection();
    testConnectionSubject.next({ success: true, message: 'Connection successful' });

    expect(component.testingConnection).toBe(false);
    expect(component.connectionResult).toEqual({ success: true, message: 'Connection successful' });
    expect(component.connectionVerified).toBe(true);
    expect(sharedVerified).toBe(true);
  });

  it('surfaces a failed result with the server-provided error message and leaves it unverified', () => {
    component.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Incorrect password' });

    expect(component.testingConnection).toBe(false);
    expect(component.connectionResult).toEqual({ success: false, message: 'Incorrect password' });
    expect(component.connectionVerified).toBe(false);
  });

  it('locks out further testing on a credential-error failure', () => {
    component.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Incorrect password', credentialError: true });

    expect(component.connectionLockedOut).toBe(true);
  });

  it('does not lock out on a non-credential failure', () => {
    component.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Connection refused by server' });

    expect(component.connectionLockedOut).toBe(false);
  });

  it('does not call the service (or reset testingConnection) while locked out', () => {
    component.connectionLockedOut = true;
    component.onTestConnection();

    expect(mockConnectionTestService.testConnection).not.toHaveBeenCalled();
    expect(component.testingConnection).toBe(false);
  });

  it('onCommandRestart() clears the lockout', () => {
    component.connectionLockedOut = true;
    component.onCommandRestart();

    expect(component.connectionLockedOut).toBe(false);
  });
});

describe('SettingsPageComponent connection-field changes invalidate a verified connection', () => {
  let component: SettingsPageComponent;
  let setSubject: Subject<{ success: boolean; data: string | null; errorMessage: string | null }>;
  let mockConfigService: { config$: unknown; configSnapshot: unknown; set: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    setSubject = new Subject();
    mockConfigService = {
      config$: of(null),
      configSnapshot: null,
      set: vi.fn().mockReturnValue(setSubject.asObservable()),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: mockConfigService },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { test: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: vi.fn().mockReturnValue(of(null)) } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(SettingsPageComponent);
    component = fixture.componentInstance;
    component.connectionVerified = true;
    component.connectionResult = { success: true, message: 'Connection successful' };
    component.connectionLockedOut = true;
  });

  it('resets connectionVerified when a connection field is changed successfully', () => {
    component.onSetConfig('lftp', 'remote_address', 'new.host.example.com');
    setSubject.next({ success: true, data: 'lftp.remote_address set to new.host.example.com', errorMessage: null });

    expect(component.connectionVerified).toBe(false);
    expect(component.connectionResult).toBeNull();
  });

  it('clears a credential-error lockout when a connection field is changed successfully', () => {
    component.onSetConfig('lftp', 'remote_password', 'new-password');
    setSubject.next({ success: true, data: 'lftp.remote_password updated', errorMessage: null });

    expect(component.connectionLockedOut).toBe(false);
  });

  it('does not reset connectionVerified for unrelated fields', () => {
    component.onSetConfig('lftp', 'remote_path', '/some/path');
    setSubject.next({ success: true, data: 'lftp.remote_path set to /some/path', errorMessage: null });

    expect(component.connectionVerified).toBe(true);
    expect(component.connectionLockedOut).toBe(true);
  });

  it('does not reset connectionVerified when the set request fails', () => {
    component.onSetConfig('lftp', 'remote_port', '22');
    setSubject.next({ success: false, data: null, errorMessage: 'Bad config' });

    expect(component.connectionVerified).toBe(true);
  });
});

describe('SettingsPageComponent directory picker', () => {
  let component: SettingsPageComponent;
  let mockConfigService: { config$: unknown; configSnapshot: unknown; set: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockConfigService = {
      config$: of(null),
      configSnapshot: { lftp: { remote_path: '/remote/current', local_path: '/local/current' } },
      set: vi.fn().mockReturnValue(of({ success: true, data: 'ok', errorMessage: null })),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: mockConfigService },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { test: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: vi.fn().mockReturnValue(of(null)) } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(SettingsPageComponent);
    component = fixture.componentInstance;
  });

  it('opens the picker for remote_path with kind "remote" and the current value', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.onBrowseDirectory(option);

    expect(component.directoryPickerOption).toBe(option);
    expect(component.directoryPickerKind).toBe('remote');
    expect(component.directoryPickerInitialPath).toBe('/remote/current');
  });

  it('opens the picker for local_path with kind "local"', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'local_path')!;
    component.onBrowseDirectory(option);

    expect(component.directoryPickerKind).toBe('local');
    expect(component.directoryPickerInitialPath).toBe('/local/current');
  });

  it('defaults to "/" when the field has no current value', () => {
    mockConfigService.configSnapshot = { lftp: { remote_path: null, local_path: null } };
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.onBrowseDirectory(option);

    expect(component.directoryPickerInitialPath).toBe('/');
  });

  it('persists the selected path and closes the picker on select', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.onBrowseDirectory(option);

    component.onDirectorySelected('/remote/chosen');

    expect(mockConfigService.set).toHaveBeenCalledWith('lftp', 'remote_path', '/remote/chosen');
    expect(component.directoryPickerOption).toBeNull();
  });

  it('closes the picker without persisting on cancel', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.onBrowseDirectory(option);

    component.onDirectoryPickerCancel();

    expect(mockConfigService.set).not.toHaveBeenCalled();
    expect(component.directoryPickerOption).toBeNull();
  });
});

describe('SettingsPageComponent auto-verifies an already-configured connection on load', () => {
  it('calls testConnection once when the loaded config already has connection fields set', () => {
    const config = { lftp: { remote_address: 'host', remote_username: 'user', remote_port: 22 } };
    const mockTestConnection = vi.fn().mockReturnValue(of({ success: true, message: 'Connection successful' }));

    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of(config), configSnapshot: config } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { test: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: mockTestConnection } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(SettingsPageComponent);
    fixture.detectChanges();

    expect(mockTestConnection).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance.connectionVerified).toBe(true);
  });

  it('does not auto-test when the connection is not yet configured', () => {
    const config = { lftp: { remote_address: null, remote_username: null, remote_port: null } };
    const mockTestConnection = vi.fn().mockReturnValue(of({ success: true, message: 'Connection successful' }));

    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of(config), configSnapshot: config } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { test: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: mockTestConnection } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(SettingsPageComponent);
    fixture.detectChanges();

    expect(mockTestConnection).not.toHaveBeenCalled();
    expect(fixture.componentInstance.connectionVerified).toBe(false);
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

describe('SettingsPageComponent.isServerDirectoryLocked', () => {
  let component: SettingsPageComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of(null) } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { testDiscord: vi.fn(), testTelegram: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: vi.fn().mockReturnValue(of(null)) } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });
    component = TestBed.createComponent(SettingsPageComponent).componentInstance;
  });

  it('is locked for remote_path when the connection is not yet verified', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.connectionVerified = false;

    expect(component.isServerDirectoryLocked(option)).toBe(true);
  });

  it('is unlocked for remote_path once the connection is verified', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.connectionVerified = true;

    expect(component.isServerDirectoryLocked(option)).toBe(false);
  });

  it('is not "locked" (no redundant note) when already disabled for another reason, e.g. path pairs', () => {
    const option = buildServerContext(true).options.find((o) => o.valuePath[1] === 'remote_path')!;
    component.connectionVerified = false;

    expect(option.disabled).toBe(true);
    expect(component.isServerDirectoryLocked(option)).toBe(false);
  });

  it('never locks local_path (no SSH connection needed to browse locally)', () => {
    const option = buildServerContext(false).options.find((o) => o.valuePath[1] === 'local_path')!;
    component.connectionVerified = false;

    expect(component.isServerDirectoryLocked(option)).toBe(false);
  });
});

describe('SettingsPageComponent Server Directory lock note renders end-to-end', () => {
  it('shows the note while unverified and hides it once Test Connection succeeds', () => {
    const testConnectionSubject = new Subject<ConnectionTestResult>();
    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of({ lftp: {} }) } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { testDiscord: vi.fn(), testTelegram: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: vi.fn().mockReturnValue(testConnectionSubject.asObservable()) } },
        { provide: ServerCommandService, useValue: { restart: vi.fn() } },
        { provide: ConnectedService, useValue: { connected$: of(false) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });
    const fixture = TestBed.createComponent(SettingsPageComponent);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.connection-lock-note')).not.toBeNull();

    fixture.componentInstance.onTestConnection();
    testConnectionSubject.next({ success: true, message: 'Connection successful' });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.connection-lock-note')).toBeNull();
  });
});

describe('SettingsPageComponent connection lockout banner renders end-to-end', () => {
  function setUpFixture() {
    const testConnectionSubject = new Subject<ConnectionTestResult>();
    TestBed.configureTestingModule({
      providers: [
        { provide: ConfigService, useValue: { config$: of({ lftp: {} }) } },
        { provide: NotificationService, useValue: { show: vi.fn(), hide: vi.fn() } },
        { provide: NotificationsService, useValue: { testDiscord: vi.fn(), testTelegram: vi.fn() } },
        { provide: ConnectionTestService, useValue: { testConnection: vi.fn().mockReturnValue(testConnectionSubject.asObservable()) } },
        {
          provide: ServerCommandService,
          useValue: { restart: vi.fn().mockReturnValue(of({ success: true, data: 'ok', errorMessage: null })) },
        },
        { provide: ConnectedService, useValue: { connected$: of(true) } },
        { provide: PathPairsService, useValue: { pairs$: of([]) } },
      ],
    });
    const fixture = TestBed.createComponent(SettingsPageComponent);
    fixture.detectChanges();
    return { fixture, testConnectionSubject };
  }

  it('is absent before any failure and appears after a credential-error failure', () => {
    const { fixture, testConnectionSubject } = setUpFixture();
    expect(fixture.nativeElement.querySelector('.connection-lockout-banner')).toBeNull();

    fixture.componentInstance.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Incorrect password', credentialError: true });
    fixture.detectChanges();

    const banner = fixture.nativeElement.querySelector('.connection-lockout-banner');
    expect(banner).not.toBeNull();
    expect(banner.textContent).toContain('Further connection tests are blocked');
  });

  it('disables the Test Connection button while the banner is showing', () => {
    const { fixture, testConnectionSubject } = setUpFixture();
    fixture.componentInstance.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Incorrect password', credentialError: true });
    fixture.detectChanges();

    const button = Array.from(fixture.nativeElement.querySelectorAll('button')).find(
      (b) => (b as HTMLButtonElement).textContent?.trim() === 'Test Connection',
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it('clicking Restart clears the lockout and hides the banner', () => {
    const { fixture, testConnectionSubject } = setUpFixture();
    fixture.componentInstance.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Incorrect password', credentialError: true });
    fixture.detectChanges();

    const restartButton = Array.from(fixture.nativeElement.querySelectorAll('button')).find(
      (b) => (b as HTMLButtonElement).textContent?.trim() === 'Restart',
    ) as HTMLButtonElement;
    restartButton.click();
    fixture.detectChanges();

    expect(fixture.componentInstance.connectionLockedOut).toBe(false);
    expect(fixture.nativeElement.querySelector('.connection-lockout-banner')).toBeNull();
  });

  it('does not show the banner for a non-credential failure', () => {
    const { fixture, testConnectionSubject } = setUpFixture();
    fixture.componentInstance.onTestConnection();
    testConnectionSubject.next({ success: false, message: 'Connection refused by server' });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.connection-lockout-banner')).toBeNull();
  });
});
