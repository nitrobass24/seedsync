import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { VersionCheckService } from './version-check.service';
import { RestService, WebReaction } from './rest.service';
import { NotificationService } from './notification.service';
import { LoggerService } from './logger.service';
import { Notification, NotificationLevel } from '../../models/notification';
import packageJson from '../../../../package.json';

function makeReaction(overrides: Partial<WebReaction> = {}): WebReaction {
  return {
    success: true,
    data: null,
    errorMessage: null,
    ...overrides,
  };
}

function makeGithubResponse(tagName: string, htmlUrl = 'https://github.com/nitrobass24/seedsync/releases/latest'): string {
  return JSON.stringify({ tag_name: tagName, html_url: htmlUrl });
}

describe('VersionCheckService', () => {
  let mockRestService: { sendRequest: ReturnType<typeof vi.fn> };
  let notificationService: NotificationService;
  let mockLogger: { debug: ReturnType<typeof vi.fn>; info: ReturnType<typeof vi.fn>; warn: ReturnType<typeof vi.fn>; error: ReturnType<typeof vi.fn> };

  function createService(): VersionCheckService {
    return TestBed.inject(VersionCheckService);
  }

  beforeEach(() => {
    mockRestService = { sendRequest: vi.fn() };
    mockLogger = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        VersionCheckService,
        NotificationService,
        { provide: RestService, useValue: mockRestService },
        { provide: LoggerService, useValue: mockLogger },
      ],
    });

    notificationService = TestBed.inject(NotificationService);
  });

  it('should show notification when a newer release is available', () => {
    // Current version is 0.17.0, so 99.0.0 is always newer
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: makeGithubResponse('v99.0.0') })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(1);
    expect(notifications[0].level).toBe(NotificationLevel.INFO);
    expect(notifications[0].text).toContain('new version');
  });

  it('should not show notification when release is same version', () => {
    // Use the live package.json version so this test stays correct
    // across version bumps.
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: makeGithubResponse('v' + packageJson.version) })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(0);
  });

  it('should not show notification when release is older', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: makeGithubResponse('v0.1.0') })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(0);
  });

  it('should strip v prefix before comparing versions', () => {
    // Without prefix stripping, "v99.0.0" might fail comparison
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: makeGithubResponse('v99.0.0') })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(1);
  });

  it('should log warning and not show notification on network error', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: false, errorMessage: 'Network error' })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(0);
    expect(mockLogger.warn).toHaveBeenCalled();
  });

  it('should log error and not crash on malformed JSON response', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: 'not valid json {{{' })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(0);
    expect(mockLogger.error).toHaveBeenCalled();
  });

  it('should log error and not crash on unexpected JSON structure', () => {
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: JSON.stringify({ foo: 'bar' }) })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications.length).toBe(0);
    expect(mockLogger.error).toHaveBeenCalled();
  });

  it('should include the release URL in the notification text', () => {
    const url = 'https://github.com/nitrobass24/seedsync/releases/tag/v99.0.0';
    mockRestService.sendRequest.mockReturnValue(
      of(makeReaction({ success: true, data: makeGithubResponse('v99.0.0', url) })),
    );

    let notifications: Notification[] = [];
    notificationService.notifications$.subscribe(n => notifications = n);

    createService();

    expect(notifications).toHaveLength(1);
    expect(notifications[0].text).toContain(url);
  });
});
