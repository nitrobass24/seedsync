import { describe, it, expect } from 'vitest';
import { resolveNestedModelFile } from './model-file-tree';
import { ModelFile, ModelFileState } from '../../models/model-file';
import { fileKey } from './file-key';

function makeModelFile(overrides: Partial<ModelFile> & { name: string; full_path: string }): ModelFile {
  return {
    pair_id: null,
    is_dir: false,
    local_size: 0,
    remote_size: 0,
    state: ModelFileState.DEFAULT,
    downloading_speed: 0,
    eta: 0,
    is_extractable: false,
    local_created_timestamp: null,
    local_modified_timestamp: null,
    remote_created_timestamp: null,
    remote_modified_timestamp: null,
    children: [],
    ...overrides,
  };
}

describe('resolveNestedModelFile', () => {
  it('resolves a top-level entry directly', () => {
    const top = makeModelFile({ name: 'Top.rar', full_path: 'Top.rar' });
    const map = new Map([[fileKey(null, 'Top.rar'), top]]);

    expect(resolveNestedModelFile(map, fileKey(null, 'Top.rar'))).toBe(top);
  });

  it('walks one level into children', () => {
    const leaf = makeModelFile({ name: 'leaf.txt', full_path: 'Top/leaf.txt' });
    const top = makeModelFile({ name: 'Top', full_path: 'Top', is_dir: true, children: [leaf] });
    const map = new Map([[fileKey(null, 'Top'), top]]);

    expect(resolveNestedModelFile(map, fileKey(null, 'Top/leaf.txt'))).toBe(leaf);
  });

  it('walks two levels into children', () => {
    const leaf = makeModelFile({ name: 'leaf.txt', full_path: 'Top/Sub/leaf.txt' });
    const sub = makeModelFile({ name: 'Sub', full_path: 'Top/Sub', is_dir: true, children: [leaf] });
    const top = makeModelFile({ name: 'Top', full_path: 'Top', is_dir: true, children: [sub] });
    const map = new Map([[fileKey(null, 'Top')  , top]]);

    expect(resolveNestedModelFile(map, fileKey(null, 'Top/Sub/leaf.txt'))).toBe(leaf);
  });

  it('is pair-aware: only resolves within the matching top-level pair entry', () => {
    const leafA = makeModelFile({ name: 'leaf.txt', full_path: 'Top/leaf.txt', pair_id: 'pair-a' });
    const topA = makeModelFile({
      name: 'Top', full_path: 'Top', is_dir: true, pair_id: 'pair-a', children: [leafA],
    });
    const topB = makeModelFile({ name: 'Top', full_path: 'Top', is_dir: true, pair_id: 'pair-b', children: [] });
    const map = new Map([
      [fileKey('pair-a', 'Top'), topA],
      [fileKey('pair-b', 'Top'), topB],
    ]);

    expect(resolveNestedModelFile(map, fileKey('pair-a', 'Top/leaf.txt'))).toBe(leafA);
    expect(resolveNestedModelFile(map, fileKey('pair-b', 'Top/leaf.txt'))).toBeUndefined();
  });

  it('returns undefined when the top-level segment is missing', () => {
    const map = new Map<string, ModelFile>();
    expect(resolveNestedModelFile(map, fileKey(null, 'NoSuchTop/leaf.txt'))).toBeUndefined();
  });

  it('returns undefined when a nested segment is missing', () => {
    const top = makeModelFile({ name: 'Top', full_path: 'Top', is_dir: true, children: [] });
    const map = new Map([[fileKey(null, 'Top'), top]]);

    expect(resolveNestedModelFile(map, fileKey(null, 'Top/no_such_child.txt'))).toBeUndefined();
  });
});
