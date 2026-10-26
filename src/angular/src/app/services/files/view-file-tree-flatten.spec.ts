import { describe, it, expect } from 'vitest';
import { flattenVisibleRows } from './view-file-tree-flatten';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { viewFileKey } from './file-key';

function makeViewFile(overrides: Partial<ViewFile> & { name: string; fullPath: string }): ViewFile {
  return {
    pairId: null,
    pairName: null,
    isDir: false,
    localSize: 0,
    remoteSize: 0,
    percentDownloaded: 0,
    status: ViewFileStatus.DEFAULT,
    downloadingSpeed: 0,
    eta: 0,
    isArchive: false,
    isSelected: false,
    isChecked: false,
    isIndeterminate: false,
    isQueueable: false,
    isStoppable: false,
    isExtractable: false,
    isLocallyDeletable: false,
    isRemotelyDeletable: false,
    isCleanupLocalable: false,
    hasDownloadingDescendant: false,
    isValidatable: false,
    validateTooltip: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
    children: [],
    ...overrides,
  };
}

describe('flattenVisibleRows', () => {
  it('gives a row without children no expand toggle (nested nav off builds no children)', () => {
    const top = makeViewFile({ name: 'Top', fullPath: 'Top', isDir: true, children: [] });

    const rows = flattenVisibleRows([top], new Set([viewFileKey(top)]));

    expect(rows).toEqual([{ file: top, depth: 0, hasChildren: false, isExpanded: false }]);
  });

  it('marks a dir with children as hasChildren when nav is enabled, collapsed by default', () => {
    const child = makeViewFile({ name: 'child.txt', fullPath: 'Top/child.txt' });
    const top = makeViewFile({ name: 'Top', fullPath: 'Top', isDir: true, children: [child] });

    const rows = flattenVisibleRows([top], new Set());

    expect(rows).toEqual([{ file: top, depth: 0, hasChildren: true, isExpanded: false }]);
  });

  it('inserts children directly after their parent when expanded', () => {
    const child = makeViewFile({ name: 'child.txt', fullPath: 'Top/child.txt' });
    const top = makeViewFile({ name: 'Top', fullPath: 'Top', isDir: true, children: [child] });
    const sibling = makeViewFile({ name: 'Sibling', fullPath: 'Sibling', isDir: false });

    const rows = flattenVisibleRows([top, sibling], new Set([viewFileKey(top)]));

    expect(rows).toEqual([
      { file: top, depth: 0, hasChildren: true, isExpanded: true },
      { file: child, depth: 1, hasChildren: false, isExpanded: false },
      { file: sibling, depth: 0, hasChildren: false, isExpanded: false },
    ]);
  });

  it('recurses into nested expansion at increasing depth', () => {
    const leaf = makeViewFile({ name: 'leaf.txt', fullPath: 'Top/Sub/leaf.txt' });
    const sub = makeViewFile({ name: 'Sub', fullPath: 'Top/Sub', isDir: true, children: [leaf] });
    const top = makeViewFile({ name: 'Top', fullPath: 'Top', isDir: true, children: [sub] });

    const rows = flattenVisibleRows([top], new Set([viewFileKey(top), viewFileKey(sub)]));

    expect(rows.map((r) => ({ name: r.file.name, depth: r.depth }))).toEqual([
      { name: 'Top', depth: 0 },
      { name: 'Sub', depth: 1 },
      { name: 'leaf.txt', depth: 2 },
    ]);
  });

  it('does not descend into an unexpanded dir even if it is in the expanded set for a different row', () => {
    const child = makeViewFile({ name: 'child.txt', fullPath: 'Top/child.txt' });
    const top = makeViewFile({ name: 'Top', fullPath: 'Top', isDir: true, children: [child] });

    // Top is not in the expanded set - its child must not appear.
    const rows = flattenVisibleRows([top], new Set(['unrelated-key']));

    expect(rows).toEqual([{ file: top, depth: 0, hasChildren: true, isExpanded: false }]);
  });
});
