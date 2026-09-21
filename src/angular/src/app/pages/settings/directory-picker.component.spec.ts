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

  function createComponent(kind: 'local' | 'remote', initialPath = '/downloads') {
    TestBed.configureTestingModule({
      providers: [{ provide: DirectoryBrowserService, useValue: mockBrowserService }],
    });
    const fixture = TestBed.createComponent(DirectoryPickerComponent);
    fixture.componentRef.setInput('kind', kind);
    fixture.componentRef.setInput('initialPath', initialPath);
    fixture.detectChanges();
    return fixture.componentInstance;
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

  it('preserves the configured initial path when the first browse fails, so Select still returns it', () => {
    mockBrowserService.browseLocal.mockReturnValue(
      of({ success: false, path: null, parent: null, directories: [], errorMessage: 'Permission denied' }),
    );
    const component = createComponent('local', '/configured/path');

    expect(component.currentPath).toBe('/configured/path');
    expect(component.errorMessage).toBe('Permission denied');

    let selected: string | undefined;
    component.pathSelected.subscribe((path) => (selected = path));
    component.onSelect();

    expect(selected).toBe('/configured/path');
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
