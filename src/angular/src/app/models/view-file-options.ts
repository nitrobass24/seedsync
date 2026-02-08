import { ViewFileStatus } from './view-file';

/**
 * View file options - describes display-related options for view files.
 */
export interface ViewFileOptions {
  showDetails: boolean;
  sortMethod: SortMethod;
  selectedStatusFilter: ViewFileStatus | null;
  nameFilter: string;
  pinFilter: boolean;
}

export enum SortMethod {
  STATUS,
  NAME_ASC,
  NAME_DESC,
}
