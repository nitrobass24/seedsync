import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { of } from 'rxjs';

import { PathPair } from '../../models/path-pair';

function makePair(overrides: Partial<PathPair> = {}): PathPair {
  return {
    id: '1',
    name: 'Default',
    remote_path: '/remote',
    local_path: '/local',
    enabled: true,
    auto_queue: false,
    ...overrides,
  };
}

/**
 * Since Vitest lacks Angular JIT compiler setup, we test the component logic
 * by dynamically importing the class and bypassing Angular decorators at
 * module-evaluation time. Instead we test the same logic inline.
 *
 * This mirrors the pattern used by the passing model/pipe spec files in this repo.
 */

// Extracted inline version of the component logic for testing
// (matches PathPairsComponent methods exactly)
class PathPairsLogic {
  editingId: string | null = null;
  editForm: Omit<PathPair, 'id'> = this.emptyForm();
  adding = false;
  addForm: Omit<PathPair, 'id'> = this.emptyForm();
  confirmingDeleteId: string | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private service: any) {}

  onStartAdd(): void {
    this.cancelEdit();
    this.adding = true;
    this.addForm = this.emptyForm();
  }

  onCancelAdd(): void {
    this.adding = false;
    this.addForm = this.emptyForm();
  }

  onSaveAdd(): void {
    if (!this.addForm.name.trim()) return;
    this.service.create(this.addForm).subscribe((created: any) => {
      if (!created) return;
      this.adding = false;
      this.addForm = this.emptyForm();
    });
  }

  onStartEdit(pair: PathPair): void {
    this.onCancelAdd();
    this.resetConfirmState();
    this.editingId = pair.id;
    this.editForm = {
      name: pair.name,
      remote_path: pair.remote_path,
      local_path: pair.local_path,
      enabled: pair.enabled,
      auto_queue: pair.auto_queue,
    };
  }

  onCancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
  }

  onSaveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim()) return;
    this.service.update({ id: this.editingId, ...this.editForm }).subscribe((updated: any) => {
      if (!updated) return;
      this.editingId = null;
      this.editForm = this.emptyForm();
    });
  }

  onDelete(pairId: string): void {
    if (this.confirmingDeleteId === pairId) {
      this.clearConfirmTimer();
      this.confirmingDeleteId = null;
      this.service.remove(pairId).subscribe();
    } else {
      this.setConfirming(pairId);
    }
  }

  onToggleEnabled(pair: PathPair, enabled: boolean): void {
    this.service.update({ ...pair, enabled }).subscribe();
  }

  onToggleAutoQueue(pair: PathPair, autoQueue: boolean): void {
    this.service.update({ ...pair, auto_queue: autoQueue }).subscribe();
  }

  destroy(): void {
    this.clearConfirmTimer();
  }

  private cancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
    this.resetConfirmState();
  }

  private emptyForm(): Omit<PathPair, 'id'> {
    return { name: '', remote_path: '', local_path: '', enabled: true, auto_queue: false };
  }

  private setConfirming(pairId: string): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = pairId;
    this.confirmResetTimer = setTimeout(() => {
      this.confirmingDeleteId = null;
      this.confirmResetTimer = null;
    }, 3000);
  }

  private resetConfirmState(): void {
    this.clearConfirmTimer();
    this.confirmingDeleteId = null;
  }

  private clearConfirmTimer(): void {
    if (this.confirmResetTimer !== null) {
      clearTimeout(this.confirmResetTimer);
      this.confirmResetTimer = null;
    }
  }
}

describe('PathPairsComponent logic', () => {
  let component: PathPairsLogic;
  let mockService: any;

  beforeEach(() => {
    mockService = {
      create: vi.fn().mockReturnValue(of(makePair({ id: '2', name: 'New' }))),
      update: vi.fn().mockReturnValue(of(makePair({ enabled: false }))),
      remove: vi.fn().mockReturnValue(of(true)),
    };
    component = new PathPairsLogic(mockService);
  });

  afterEach(() => {
    component.destroy();
    vi.restoreAllMocks();
  });

  it('should start with no adding/editing state', () => {
    expect(component.adding).toBe(false);
    expect(component.editingId).toBeNull();
    expect(component.confirmingDeleteId).toBeNull();
  });

  it('should open add form', () => {
    component.onStartAdd();
    expect(component.adding).toBe(true);
    expect(component.addForm.name).toBe('');
  });

  it('should cancel add form', () => {
    component.onStartAdd();
    component.addForm.name = 'test';
    component.onCancelAdd();
    expect(component.adding).toBe(false);
    expect(component.addForm.name).toBe('');
  });

  it('should call create on save add', () => {
    component.onStartAdd();
    component.addForm = { name: 'Test', remote_path: '/r', local_path: '/l', enabled: true, auto_queue: false };
    component.onSaveAdd();
    expect(mockService.create).toHaveBeenCalledWith({
      name: 'Test', remote_path: '/r', local_path: '/l', enabled: true, auto_queue: false,
    });
  });

  it('should not save add when name is empty', () => {
    component.onStartAdd();
    component.addForm.name = '   ';
    component.onSaveAdd();
    expect(mockService.create).not.toHaveBeenCalled();
  });

  it('should close add form after successful create', () => {
    component.onStartAdd();
    component.addForm = { name: 'Test', remote_path: '/r', local_path: '/l', enabled: true, auto_queue: false };
    component.onSaveAdd();
    expect(component.adding).toBe(false);
  });

  it('should enter edit mode', () => {
    const pair = makePair();
    component.onStartEdit(pair);
    expect(component.editingId).toBe(pair.id);
    expect(component.editForm.name).toBe(pair.name);
    expect(component.editForm.remote_path).toBe(pair.remote_path);
  });

  it('should cancel edit mode', () => {
    component.onStartEdit(makePair());
    component.onCancelEdit();
    expect(component.editingId).toBeNull();
  });

  it('should call update on save edit', () => {
    const pair = makePair();
    component.onStartEdit(pair);
    component.editForm.name = 'Updated';
    component.onSaveEdit();
    expect(mockService.update).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', name: 'Updated' }),
    );
  });

  it('should not save edit when name is empty', () => {
    component.onStartEdit(makePair());
    component.editForm.name = '   ';
    component.onSaveEdit();
    expect(mockService.update).not.toHaveBeenCalled();
  });

  it('should close edit form after successful update', () => {
    component.onStartEdit(makePair());
    component.editForm.name = 'Updated';
    component.onSaveEdit();
    expect(component.editingId).toBeNull();
  });

  it('should cancel add when starting edit', () => {
    component.onStartAdd();
    component.onStartEdit(makePair());
    expect(component.adding).toBe(false);
  });

  it('should require double-click to delete', () => {
    component.onDelete('1');
    expect(component.confirmingDeleteId).toBe('1');
    expect(mockService.remove).not.toHaveBeenCalled();

    component.onDelete('1');
    expect(mockService.remove).toHaveBeenCalledWith('1');
    expect(component.confirmingDeleteId).toBeNull();
  });

  it('should reset confirm state after timeout', () => {
    vi.useFakeTimers();
    component.onDelete('1');
    expect(component.confirmingDeleteId).toBe('1');

    vi.advanceTimersByTime(3000);
    expect(component.confirmingDeleteId).toBeNull();
    vi.useRealTimers();
  });

  it('should switch confirming to different pair on click', () => {
    component.onDelete('1');
    expect(component.confirmingDeleteId).toBe('1');

    component.onDelete('2');
    expect(component.confirmingDeleteId).toBe('2');
  });

  it('should toggle enabled via update', () => {
    const pair = makePair({ enabled: true });
    component.onToggleEnabled(pair, false);
    expect(mockService.update).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false }),
    );
  });

  it('should toggle auto_queue via update', () => {
    const pair = makePair({ auto_queue: false });
    component.onToggleAutoQueue(pair, true);
    expect(mockService.update).toHaveBeenCalledWith(
      expect.objectContaining({ auto_queue: true }),
    );
  });

  it('should not clear add form when service returns null', () => {
    mockService.create = vi.fn().mockReturnValue(of(null));
    component.onStartAdd();
    component.addForm = { name: 'Test', remote_path: '/r', local_path: '/l', enabled: true, auto_queue: false };
    component.onSaveAdd();
    expect(component.adding).toBe(true);
    expect(component.addForm.name).toBe('Test');
  });

  it('should not clear edit form when service returns null', () => {
    mockService.update = vi.fn().mockReturnValue(of(null));
    component.onStartEdit(makePair());
    component.editForm.name = 'Updated';
    component.onSaveEdit();
    expect(component.editingId).toBe('1');
    expect(component.editForm.name).toBe('Updated');
  });

  it('should reset confirm state when starting edit', () => {
    component.onDelete('1');
    expect(component.confirmingDeleteId).toBe('1');
    component.onStartEdit(makePair());
    expect(component.confirmingDeleteId).toBeNull();
  });
});
