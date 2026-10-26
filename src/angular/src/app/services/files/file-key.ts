/** ASCII Unit Separator -- safe composite-key delimiter that cannot appear in filenames */
export const FILE_KEY_SEP = '\x1f';

export function fileKey(pairId: string | null, name: string): string {
  return pairId ? `${pairId}${FILE_KEY_SEP}${name}` : name;
}

/** Split a fileKey() back into its pairId and name/fullPath parts. */
export function parseFileKey(key: string): { pairId: string | null; name: string } {
  const idx = key.indexOf(FILE_KEY_SEP);
  if (idx === -1) {
    return { pairId: null, name: key };
  }
  return { pairId: key.slice(0, idx), name: key.slice(idx + FILE_KEY_SEP.length) };
}

/**
 * Row identity for a ViewFile/ModelFile-like object, keyed by fullPath (not
 * name) so nested rows with the same leaf name in different folders don't
 * collide. Equals fileKey(pairId, name) for top-level files, where
 * fullPath === name.
 */
export function viewFileKey(vf: { pairId: string | null; fullPath: string }): string {
  return fileKey(vf.pairId, vf.fullPath);
}
