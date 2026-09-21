import '@angular/compiler';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { DirectoryBrowserService, BrowseResult } from './directory-browser.service';

describe('DirectoryBrowserService', () => {
  let service: DirectoryBrowserService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        DirectoryBrowserService,
      ],
    });
    service = TestBed.inject(DirectoryBrowserService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('browseLocal() returns the listing on success', () => {
    let result: BrowseResult | undefined;
    service.browseLocal('/downloads').subscribe((r) => (result = r));

    const req = httpMock.expectOne((r) => r.url === '/server/browse/local' && r.params.get('path') === '/downloads');
    expect(req.request.method).toBe('GET');
    req.flush({ path: '/downloads', parent: '/', directories: ['a', 'b'] });

    expect(result).toEqual({
      success: true,
      path: '/downloads',
      parent: '/',
      directories: ['a', 'b'],
      errorMessage: null,
    });
  });

  it('browseRemote() returns the listing on success', () => {
    let result: BrowseResult | undefined;
    service.browseRemote('/home/user').subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      (r) => r.url === '/server/browse/remote' && r.params.get('path') === '/home/user',
    );
    expect(req.request.method).toBe('GET');
    req.flush({ path: '/home/user', parent: '/home', directories: ['files'] });

    expect(result!.success).toBe(true);
    expect(result!.directories).toEqual(['files']);
  });

  it('surfaces the server-provided error message on failure', () => {
    let result: BrowseResult | undefined;
    service.browseRemote('/bad/path').subscribe((r) => (result = r));

    httpMock.expectOne((r) => r.url === '/server/browse/remote').flush(
      { error: 'Connection refused' },
      { status: 502, statusText: 'Bad Gateway' },
    );

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe('Connection refused');
    expect(result!.directories).toEqual([]);
  });

  it('falls back to a generic message when the error body is unparsable', () => {
    let result: BrowseResult | undefined;
    service.browseLocal('/bad/path').subscribe((r) => (result = r));

    httpMock.expectOne((r) => r.url === '/server/browse/local').error(new ProgressEvent('error'));

    expect(result!.success).toBe(false);
    expect(result!.errorMessage).toBe('Failed to browse directory');
  });
});
