import { describe, it, expect, beforeEach } from 'vitest';

import { ViewFileSelectionService } from './view-file-selection.service';

describe('ViewFileSelectionService', () => {
  let service: ViewFileSelectionService;

  beforeEach(() => {
    service = new ViewFileSelectionService();
  });

  function latestChecked(): Set<string> {
    let result = new Set<string>();
    service.checked$.subscribe((s) => (result = s));
    return result;
  }

  it('starts with an empty checked set', () => {
    expect(latestChecked().size).toBe(0);
    expect(service.snapshot().size).toBe(0);
    expect(service.isChecked('a')).toBe(false);
  });

  // --- toggle ---

  it('toggle adds a key when absent and removes it when present', () => {
    service.toggle('a');
    expect(service.isChecked('a')).toBe(true);
    expect(latestChecked().has('a')).toBe(true);

    service.toggle('a');
    expect(service.isChecked('a')).toBe(false);
    expect(latestChecked().has('a')).toBe(false);
  });

  it('toggle emits a fresh defensive copy each time', () => {
    const emissions: Set<string>[] = [];
    service.checked$.subscribe((s) => emissions.push(s));
    const initial = emissions.length;

    service.toggle('a');
    service.toggle('b');

    expect(emissions.length).toBe(initial + 2);
    // Distinct set instances, not the internal mutable set.
    expect(emissions[emissions.length - 1]).not.toBe(emissions[emissions.length - 2]);
    expect(emissions[emissions.length - 1].has('a')).toBe(true);
    expect(emissions[emissions.length - 1].has('b')).toBe(true);
  });

  // --- shiftRange ---

  it('shiftRange falls back to toggle when there is no prior anchor', () => {
    service.shiftRange('b', ['a', 'b', 'c']);
    expect(service.snapshot()).toEqual(new Set(['b']));
  });

  it('shiftRange selects the inclusive forward range from the anchor', () => {
    service.toggle('a'); // anchor = a
    service.shiftRange('c', ['a', 'b', 'c', 'd']);
    expect(service.snapshot()).toEqual(new Set(['a', 'b', 'c']));
  });

  it('shiftRange selects the inclusive backward range from the anchor', () => {
    service.toggle('d'); // anchor = d
    service.shiftRange('b', ['a', 'b', 'c', 'd']);
    expect(service.snapshot()).toEqual(new Set(['b', 'c', 'd']));
  });

  it('shiftRange moves the anchor to the latest key for chained ranges', () => {
    service.toggle('a'); // anchor = a
    service.shiftRange('c', ['a', 'b', 'c', 'd', 'e']); // anchor now c
    service.shiftRange('e', ['a', 'b', 'c', 'd', 'e']); // c..e
    expect(service.snapshot()).toEqual(new Set(['a', 'b', 'c', 'd', 'e']));
  });

  it('shiftRange falls back to toggle when the anchor is no longer in the list', () => {
    service.toggle('z'); // anchor = z, but z not in the list below
    service.shiftRange('b', ['a', 'b', 'c']);
    // z stayed checked (from its own toggle), b toggled on via fallback
    expect(service.snapshot()).toEqual(new Set(['z', 'b']));
  });

  it('shiftRange falls back to toggle when the target key is not in the list', () => {
    service.toggle('a'); // anchor = a
    service.shiftRange('zzz', ['a', 'b', 'c']);
    // zzz not present -> fallback toggles zzz on
    expect(service.snapshot()).toEqual(new Set(['a', 'zzz']));
  });

  // --- checkAll ---

  it('checkAll checks every provided key', () => {
    service.checkAll(['a', 'b', 'c']);
    expect(service.snapshot()).toEqual(new Set(['a', 'b', 'c']));
    expect(latestChecked()).toEqual(new Set(['a', 'b', 'c']));
  });

  it('checkAll unions with the existing selection', () => {
    service.toggle('x');
    service.checkAll(['a', 'b']);
    expect(service.snapshot()).toEqual(new Set(['x', 'a', 'b']));
  });

  // --- uncheckAll ---

  it('uncheckAll clears the set and the anchor', () => {
    service.toggle('a'); // anchor = a
    service.checkAll(['b', 'c']);
    service.uncheckAll();
    expect(service.snapshot().size).toBe(0);
    expect(latestChecked().size).toBe(0);

    // Anchor was cleared: a subsequent shiftRange falls back to a plain toggle.
    service.shiftRange('c', ['a', 'b', 'c']);
    expect(service.snapshot()).toEqual(new Set(['c']));
  });

  // --- pruneRemoved ---

  it('pruneRemoved drops removed keys, returns true, and re-emits checked$', () => {
    service.checkAll(['keep', 'gone']);
    const emissions: Set<string>[] = [];
    service.checked$.subscribe((s) => emissions.push(s));
    const before = emissions.length;

    const changed = service.pruneRemoved(['gone']);

    expect(changed).toBe(true);
    expect(service.isChecked('gone')).toBe(false);
    expect(service.isChecked('keep')).toBe(true);
    expect(emissions.length).toBe(before + 1);
    expect(emissions[emissions.length - 1].has('gone')).toBe(false);
  });

  it('pruneRemoved returns false and does NOT re-emit when no key was checked', () => {
    service.checkAll(['keep']);
    const emissions: Set<string>[] = [];
    service.checked$.subscribe((s) => emissions.push(s));
    const before = emissions.length;

    const changed = service.pruneRemoved(['never-checked']);

    expect(changed).toBe(false);
    expect(emissions.length).toBe(before); // no re-emission
  });

  it('pruneRemoved does not disturb the shift anchor', () => {
    service.toggle('a'); // anchor = a
    service.checkAll(['b', 'c']);
    service.pruneRemoved(['b']);
    // anchor still 'a' -> range a..c selects a, c (b was removed but reselected in range)
    service.shiftRange('c', ['a', 'b', 'c']);
    expect(service.snapshot()).toEqual(new Set(['a', 'b', 'c']));
  });

  // --- snapshot defensiveness ---

  it('snapshot returns a copy that does not mutate internal state', () => {
    service.toggle('a');
    const snap = service.snapshot();
    snap.add('b');
    expect(service.isChecked('b')).toBe(false);
  });
});
