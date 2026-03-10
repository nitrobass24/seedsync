/** ASCII Unit Separator -- safe composite-key delimiter that cannot appear in filenames */
export const FILE_KEY_SEP = '\x1f';

export function fileKey(pairId: string | null, name: string): string {
  return pairId ? `${pairId}${FILE_KEY_SEP}${name}` : name;
}
