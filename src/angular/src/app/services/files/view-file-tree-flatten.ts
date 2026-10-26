import { ViewFile } from '../../models/view-file';
import { viewFileKey } from './file-key';

/** A single row in the flattened, expansion-aware display list. */
export interface FlatViewFileRow {
  file: ViewFile;
  depth: number;
  hasChildren: boolean;
  isExpanded: boolean;
}

/**
 * Flatten the top-level file list plus each row's nested `children` into a
 * single display list, honoring which rows are currently expanded.
 *
 * A flat list (rather than rendering `children` recursively inside a row's own
 * template) is required so the display stays compatible with
 * CdkFixedSizeVirtualScroll, which assumes every rendered item has the same
 * fixed height - a row that grows to contain its own nested subtree would
 * violate that and visually overlap the next virtual-scrolled row.
 *
 * When nested navigation is disabled, ViewFileService builds rows with no
 * children, so this degrades to one row per top-level file.
 */
export function flattenVisibleRows(
  files: readonly ViewFile[],
  expandedKeys: ReadonlySet<string>,
): FlatViewFileRow[] {
  const rows: FlatViewFileRow[] = [];
  for (const file of files) {
    appendRow(rows, file, 0, expandedKeys);
  }
  return rows;
}

function appendRow(
  rows: FlatViewFileRow[],
  file: ViewFile,
  depth: number,
  expandedKeys: ReadonlySet<string>,
): void {
  const hasChildren = file.children.length > 0;
  const key = viewFileKey(file);
  const isExpanded = hasChildren && expandedKeys.has(key);
  rows.push({ file, depth, hasChildren, isExpanded });
  if (isExpanded) {
    for (const child of file.children) {
      appendRow(rows, child, depth + 1, expandedKeys);
    }
  }
}
