import '@angular/compiler';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject, of, throwError } from 'rxjs';

import { IntegrationsComponent } from './integrations.component';
import { IntegrationsService } from '../../services/settings/integrations.service';
import { ArrInstance } from '../../models/arr-instance';

function makeInstance(overrides: Partial<ArrInstance> = {}): ArrInstance {
  return {
    id: 'inst-1',
    name: 'Sonarr — TV',
    kind: 'sonarr',
    url: 'http://sonarr:8989',
    api_key: '********',
    enabled: true,
    ...overrides,
  };
}

describe('IntegrationsComponent', () => {
  let component: IntegrationsComponent;
  let instancesSubject: BehaviorSubject<ArrInstance[]>;
  let mockIntegrationsService: {
    instances$: ReturnType<typeof BehaviorSubject.prototype.asObservable>;
    create: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    refresh: ReturnType<typeof vi.fn>;
    test: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.useFakeTimers();
    instancesSubject = new BehaviorSubject<ArrInstance[]>([]);

    mockIntegrationsService = {
      instances$: instancesSubject.asObservable(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
      refresh: vi.fn(),
      test: vi.fn(),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: IntegrationsService, useValue: mockIntegrationsService },
      ],
    });

    const fixture = TestBed.createComponent(IntegrationsComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // --- Add form ---

  it('should open add form with kind pre-selected and cancel should reset', () => {
    component.onStartAdd('radarr');
    expect(component.adding).toBe(true);
    expect(component.addForm.kind).toBe('radarr');
    expect(component.addForm.name).toBe('');

    component.onCancelAdd();
    expect(component.adding).toBe(false);
    expect(component.addForm.name).toBe('');
  });

  it('should set error when saving add with empty name', () => {
    component.onStartAdd('sonarr');
    component.addForm.name = '   ';
    component.onSaveAdd();

    expect(component.errorMessage).toBe('Name is required.');
    expect(mockIntegrationsService.create).not.toHaveBeenCalled();
  });

  it('should call service create with valid data', () => {
    const created = makeInstance({ id: 'new-id', name: 'My Sonarr' });
    mockIntegrationsService.create.mockReturnValue(of(created));

    component.onStartAdd('sonarr');
    component.addForm.name = 'My Sonarr';
    component.addForm.url = 'http://sonarr:8989';
    component.addForm.api_key = 'key123';
    component.onSaveAdd();

    expect(mockIntegrationsService.create).toHaveBeenCalledWith({
      name: 'My Sonarr',
      kind: 'sonarr',
      url: 'http://sonarr:8989',
      api_key: 'key123',
      enabled: true,
    });
    expect(component.adding).toBe(false);
  });

  // --- Edit form ---

  it('should populate edit form from instance', () => {
    const inst = makeInstance({ name: 'Radarr — Movies', kind: 'radarr' });
    component.onStartEdit(inst);

    expect(component.editingId).toBe('inst-1');
    expect(component.editForm.name).toBe('Radarr — Movies');
    expect(component.editForm.kind).toBe('radarr');
  });

  it('should cancel edit and clear form', () => {
    component.onStartEdit(makeInstance());
    expect(component.editingId).not.toBeNull();

    component.onCancelEdit();
    expect(component.editingId).toBeNull();
    expect(component.editForm.name).toBe('');
  });

  // --- Delete double-click ---

  it('should enter confirmation state on first delete click', () => {
    component.onDelete('inst-1');
    expect(component.confirmingDeleteId).toBe('inst-1');
    expect(mockIntegrationsService.remove).not.toHaveBeenCalled();
  });

  it('should call service remove on second delete click (confirmation)', () => {
    mockIntegrationsService.remove.mockReturnValue(of(true));

    component.onDelete('inst-1'); // first click -> confirm
    component.onDelete('inst-1'); // second click -> delete

    expect(mockIntegrationsService.remove).toHaveBeenCalledWith('inst-1');
    expect(component.confirmingDeleteId).toBeNull();
  });

  it('should reset confirmation state after 3 seconds', () => {
    component.onDelete('inst-1');
    expect(component.confirmingDeleteId).toBe('inst-1');

    vi.advanceTimersByTime(3000);
    expect(component.confirmingDeleteId).toBeNull();
  });

  it('should clear confirmation timer on destroy', () => {
    component.onDelete('inst-1');
    expect(component.confirmingDeleteId).toBe('inst-1');

    component.ngOnDestroy();
    // Advancing timers after destroy should not cause issues
    vi.advanceTimersByTime(5000);
    // Timer was cleared, so it doesn't auto-reset (already cleared in ngOnDestroy)
  });

  // --- Error handling ---

  it('should set error when create returns null (server error)', () => {
    mockIntegrationsService.create.mockReturnValue(of(null));

    component.onStartAdd('sonarr');
    component.addForm.name = 'Test';
    component.onSaveAdd();

    expect(component.errorMessage).toContain('Failed to create');
  });

  it('should set error when create throws (409 conflict)', () => {
    mockIntegrationsService.create.mockReturnValue(
      throwError(() => ({ status: 409 })),
    );

    component.onStartAdd('sonarr');
    component.addForm.name = 'Duplicate';
    component.onSaveAdd();

    expect(component.errorMessage).toContain('already exists');
  });
});
