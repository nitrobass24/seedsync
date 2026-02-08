import { describe, it, expect } from 'vitest';
import { modelFileFromJson, ModelFileState } from './model-file';

describe('modelFileFromJson', () => {
  function makeJson(overrides: Record<string, any> = {}) {
    return {
      name: 'test.txt',
      is_dir: false,
      local_size: 100,
      remote_size: 200,
      state: 'DEFAULT',
      downloading_speed: 50,
      eta: 10,
      full_path: '/remote/test.txt',
      is_extractable: false,
      local_created_timestamp: null,
      local_modified_timestamp: null,
      remote_created_timestamp: null,
      remote_modified_timestamp: null,
      children: [],
      ...overrides,
    };
  }

  it('should parse all fields from JSON correctly', () => {
    const json = makeJson({
      name: 'movie.mkv',
      is_dir: false,
      local_size: 500,
      remote_size: 1000,
      state: 'DOWNLOADING',
      downloading_speed: 1024,
      eta: 60,
      full_path: '/remote/movie.mkv',
      is_extractable: true,
    });

    const result = modelFileFromJson(json);

    expect(result.name).toBe('movie.mkv');
    expect(result.is_dir).toBe(false);
    expect(result.local_size).toBe(500);
    expect(result.remote_size).toBe(1000);
    expect(result.state).toBe(ModelFileState.DOWNLOADING);
    expect(result.downloading_speed).toBe(1024);
    expect(result.eta).toBe(60);
    expect(result.full_path).toBe('/remote/movie.mkv');
    expect(result.is_extractable).toBe(true);
  });

  it('should map state strings to ModelFileState enum via toUpperCase', () => {
    const states: Array<[string, ModelFileState]> = [
      ['default', ModelFileState.DEFAULT],
      ['queued', ModelFileState.QUEUED],
      ['downloading', ModelFileState.DOWNLOADING],
      ['downloaded', ModelFileState.DOWNLOADED],
      ['deleted', ModelFileState.DELETED],
      ['extracting', ModelFileState.EXTRACTING],
      ['extracted', ModelFileState.EXTRACTED],
      ['DOWNLOADING', ModelFileState.DOWNLOADING],
      ['Queued', ModelFileState.QUEUED],
    ];

    for (const [input, expected] of states) {
      const result = modelFileFromJson(makeJson({ state: input }));
      expect(result.state).toBe(expected);
    }
  });

  it('should fall back to DEFAULT for unknown state strings', () => {
    const result = modelFileFromJson(makeJson({ state: 'UNKNOWN_STATE' }));
    expect(result.state).toBe(ModelFileState.DEFAULT);
  });

  it('should convert timestamps from seconds to milliseconds', () => {
    const json = makeJson({
      local_created_timestamp: 1700000000,
      local_modified_timestamp: 1700000100,
      remote_created_timestamp: 1700000200,
      remote_modified_timestamp: 1700000300,
    });

    const result = modelFileFromJson(json);

    expect(result.local_created_timestamp).toEqual(new Date(1700000000 * 1000));
    expect(result.local_modified_timestamp).toEqual(new Date(1700000100 * 1000));
    expect(result.remote_created_timestamp).toEqual(new Date(1700000200 * 1000));
    expect(result.remote_modified_timestamp).toEqual(new Date(1700000300 * 1000));
  });

  it('should handle null timestamps', () => {
    const result = modelFileFromJson(makeJson());

    expect(result.local_created_timestamp).toBeNull();
    expect(result.local_modified_timestamp).toBeNull();
    expect(result.remote_created_timestamp).toBeNull();
    expect(result.remote_modified_timestamp).toBeNull();
  });

  it('should recursively parse children', () => {
    const json = makeJson({
      name: 'parent',
      is_dir: true,
      children: [
        makeJson({ name: 'child1.txt', state: 'DOWNLOADED' }),
        makeJson({
          name: 'subfolder',
          is_dir: true,
          children: [
            makeJson({ name: 'grandchild.txt', state: 'QUEUED' }),
          ],
        }),
      ],
    });

    const result = modelFileFromJson(json);

    expect(result.children).toHaveLength(2);
    expect(result.children[0].name).toBe('child1.txt');
    expect(result.children[0].state).toBe(ModelFileState.DOWNLOADED);
    expect(result.children[1].name).toBe('subfolder');
    expect(result.children[1].is_dir).toBe(true);
    expect(result.children[1].children).toHaveLength(1);
    expect(result.children[1].children[0].name).toBe('grandchild.txt');
    expect(result.children[1].children[0].state).toBe(ModelFileState.QUEUED);
  });
});
