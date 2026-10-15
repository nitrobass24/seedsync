import '@angular/compiler';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { DirectoryPickerComponent } from './directory-picker.component';
import { DirectoryBrowserService, BrowseResult } from '../../services/settings/directory-browser.service';

function result(overrides: Partial<BrowseResult> = {}): BrowseResult {
  return {
    success: true,
    path: '/downloads',
    parent: '/',
    directories: ['sub1', 'sub2'],
    errorMessage: null,
    ...overrides,
  };
}

describe('DirectoryPickerComponent', () => {
  let mockBrowserService: {
    browseLocal: ReturnType<typeof vi.fn>;
    browseRemote: ReturnType<typeof vi.fn>;
  };

  function createFixture(kind: 'local' | 'remote', initialPath = '/downloads') {
    TestBed.configureTestingModule({
      providers: [{ provide: DirectoryBrowserService, useValue: mockBrowserService }],
    });
    const fixture = TestBed.createComponent(DirectoryPickerComponent);
    fixture.componentRef.setInput('kind', kind);
    fixture.componentRef.setInput('initialPath', initialPath);
    fixture.detectChanges();
    return fixture;
  }

  function createComponent(kind: 'local' | 'remote', initialPath = '/downloads') {
    return createFixture(kind, initialPath).componentInstance;
  }

  beforeEach(() => {
    mockBrowserService = {
      browseLocal: vi.fn().mockReturnValue(of(result())),
      browseRemote: vi.fn().mockReturnValue(of(result())),
    };
  });

  it('loads the initial path via browseLocal for kind "local"', () => {
    const component = createComponent('local', '/downloads');

    expect(mockBrowserService.browseLocal).toHaveBeenCalledWith('/downloads');
    expect(component.currentPath).toBe('/downloads');
    expect(component.directories).toEqual(['sub1', 'sub2']);
    expect(component.parentPath).toBe('/');
  });

  it('loads the initial path via browseRemote for kind "remote"', () => {
    createComponent('remote', '/home/user');
    expect(mockBrowserService.browseRemote).toHaveBeenCalledWith('/home/user');
  });

  it('defaults to "/" when initialPath is empty', () => {
    createComponent('local', '');
    expect(mockBrowserService.browseLocal).toHaveBeenCalledWith('/');
  });

  it('descends into a subdirectory on entry click', () => {
    const component = createComponent('local', '/downloads');
    mockBrowserService.browseLocal.mockReturnValue(
      of(result({ path: '/downloads/sub1', parent: '/downloads', directories: [] })),
    );

    component.onEnterDirectory('sub1');

    expect(mockBrowserService.browseLocal).toHaveBeenCalledWith('/downloads/sub1');
    expect(component.currentPath).toBe('/downloads/sub1');
  });

  it('navigates to the parent on "up"', () => {
    const component = createComponent('local', '/downloads');
    component.onGoUp();
    expect(mockBrowserService.browseLocal).toHaveBeenCalledWith('/');
  });

  it('does nothing on "up" when there is no parent (already at root)', () => {
    mockBrowserService.browseLocal.mockReturnValue(of(result({ path: '/', parent: null, directories: [] })));
    const component = createComponent('local', '/');
    mockBrowserService.browseLocal.mockClear();

    component.onGoUp();

    expect(mockBrowserService.browseLocal).not.toHaveBeenCalled();
  });

  it('emits select with the current path', () => {
    const component = createComponent('local', '/downloads');
    let selected: string | undefined;
    component.pathSelected.subscribe((path) => (selected = path));

    component.onSelect();

    expect(selected).toBe('/downloads');
  });

  it('emits cancelPick on cancel', () => {
    const component = createComponent('local', '/downloads');
    let cancelled = false;
    component.cancelPick.subscribe(() => (cancelled = true));

    component.onCancel();

    expect(cancelled).toBe(true);
  });

  function failure(errorMessage: string): BrowseResult {
    return { success: false, path: null, parent: null, directories: [], errorMessage };
  }

  it('falls back to the nearest listable ancestor when the initial path fails, keeping the error', () => {
    mockBrowserService.browseRemote.mockImplementation((path: string) =>
      of(
        path === '/downloads'
          ? result({ path: '/downloads', parent: '/', directories: ['other'] })
          : failure('No such file or directory'),
      ),
    );
    const component = createComponent('remote', '/downloads/renamed/deeper');

    expect(mockBrowserService.browseRemote.mock.calls.map((c) => c[0])).toEqual([
      '/downloads/renamed/deeper',
      '/downloads/renamed',
      '/downloads',
    ]);
    expect(component.currentPath).toBe('/downloads');
    expect(component.parentPath).toBe('/');
    expect(component.directories).toEqual(['other']);
    expect(component.errorMessage).toBe('No such file or directory');
  });

  it('stops at "/" and disables Select when nothing lists', () => {
    mockBrowserService.browseRemote.mockReturnValue(of(failure('Connection refused')));
    const fixture = createFixture('remote', '~/gone');

    expect(mockBrowserService.browseRemote.mock.calls.map((c) => c[0])).toEqual(['~/gone', '~', '/']);
    expect(fixture.componentInstance.errorMessage).toBe('Connection refused');
    const select = Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>).find(
      (b) => b.textContent?.includes('Select This Folder'),
    );
    expect(select?.disabled).toBe(true);
  });

  it('does not walk up when a later navigation fails', () => {
    const component = createComponent('local', '/downloads');
    mockBrowserService.browseLocal.mockClear();
    mockBrowserService.browseLocal.mockReturnValue(of(failure('Permission denied')));

    component.onEnterDirectory('locked');

    expect(mockBrowserService.browseLocal).toHaveBeenCalledTimes(1);
  });

  it('surfaces the error message and keeps the previous listing on a failed navigation', () => {
    const component = createComponent('local', '/downloads');
    mockBrowserService.browseLocal.mockReturnValue(
      of(result({ success: true, errorMessage: null })).pipe(),
    );
    mockBrowserService.browseLocal.mockReturnValue(
      of({ success: false, path: null, parent: null, directories: [], errorMessage: 'Permission denied' }),
    );

    component.onEnterDirectory('locked');

    expect(component.errorMessage).toBe('Permission denied');
    expect(component.currentPath).toBe('/downloads');
    expect(component.directories).toEqual(['sub1', 'sub2']);
  });
});
