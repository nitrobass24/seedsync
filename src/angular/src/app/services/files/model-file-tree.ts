import { ModelFile } from '../../models/model-file';
import { fileKey, parseFileKey } from './file-key';

/**
 * Resolve a fullPath-keyed row identity (see viewFileKey) back to its backing
 * ModelFile, walking into a top-level entry's `children` when the key doesn't
 * match a top-level entry directly.
 *
 * `topLevel` is keyed by fileKey(pairId, name) (top-level name only) - the
 * shape ModelFileService's SSE-driven map already uses, since the backend only
 * emits add/remove/update events for top-level files. Nested files live only
 * as `children` on those top-level entries.
 */
export function resolveNestedModelFile(
  topLevel: ReadonlyMap<string, ModelFile>,
  key: string,
): ModelFile | undefined {
  const { pairId, name: fullPath } = parseFileKey(key);
  const segments = fullPath.split('/');
  let file = topLevel.get(fileKey(pairId, segments[0]));
  if (file === undefined) {
    return undefined;
  }
  for (let i = 1; i < segments.length; i++) {
    file = file.children.find((c) => c.name === segments[i]);
    if (file === undefined) {
      return undefined;
    }
  }
  return file;
}
