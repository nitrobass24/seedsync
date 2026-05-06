import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { HeaderComponent } from './header.component';
import { ServerStatusService } from '../../services/server/server-status.service';
import { NotificationService } from '../../services/utils/notification.service';
import { LoggerService } from '../../services/utils/logger.service';
import { ServerStatus } from '../../models/server-status';
import { Notification, NotificationLevel } from '../../models/notification';
import { Localization } from '../../models/localization';

function makeStatus(overrides: Partial<{
  server: Partial<ServerStatus['server']>;
  controller: Partial<ServerStatus['controller']>;
}> = {}): ServerStatus {
  return {
    server: {
      up: true,
      errorMessage: null,
      ...overrides.server,
    },
    controller: {
      latestLocalScanTime: null,
      latestRemoteScanTime: new Date(),
      latestRemoteScanFailed: false,
      latestRemoteScanError: null,
      noEnabledPairs: false,
      ...overrides.controller,
    },
  };
}

describe('HeaderComponent', () => {
  let component: HeaderComponent;
  let statusSubject: BehaviorSubject<ServerStatus>;
  let notificationService: NotificationService;

  beforeEach(() => {
    statusSubject = new BehaviorSubject<ServerStatus>(makeStatus());

    TestBed.configureTestingModule({
      providers: [
        { provide: ServerStatusService, useValue: { status$: statusSubject.asObservable() } },
        NotificationService,
        { provide: LoggerService, useValue: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() } },
      ],
    });

    notificationService = TestBed.inject(NotificationService);
    const fixture = TestBed.createComponent(HeaderComponent);
    component = fixture.componentInstance;
    component.ngOnInit();
  });

  // --- Server down ---

  it('should show DANGER notification when server is down', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Connection refused' } }));

    expect(notifications.length).toBeGreaterThanOrEqual(1);
    const danger = notifications.find(n => n.level === NotificationLevel.DANGER);
    expect(danger).toBeDefined();
    expect(danger!.text).toBe('Connection refused');
  });

  it('should hide server notification when server recovers', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Down' } }));
    expect(notifications.some(n => n.level === NotificationLevel.DANGER)).toBe(true);

    statusSubject.next(makeStatus({ server: { up: true, errorMessage: null } }));
    expect(notifications.some(n => n.level === NotificationLevel.DANGER)).toBe(false);
  });

  // --- Waiting for remote scan ---

  it('should show INFO notification when no remote scan yet and pairs exist', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({
      server: { up: true },
      controller: { latestRemoteScanTime: null, noEnabledPairs: false },
    }));

    const info = notifications.find(n => n.level === NotificationLevel.INFO);
    expect(info).toBeDefined();
    expect(info!.text).toBe(Localization.Notification.STATUS_REMOTE_SCAN_WAITING);
  });

  // --- Remote scan failed ---

  it('should show WARNING notification when remote scan fails', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({
      server: { up: true },
      controller: {
        latestRemoteScanFailed: true,
        latestRemoteScanError: 'Timeout',
        noEnabledPairs: false,
      },
    }));

    const warning = notifications.find(n => n.level === NotificationLevel.WARNING);
    expect(warning).toBeDefined();
    expect(warning!.text).toContain('Timeout');
  });

  // --- No enabled pairs ---

  it('should show WARNING notification when no pairs are enabled', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({
      server: { up: true },
      controller: { noEnabledPairs: true },
    }));

    const warning = notifications.find(n => n.text === Localization.Notification.STATUS_NO_ENABLED_PAIRS);
    expect(warning).toBeDefined();
    expect(warning!.level).toBe(NotificationLevel.WARNING);
  });

  // --- Precedence / coexistence ---

  it('should show server-down notification with highest priority (DANGER sorts first)', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Server down' } }));

    // DANGER should be first in the sorted list
    expect(notifications[0].level).toBe(NotificationLevel.DANGER);
  });

  it('should replace old notification text when status text changes', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Error A' } }));
    expect(notifications.some(n => n.text === 'Error A')).toBe(true);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Error B' } }));
    expect(notifications.some(n => n.text === 'Error B')).toBe(true);
    expect(notifications.some(n => n.text === 'Error A')).toBe(false);
  });

  it('should not create duplicate notification when same text is emitted again', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Same error' } }));
    const countBefore = notifications.length;

    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Same error' } }));
    expect(notifications.length).toBe(countBefore);
  });

  it('should handle multiple rules coexisting independently', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    // Trigger both "waiting for scan" and "no enabled pairs" are mutually exclusive
    // (noEnabledPairs suppresses waitingForRemoteScan), but remoteServerError + noEnabledPairs
    // are also exclusive. Let's verify server-down + noEnabledPairs can't coexist
    // because server.up is false suppresses the noEnabledPairs check.
    // Instead, let's verify that changing from one rule to another cleans up properly.

    // First: no enabled pairs
    statusSubject.next(makeStatus({
      server: { up: true },
      controller: { noEnabledPairs: true, latestRemoteScanTime: new Date() },
    }));
    expect(notifications.some(n => n.text === Localization.Notification.STATUS_NO_ENABLED_PAIRS)).toBe(true);

    // Then: server goes down
    statusSubject.next(makeStatus({
      server: { up: false, errorMessage: 'Down' },
      controller: { noEnabledPairs: true },
    }));
    // noEnabledPairs rule should be hidden (server.up is false)
    expect(notifications.some(n => n.text === Localization.Notification.STATUS_NO_ENABLED_PAIRS)).toBe(false);
    expect(notifications.some(n => n.level === NotificationLevel.DANGER)).toBe(true);
  });

  it('should not show "waiting for remote scan" when no pairs are enabled', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({
      server: { up: true },
      controller: { latestRemoteScanTime: null, noEnabledPairs: true },
    }));

    // "waitingForRemoteScan" should NOT show because noEnabledPairs is true
    expect(notifications.some(n => n.text === Localization.Notification.STATUS_REMOTE_SCAN_WAITING)).toBe(false);
    // But "noEnabledPairs" should show
    expect(notifications.some(n => n.text === Localization.Notification.STATUS_NO_ENABLED_PAIRS)).toBe(true);
  });

  it('should not show remote scan error when no pairs are enabled', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    statusSubject.next(makeStatus({
      server: { up: true },
      controller: {
        latestRemoteScanFailed: true,
        latestRemoteScanError: 'Timeout',
        noEnabledPairs: true,
      },
    }));

    expect(notifications.some(n => n.text.includes('Timeout'))).toBe(false);
  });

  it('should clean up all notifications when server recovers from complex state', () => {
    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    // Server down
    statusSubject.next(makeStatus({ server: { up: false, errorMessage: 'Error' } }));
    expect(notifications.length).toBeGreaterThan(0);

    // Server recovers to healthy state
    statusSubject.next(makeStatus({
      server: { up: true },
      controller: { latestRemoteScanTime: new Date(), noEnabledPairs: false },
    }));
    expect(notifications.length).toBe(0);
  });
});
