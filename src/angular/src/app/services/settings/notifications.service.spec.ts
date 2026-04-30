import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { NotificationsService, TestResult } from './notifications.service';

describe('NotificationsService', () => {
  let service: NotificationsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        NotificationsService,
      ],
    });
    service = TestBed.inject(NotificationsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('testDiscord() returns success on HTTP 200', () => {
    let result: TestResult | undefined;
    service.testDiscord().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/notifications/test/discord');
    expect(req.request.method).toBe('POST');
    req.flush({});

    expect(result!.success).toBe(true);
    expect(result!.message).toBe('Notification sent successfully');
  });

  it('testDiscord() surfaces server-provided error message on failure', () => {
    let result: TestResult | undefined;
    service.testDiscord().subscribe((r) => (result = r));

    httpMock.expectOne('/server/notifications/test/discord').flush(
      { error: 'Discord webhook URL not configured' },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Discord webhook URL not configured');
  });

  it('testDiscord() falls back to generic message when error body is unparsable', () => {
    let result: TestResult | undefined;
    service.testDiscord().subscribe((r) => (result = r));

    httpMock.expectOne('/server/notifications/test/discord').error(new ProgressEvent('error'));

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Notification failed');
  });

  it('testTelegram() returns success on HTTP 200', () => {
    let result: TestResult | undefined;
    service.testTelegram().subscribe((r) => (result = r));

    const req = httpMock.expectOne('/server/notifications/test/telegram');
    expect(req.request.method).toBe('POST');
    req.flush({});

    expect(result!.success).toBe(true);
    expect(result!.message).toBe('Notification sent successfully');
  });

  it('testTelegram() surfaces server-provided error message on failure', () => {
    let result: TestResult | undefined;
    service.testTelegram().subscribe((r) => (result = r));

    httpMock.expectOne('/server/notifications/test/telegram').flush(
      { error: 'Telegram bot token not configured' },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Telegram bot token not configured');
  });

  it('testTelegram() falls back to generic message when error body is unparsable', () => {
    let result: TestResult | undefined;
    service.testTelegram().subscribe((r) => (result = r));

    httpMock.expectOne('/server/notifications/test/telegram').error(new ProgressEvent('error'));

    expect(result!.success).toBe(false);
    expect(result!.message).toBe('Notification failed');
  });
});
