import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { Observable, of } from 'rxjs';

import { PathPair } from '../../models/path-pair';
import { ArrInstance } from '../../models/arr-instance';

interface PathPairsServiceLike {
  create(pair: Omit<PathPair, 'id'>): Observable<PathPair | null>;
  update(pair: PathPair): Observable<PathPair | null>;
  remove(pairId: string): Observable<boolean>;
}

function makePair(overrides: Partial<PathPair> = {}): PathPair {
  return {
    id: '1',
    name: 'Default',
    remote_path: '/remote',
    local_path: '/local',
    enabled: true,
    auto_queue: false,
    arr_target_ids: [],
    ...overrides,
  };
}

function makeInstance(overrides: Partial<ArrInstance> = {}): ArrInstance {
  return {
    id: 'inst-1',
    name: 'Sonarr — TV',
    kind: 'sonarr',
    url: 'http://s',
    api_key: '********',
    enabled: true,
    ...overrides,
  };
}

/**
 * Vitest lacks Angular JIT compiler setup, so we mirror PathPairsComponent's
 * methods inline and exercise them directly. Same pattern as the existing
 * model/pipe spec files.
 */
class PathPairsLogic {
  editingId: string | null = null;
  editForm: Omit<PathPair, 'id'> = this.emptyForm();
  adding = false;
  addForm: Omit<PathPair, 'id'> = this.emptyForm();
  confirmingDeleteId: string | null = null;
  arrPickerPairId: string | null = null;
  private confirmResetTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private service: PathPairsServiceLike) {}

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
    this.service.create(this.addForm).subscribe((created: PathPair | null) => {
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
      arr_target_ids: [...pair.arr_target_ids],
    };
  }

  onCancelEdit(): void {
    this.editingId = null;
    this.editForm = this.emptyForm();
  }

  onSaveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim()) return;
    this.service.update({ id: this.editingId, ...this.editForm }).subscribe((updated: PathPair | null) => {
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

  // --- Arr targets ---

  attachedInstances(pair: PathPair, allInstances: ArrInstance[] | null): ArrInstance[] {
    if (!allInstances) return [];
    const byId = new Map(allInstances.map((i) => [i.id, i]));
    return pair.arr_target_ids
      .map((id) => byId.get(id))
      .filter((i): i is ArrInstance => i !== undefined);
  }

  availableInstances(pair: PathPair, allInstances: ArrInstance[] | null): ArrInstance[] {
    if (!allInstances) return [];
    return allInstances.filter((i) => !pair.arr_target_ids.includes(i.id));
  }

  togglePicker(pairId: string): void {
    this.arrPickerPairId = this.arrPickerPairId === pairId ? null : pairId;
  }

  onAttachInstance(pair: PathPair, instance: ArrInstance): void {
    if (pair.arr_target_ids.includes(instance.id)) return;
    const updated = { ...pair, arr_target_ids: [...pair.arr_target_ids, instance.id] };
    this.arrPickerPairId = null;
    this.service.update(updated).subscribe();
  }

  onDetachInstance(pair: PathPair, instanceId: string): void {
    const updated = {
      ...pair,
      arr_target_ids: pair.arr_target_ids.filter((id) => id !== instanceId),
    };
    this.service.update(updated).subscribe();
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
    return {
      name: '',
      remote_path: '',
      local_path: '',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    };
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
  let mockService: {
    create: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    mockService = {
      create: vi.fn().mockReturnValue(of(makePair({ id: '2', name: 'New' }))),
      update: vi.fn().mockReturnValue(of(makePair({ enabled: false }))),
      remove: vi.fn().mockReturnValue(of(true)),
    };
    component = new PathPairsLogic(mockService as unknown as PathPairsServiceLike);
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

  it('should call create on save add with arr_target_ids included', () => {
    component.onStartAdd();
    component.addForm = {
      name: 'Test',
      remote_path: '/r',
      local_path: '/l',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    };
    component.onSaveAdd();
    expect(mockService.create).toHaveBeenCalledWith({
      name: 'Test',
      remote_path: '/r',
      local_path: '/l',
      enabled: true,
      auto_queue: false,
      arr_target_ids: [],
    });
  });

  it('should preserve arr_target_ids when entering edit mode', () => {
    const pair = makePair({ arr_target_ids: ['a', 'b'] });
    component.onStartEdit(pair);
    expect(component.editForm.arr_target_ids).toEqual(['a', 'b']);
    // Mutating the form must not mutate the source pair
    component.editForm.arr_target_ids.push('c');
    expect(pair.arr_target_ids).toEqual(['a', 'b']);
  });

  it('should require double-click to delete', () => {
    component.onDelete('1');
    expect(component.confirmingDeleteId).toBe('1');
    expect(mockService.remove).not.toHaveBeenCalled();

    component.onDelete('1');
    expect(mockService.remove).toHaveBeenCalledWith('1');
    expect(component.confirmingDeleteId).toBeNull();
  });

  describe('arr target attachment', () => {
    it('attachedInstances returns instances in the order of arr_target_ids', () => {
      const a = makeInstance({ id: 'a', name: 'A' });
      const b = makeInstance({ id: 'b', name: 'B' });
      const pair = makePair({ arr_target_ids: ['b', 'a'] });
      const result = component.attachedInstances(pair, [a, b]);
      expect(result.map((i) => i.id)).toEqual(['b', 'a']);
    });

    it('attachedInstances drops dangling ids', () => {
      const a = makeInstance({ id: 'a', name: 'A' });
      const pair = makePair({ arr_target_ids: ['a', 'ghost'] });
      const result = component.attachedInstances(pair, [a]);
      expect(result.map((i) => i.id)).toEqual(['a']);
    });

    it('availableInstances excludes already-attached instances', () => {
      const a = makeInstance({ id: 'a', name: 'A' });
      const b = makeInstance({ id: 'b', name: 'B' });
      const pair = makePair({ arr_target_ids: ['a'] });
      const result = component.availableInstances(pair, [a, b]);
      expect(result.map((i) => i.id)).toEqual(['b']);
    });

    it('onAttachInstance updates with the new id appended', () => {
      const inst = makeInstance({ id: 'new' });
      const pair = makePair({ arr_target_ids: ['existing'] });
      component.onAttachInstance(pair, inst);
      expect(mockService.update).toHaveBeenCalledWith(
        expect.objectContaining({ arr_target_ids: ['existing', 'new'] }),
      );
    });

    it('onAttachInstance is a no-op for already-attached instance', () => {
      const inst = makeInstance({ id: 'a' });
      const pair = makePair({ arr_target_ids: ['a'] });
      component.onAttachInstance(pair, inst);
      expect(mockService.update).not.toHaveBeenCalled();
    });

    it('onAttachInstance closes the picker', () => {
      component.arrPickerPairId = 'pair-1';
      const inst = makeInstance({ id: 'new' });
      const pair = makePair({ id: 'pair-1', arr_target_ids: [] });
      component.onAttachInstance(pair, inst);
      expect(component.arrPickerPairId).toBeNull();
    });

    it('onDetachInstance removes the id from arr_target_ids', () => {
      const pair = makePair({ arr_target_ids: ['a', 'b', 'c'] });
      component.onDetachInstance(pair, 'b');
      expect(mockService.update).toHaveBeenCalledWith(
        expect.objectContaining({ arr_target_ids: ['a', 'c'] }),
      );
    });

    it('togglePicker opens and closes the picker for a pair', () => {
      expect(component.arrPickerPairId).toBeNull();
      component.togglePicker('pair-1');
      expect(component.arrPickerPairId).toBe('pair-1');
      component.togglePicker('pair-1');
      expect(component.arrPickerPairId).toBeNull();
    });

    it('togglePicker switches between pairs', () => {
      component.togglePicker('pair-1');
      component.togglePicker('pair-2');
      expect(component.arrPickerPairId).toBe('pair-2');
    });
  });
});
